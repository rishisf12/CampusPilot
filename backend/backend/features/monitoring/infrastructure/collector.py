"""Telemetry collection: validating and storing usage events.

This is the ingest path for both the web beacon and the Android SDK. It is
unauthenticated by necessity - a client cannot hold a database credential - so
the defences are: strict schema validation, a body size cap, and a per-source
rate limit. There is no write capability in the request beyond "append an event".

Privacy properties, which are the reason this is hand-written rather than
pointed at an off-the-shelf analytics product:

* No IP address is stored. A truncated HMAC of the remote address is kept in
  `security_event.ip_hash` for rate limiting and nothing else.
* No user id in the clear. `user_hash` is HMAC-SHA256 with a server-side pepper,
  so it cannot be reversed by anyone holding only the table.
* No free-text user content. `props` is a flat map of scalars, capped in size,
  and is never rendered.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from features.monitoring.infrastructure.metrics import COLLECTOR_EVENTS
from features.monitoring.infrastructure.ratelimit import COLLECT_BATCH_LIMIT, CRASH_LIMIT
from features.monitoring.domain.models import (
    AdEvent,
    Event,
    Platform,
    Purchase,
    Session as MonitorSession,
)

#: Event names we accept. An allowlist rather than a blocklist, because the
#: failure mode of an allowlist is a dropped metric and the failure mode of a
#: blocklist is unbounded cardinality in a table someone will query forever.
ALLOWED_EVENTS = frozenset({
    "app_open", "app_close", "screen_view", "page_view",
    "sign_up", "sign_in", "sign_out", "session_start", "session_end",
    "push_received", "push_opened",
    "purchase_started", "purchase_completed", "subscription_renewed",
    "ad_impression", "ad_click",
    "feedback_submitted", "rating_given",
    "crash", "anr", "slow_frame",
    "root_detected", "emulator_detected", "tamper_detected",
    # Web security signals (server-side only)
    "failed_login", "brute_force", "rate_limited", "waf_blocked",
})

MAX_PROPS = 12
MAX_PROP_LEN = 120
MAX_MESSAGE = 4000

_EVENT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,47}$")
_VERSION_RE = re.compile(r"^[A-Za-z0-9._+\-]{1,32}$")
_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")


class CollectError(ValueError):
    """Rejected input. Carries a reason that is safe to log."""


def user_hash(pepper: str, user_id: int | None) -> str | None:
    """HMAC a user id with the server pepper.

    Not a bare hash. Given a known email, a plain SHA-256 of it is trivially
    reversed by anyone with the table, because email addresses are enumerable.
    An HMAC with a secret the attacker does not have is not.
    """
    if user_id is None:
        return None
    return hmac.new(pepper.encode(), str(user_id).encode(), hashlib.sha256).hexdigest()


def ip_hash(pepper: str, ip: str | None) -> str | None:
    """Truncated HMAC of a remote address.

    Truncated to 32 hex chars: enough to group by source for rate limiting and
    brute-force detection, short enough that it is not a stable identifier for
    one person's browsing across months.
    """
    if not ip:
        return None
    return hmac.new(pepper.encode(), ip.encode(), hashlib.sha256).hexdigest()[:32]


def _clean_scalar(v: Any) -> Any:
    """Reduce a prop value to something bounded and scalar."""
    if isinstance(v, bool) or isinstance(v, (int, float)):
        return v
    s = str(v)[:MAX_PROP_LEN]
    return s


def validate_event(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalise one event, or raise `CollectError`.

    Every rejection reason is generic on purpose. Echoing back "event_name 'xyz'
    is not in the allowlist" turns the collector into an oracle for enumerating
    what the app records, which is not worth the debugging convenience.
    """
    if not isinstance(raw, dict):
        raise CollectError("event must be an object")

    name = str(raw.get("event_name") or "")
    if not _EVENT_NAME_RE.match(name) or name not in ALLOWED_EVENTS:
        raise CollectError("unknown event_name")

    platform = str(raw.get("platform") or "")
    if platform not in {Platform.WEB.value, Platform.ANDROID.value}:
        raise CollectError("bad platform")

    session_id = str(raw.get("session_id") or "")
    if not (8 <= len(session_id) <= 64):
        raise CollectError("bad session_id")

    props_in = raw.get("props") or {}
    if not isinstance(props_in, dict):
        raise CollectError("props must be an object")
    # Truncate rather than reject: a client sending extra keys should still get
    # its event recorded, and the cap is what bounds the column.
    props = {str(k)[:40]: _clean_scalar(v) for k, v in list(props_in.items())[:MAX_PROPS]}

    def opt_version(v: Any) -> str | None:
        if v is None:
            return None
        s = str(v)[:32]
        return s if _VERSION_RE.match(s) else None

    country = raw.get("country")
    country = str(country)[:2].upper() if country and _COUNTRY_RE.match(str(country).upper()) else None

    ts = raw.get("ts")
    when = datetime.now(timezone.utc).replace(tzinfo=None)
    if ts:
        try:
            when = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            raise CollectError("bad ts")

    return {
        "ts": when,
        "platform": platform,
        "session_id": session_id,
        "event_name": name,
        "props": props,
        "app_version": opt_version(raw.get("app_version")),
        "os_version": opt_version(raw.get("os_version")),
        "device_model": (str(raw["device_model"])[:64] if raw.get("device_model") else None),
        "country": country,
    }


def _price_micros(value: Any) -> int:
    """Coerce a price to integer minor units.

    Money is never a float. `0.1 + 0.2 != 0.3`, and a revenue total that drifts
    by a paisa is a support ticket. The client may send a float for convenience;
    it is rounded once, here, and stored as an integer.
    """
    try:
        return max(0, int(round(float(value) * 1_000_000)))
    except (TypeError, ValueError):
        return 0


def collect(db: Session, payload: dict[str, Any], *, user_id: int | None = None,
            pepper: str = "", ip: str | None = None) -> dict[str, Any]:
    """Accept a batch of events. Partial success is normal, not exceptional.

    A mobile client on a flaky connection batches 50 events; losing all 50
    because one had a bad device_model is worse than recording 49. So each event
    is validated independently and failures are counted, not raised.
    """
    events_in = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events_in, list):
        raise CollectError("events must be a list")
    if len(events_in) > 200:
        raise CollectError("too many events in one batch")

    accepted, rejected = 0, 0
    platform_hint = str(payload.get("platform") or "")

    for raw in events_in:
        if not isinstance(raw, dict):
            rejected += 1
            COLLECTOR_EVENTS.labels(platform_hint or "unknown", "rejected").inc()
            continue
        try:
            ev = validate_event(raw)
        except CollectError:
            rejected += 1
            COLLECTOR_EVENTS.labels(ev_platform(raw) or platform_hint or "unknown",
                                   "rejected").inc()
            continue

        row = Event(user_hash=user_hash(pepper, user_id), **ev)
        db.add(row)
        _side_effects(db, row, pepper=pepper, ip=ip)
        accepted += 1
        COLLECTOR_EVENTS.labels(row.platform, "accepted").inc()

    db.commit()
    return {"accepted": accepted, "rejected": rejected}


def ev_platform(raw: dict[str, Any]) -> str:
    """Best-effort platform for a rejected event, for metric labelling only."""
    p = str((raw or {}).get("platform") or "")
    return p if p in {"web", "android"} else ""


def _side_effects(db: Session, ev: Event, *, pepper: str, ip: str | None) -> None:
    """Derive the aggregate tables an event implies.

    Purchase and ad rows are promoted out of the event stream at write time rather
    than aggregated later. They are low-volume, money-bearing, and need to be
    individually auditable - "the revenue table" is exactly the thing an auditor
    asks to reconcile, and it should not require replaying raw events.
    """
    if ev.event_name == "purchase_completed":
        props = ev.props or {}
        txn = str(props.get("transaction_id") or "")[:128]
        if txn:
            existing = db.exec(
                select(Purchase).where(Purchase.transaction_id == txn)
            ).first()
            if existing is None:
                db.add(Purchase(
                    transaction_id=txn,
                    ts=ev.ts,
                    platform=ev.platform,
                    product_id=str(props.get("product_id") or "unknown")[:64],
                    price_micros=_price_micros(props.get("price", 0)),
                    currency=str(props.get("currency") or "INR")[:8],
                    user_hash=ev.user_hash,
                    app_version=ev.app_version,
                    # A client claiming its own purchase is not verification.
                    verified=False,
                    kind=str(props.get("kind") or "one_time")[:24],
                ))

    if ev.event_name in {"ad_impression", "ad_click"}:
        props = ev.props or {}
        db.add(AdEvent(
            ts=ev.ts,
            platform=ev.platform,
            ad_network=str(props.get("network") or "unknown")[:32],
            ad_unit=str(props.get("ad_unit") or "unknown")[:64],
            event_type="impression" if ev.event_name == "ad_impression" else "click",
            revenue_micros=_price_micros(props.get("revenue", 0)) or None,
            currency=str(props.get("currency") or "INR")[:8],
            user_hash=ev.user_hash,
            app_version=ev.app_version,
        ))

    if ev.event_name == "session_start":
        # Guard against a replayed batch creating a second session row for the
        # same install. Mobile clients retry aggressively when a request times
        # out, so this is a routine occurrence, not a hypothetical - and a
        # duplicated session inflates both the session count and the denominator
        # of the crash-free rate.
        existing = db.exec(
            select(MonitorSession).where(MonitorSession.session_id == ev.session_id)
        ).first()
        if existing is None:
            db.add(MonitorSession(
                session_id=ev.session_id,
                platform=ev.platform,
                # Propagated so DAU/WAU/MAU can count distinct people. Without
                # this the session table only knows installs, and every user
                # metric silently degrades into a session count.
                user_hash=ev.user_hash,
                started_at=ev.ts,
                last_seen_at=ev.ts,
                app_version=ev.app_version,
                os_version=ev.os_version,
                device_model=ev.device_model,
                country=ev.country,
            ))
    elif ev.event_name == "session_end":
        s = db.exec(
            select(MonitorSession).where(MonitorSession.session_id == ev.session_id)
        ).first()
        if s is not None:
            s.last_seen_at = max(s.last_seen_at, ev.ts)
            # Bounded rather than trusted: a client that sends a session_end with
            # no matching start, or a wildly wrong duration, must not be able to
            # poison the "average session length" figure with a 10^9 second
            # outlier that survives every later average.
            s.duration_s = min(max(0, int(ev.ts.timestamp() - s.started_at.timestamp())), 86_400)
    elif ev.event_name in {"app_open", "screen_view", "page_view"}:
        s = db.exec(
            select(MonitorSession).where(MonitorSession.session_id == ev.session_id)
        ).first()
        if s is not None:
            s.last_seen_at = max(s.last_seen_at, ev.ts)
            s.event_count += 1


# Re-export rate limiters for use in routes
__all__ = [
    "validate_event",
    "user_hash",
    "ip_hash",
    "collect",
    "record_security_event",
    "CollectError",
    "COLLECT_BATCH_LIMIT",
    "CRASH_LIMIT",
]


def record_security_event(
    db: Session,
    kind: str,
    *,
    platform: str = "web",
    blocked: bool = False,
    user_id: int | None = None,
    pepper: str = "",
    ip: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Record a server-side security event (failed_login, brute_force, etc.).

    Called from middleware/auth code, not from the public collector endpoint.
    """
    from features.monitoring.domain.models import SecurityEvent
    from datetime import datetime, timezone

    client_ip_hash = ip_hash(pepper, ip) if ip else None
    user_h = user_hash(pepper, user_id) if user_id is not None else None

    signal = SecurityEvent(
        ts=datetime.now(timezone.utc).replace(tzinfo=None),
        platform=platform,
        kind=kind,
        ip_hash=client_ip_hash,
        user_hash=user_h,
        app_version=None,
        blocked=blocked,
        detail=detail or {},
    )
    db.add(signal)
    db.commit()