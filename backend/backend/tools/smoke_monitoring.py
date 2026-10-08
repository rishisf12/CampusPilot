"""End-to-end smoke test for the monitoring subsystem.

Not a pytest module - a script that runs against a real database and prints
what each endpoint returned, so the numbers can be eyeballed rather than only
asserted. Run from ``backend/backend``::

    DATABASE_URL=postgresql+psycopg://... python tools/smoke_monitoring.py
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlmodel import Session, delete, select

from core.config import get_settings
from core.database import create_db_and_tables, engine
from features.auth.routes import create_access_token
from features.monitoring import collector, rollup as rollup_mod
from features.monitoring.models import (
    AdEvent,
    CrashReport,
    Event,
    EventHourly,
    Purchase,
    SecurityEvent,
)
from features.monitoring.models import Session as MonitoringSessionModel
from main import app

#: `monitoring_session` is exported as `Session` from the models module because
#: plain `Session` would collide with SQLModel's own name.
MonitorSession = MonitoringSessionModel

UTC = timezone.utc
NOW = datetime.now(UTC).replace(tzinfo=None, microsecond=0)

PLATFORMS = ["web", "android"]
COUNTRIES = ["IN", "IN", "IN", "US", "SG"]
VERSIONS = {"web": ["1.4.0", "1.5.0"], "android": ["2.1.0"]}


def seed(session) -> None:
    """Wipe the monitoring tables and fill them with plausible data.

    Events go through `collector.collect` rather than being inserted directly.
    That is deliberate: the session table that DAU, retention and crash-free
    rate are computed from is populated as a side effect of `session_start`
    during ingest. Writing `event` rows straight into the database produces
    event volume with a DAU of zero, which looks like a bug and is really just
    a bypassed code path. Using the real collector exercises the whole chain.
    """
    for model in (Event, MonitorSession, EventHourly, AdEvent, CrashReport,
                  SecurityEvent, Purchase):
        session.exec(delete(model))
    session.commit()

    rng = random.Random(20261007)
    # One batch per (user, session). `collect` applies a single user_id to a
    # whole batch, so flushing per session is what makes `user_hash` correct.
    # Batching harder would need a per-event identity field, which is
    # deliberately absent from the schema: letting a client name its own user
    # would let anyone forge activity for anyone.
    for user in range(1, 121):
        for platform in PLATFORMS:
            # `joined_days_ago` is when this user first appeared. Weighted
            # towards recent days so the retention cohorts are populated; a flat
            # distribution puts almost nobody in the last three days, which
            # makes every day-1..day-3 cell read 0% and the dashboard look
            # broken when it is actually correct.
            joined = min(29, int(abs(rng.gauss(0, 11))))
            for _ in range(rng.randint(1, 6)):
                # Sessions happen at or *after* joining. Note the direction:
                # `days_ago` counts backwards, so a smaller number is more
                # recent. Drawing from [0, joined] therefore spreads sessions
                # from the signup day forward in time, and the user's
                # chronologically first session is the largest day number.
                #
                # Getting this backwards - drawing from [joined, 29] - makes
                # every user's earliest session land 29 days ago, which reads as
                # "no retention data" on the dashboard even though the query is
                # fine.
                days_ago = rng.randint(0, joined)
                ts = (NOW - timedelta(days=days_ago)).replace(
                    hour=rng.randint(7, 22), minute=rng.randint(0, 59)
                )
                sid = f"sess-{platform}-{user}-{rng.randint(1000, 9999)}"
                version = rng.choice(VERSIONS[platform])
                country = rng.choice(COUNTRIES)
                common = {
                    "platform": platform,
                    "session_id": sid,
                    "app_version": version,
                    "os_version": "17",
                    "country": country,
                    "ts": ts.isoformat() + "Z",
                }
                events = [{"event_name": n, **common}
                          for n in ("session_start", "app_open", "page_view", "sign_in")]
                collector.collect(session, {"events": events},
                                  user_id=user, pepper="smoke-pepper")

    # A handful of purchases, half of them verified.
    for i in range(20):
        session.add(Purchase(
            transaction_id=f"txn-{i}", ts=NOW - timedelta(days=rng.randint(0, 29)),
            platform="android", product_id="pro_monthly",
            price_micros=99_000_000 + rng.randint(0, 5) * 1_000_000,
            currency="INR", user_hash=f"hash-{rng.randint(1, 120)}",
            app_version="2.1.0", verified=(i % 2 == 0), kind="subscription",
        ))

    # Ad impressions and clicks.
    for _ in range(4000):
        session.add(AdEvent(
            ts=NOW - timedelta(days=rng.randint(0, 29)), platform="android",
            ad_network="local-test-net", ad_unit="banner",
            event_type="impression", revenue_micros=rng.randint(200, 1200),
            currency="INR", user_hash=f"hash-{rng.randint(1, 120)}", app_version="2.1.0",
        ))
    for _ in range(60):
        session.add(AdEvent(
            ts=NOW - timedelta(days=rng.randint(0, 29)), platform="android",
            ad_network="local-test-net", ad_unit="banner", event_type="click",
            revenue_micros=None, currency="INR",
            user_hash=f"hash-{rng.randint(1, 120)}", app_version="2.1.0",
        ))

    # Crashes concentrated in one fingerprint, which is what a real regression
    # looks like rather than uniform noise.
    for i in range(140):
        session.add(CrashReport(
            ts=NOW - timedelta(days=rng.randint(0, 6)), platform="android",
            kind="crash", session_id=f"sess-android-{rng.randint(1, 120)}-{i}",
            fingerprint="NullPointerException@TimetableFragment:412",
            exception_type="NullPointerException", message="Attempt to read from null array",
            stack_trace="at com.essential.timetable.TimetableFragment.onResume(TimetableFragment.java:412)",
            fatal=True, app_version="2.1.0", os_version="14",
            device_model="Pixel 7", foreground=True,
        ))

    for kind, n in (("root_detected", 12), ("emulator_detected", 30), ("failed_login", 8)):
        for _ in range(n):
            session.add(SecurityEvent(
                ts=NOW - timedelta(days=rng.randint(0, 29)), platform="android",
                kind=kind, ip_hash=f"{rng.randint(0, 2**31):032x}"[:32],
                user_hash=f"hash-{rng.randint(1, 120)}", app_version="2.1.0",
                blocked=False, detail={},
            ))

    session.commit()


def main() -> None:
    settings = get_settings()
    settings.telemetry_enabled = True
    settings.telemetry_pepper = "smoke-test-pepper"
    create_db_and_tables()

    with Session(engine) as session:
        print("seeding…")
        seed(session)
        print("rolling up…")
        summary = rollup_mod.rollup(session, lookback_hours=24 * 30, now=NOW)
        print(f"  {summary['rows_written']} hourly rows from "
              f"{summary['events_scanned']} events")

    from models import User
    with Session(engine) as session:
        admin = session.exec(select(User).where(User.role == "admin")).first()
        if admin is None:
            admin = User(email="smokeadmin@iiitdmj.ac.in", password_hash="x",
                         full_name="Smoke Admin", username="smokeadmin",
                         roll_number="23BCS111", is_email_verified=True, role="admin")
            session.add(admin)
            session.commit()
            session.refresh(admin)
        admin_id = admin.id

    headers = {"Authorization": f"Bearer {create_access_token(admin_id, 'smokeadmin')}"}

    with TestClient(app) as client:
        print("\n--- ingestion ---")
        r = client.post("/collect/events", json={"events": [
            {"event_name": "screen_view", "platform": "web", "session_id": "smoke-000001"},
            {"event_name": "not_real", "platform": "web", "session_id": "smoke-000001"},
        ]})
        print(f"POST /collect/events -> {r.status_code} {r.json()}")

        print("\n--- subsections ---")
        subs = client.get("/monitoring/subsections", headers=headers).json()["subsections"]
        for s in subs:
            print(f"  {s['id']:<16} {s['platform']:<8} {s['group']} / {s['title']}")

        print("\n--- overview (web, 30d) ---")
        ov = client.get("/monitoring/overview?days=30&platform=web", headers=headers).json()
        a = ov["activity"]
        print(f"  active users      {a['active_users']} (prev {a['active_users_prev']})")
        print(f"  sessions          {a['sessions']} (prev {a['sessions_prev']})")
        print(f"  events (rollup)   {a['events']}")
        print(f"  new / returning   {a['new_vs_returning']}")
        print("  retention day1-3  " + ", ".join(
            f"d{k}={v['pct']}%(n={v['cohort']})" for k, v in list(a['retention'].items())[:3]))
        print("  top countries     " + ", ".join(
            f"{c['value']}={c['events']}" for c in a['countries'][:4]))
        print(f"  freshness         rollup={ov['data_freshness']['latest_rollup_hour']} "
              f"lag={ov['data_freshness']['rollup_lag_minutes']}min")

        print("\n--- overview (android, 30d) ---")
        ova = client.get("/monitoring/overview?days=30&platform=android", headers=headers).json()
        print(f"  crash-free        {ova['crashes']['android']['crash_free_pct']}% "
              f"({ova['crashes']['android']['crashed_sessions']}/{ova['crashes']['android']['sessions']})")
        print(f"  top cluster       {ova['crashes']['clusters'][0]}")
        print(f"  revenue           {ova['revenue']}")
        print(f"  arpu              {ova['arpu']}")
        print(f"  ads               {ova['ads']}")
        print(f"  security counts   {ova['security']['counts']}")

        print("\n--- health ---")
        h = client.get("/monitoring/health?days=7&platform=web", headers=headers).json()
        print(f"  registry series   {h['http']['registry_series']}")
        print(f"  route series      {len(h['http']['requests_by_route'])}")
        print(f"  active users      {h['db']['active_users']}")

        print("\n--- feedback ---")
        fb = client.get("/monitoring/feedback?days=3650", headers=headers).json()
        print(f"  total             {fb['total']} (sampled {fb['sampled']}, truncated {fb['truncated']})")
        print(f"  sentiment         {fb['sentiment']}")
        print("  topics            " + ", ".join(f"{t['topic']}={t['count']}" for t in fb['topics'][:5]))

        print("\n--- monetisation ---")
        mo = client.get("/monitoring/monetisation?days=30", headers=headers).json()
        print(f"  revenue           {mo['revenue']}")
        print(f"  ads               {mo['ads']}")
        print(f"  verify enabled    {mo['store_verification_enabled']}")
        print(f"  note              {mo['note']}")

        print("\n--- history (no scans yet) ---")
        hist = client.get("/monitoring/history", headers=headers).json()
        print(f"  scans={len(hist['scans'])} incidents={len(hist['incidents'])} "
              f"tool_calls={len(hist['tool_calls'])}")

        print("\n--- rollup idempotency ---")
        # Compare the *total*, not the row count: the collector POST above adds
        # one event in a fresh hour bucket, so the row count legitimately grows
        # while the total for unchanged buckets must not.
        with Session(engine) as s:
            rollup_mod.rollup(s, lookback_hours=24 * 30, now=NOW)
            total_1 = s.exec(select(func.sum(EventHourly.n))).first()
            rollup_mod.rollup(s, lookback_hours=24 * 30, now=NOW)
            total_2 = s.exec(select(func.sum(EventHourly.n))).first()
            rows_1 = len(s.exec(select(EventHourly)).all())
            rollup_mod.rollup(s, lookback_hours=24 * 30, now=NOW)
            total_3 = s.exec(select(func.sum(EventHourly.n))).first()
        print(f"  event totals across 3 consecutive runs: {total_1} {total_2} {total_3}")
        print(f"  {'PASS' if total_1 == total_2 == total_3 else 'FAIL'} - totals must be identical")
        print(f"  hourly rows: {rows_1}")

        print("\n--- metrics ---")
        m = client.get("/metrics")
        lines = [line for line in m.text.splitlines() if line.startswith("campuspilot_")]
        names = sorted({line.split("{")[0].split(" ")[0] for line in lines})
        print(f"  {len(lines)} samples across {len(names)} series")
        for n in names:
            print(f"    {n}")

        print("\n--- authz ---")
        print(f"  anon overview     {client.get('/monitoring/overview').status_code}")
        print(f"  feedback resp     {client.get('/feedback/responses', headers=headers).status_code}")


if __name__ == "__main__":
    main()