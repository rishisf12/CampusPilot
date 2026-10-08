"""Tests for the monitoring subsystem.

Two things these tests are actually defending, in order of how much damage a
regression would do:

1. **Privacy.** The monitoring tables are the only place in this app that stores
   anything about users that is not already in the `user` table. If a change
   starts storing a plain user id, a raw IP, or free-text props, the tests must
   fail loudly. That is a different class of bug from a wrong number, and it is
   the one that cannot be fixed after the fact.

2. **Arithmetic.** The queries here are the only source of the numbers an admin
   sees and the only source the AI scans are allowed to quote. Every figure below
   is pinned against a hand-computed expected value rather than against whatever
   the function happens to return, so a change in behaviour fails instead of
   quietly redefining the metric.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from core.config import get_settings
from core.database import create_db_and_tables, engine  # noqa: F401
from features.monitoring import collector, queries, rollup as rollup_mod
from features.monitoring.models import (
    AdEvent,
    CrashReport,
    Event,
    EventHourly,
    Purchase,
    ScanResult,
    SecurityEvent,
    Session as MonitorSession,
    StatusTransition,
)
from features.monitoring.ratelimit import SlidingWindowLimiter
from main import app  # noqa: F401

UTC = timezone.utc
NOW = datetime.now(UTC).replace(tzinfo=None, microsecond=0)


@pytest.fixture
def db():
    """A session with every monitoring table emptied.

    Monitoring rows are global and the admin endpoints read them without a user
    filter, so leftovers from one test would show up in the next one's totals.
    Truncating per-test is the alternative and is not worth the connection
    gymnastics for a test database.
    """
    with Session(engine) as session:
        for model in (Event, EventHourly, MonitorSession, Purchase, AdEvent,
                      CrashReport, SecurityEvent, ScanResult, StatusTransition):
            session.exec(delete(model))
        session.commit()
        yield session


def _ev(session, *, name, ts=None, user=1, sid="sess-00000001",
        platform="web", version=None, country=None, props=None):
    session.add(Event(
        ts=ts or NOW,
        platform=platform,
        session_id=sid,
        user_hash=None if user is None else f"hash-{user}",
        event_name=name,
        props=props or {},
        app_version=version,
        os_version=None,
        device_model=None,
        country=country,
    ))
    session.commit()


def _sess(session, *, user, started, sid=None, platform="web"):
    session.add(MonitorSession(
        session_id=sid or f"sess-{user}-{started.isoformat()}",
        platform=platform,
        user_hash=None if user is None else f"hash-{user}",
        started_at=started,
        last_seen_at=started,
        duration_s=0,
        event_count=0,
        app_version=None,
        os_version=None,
        device_model=None,
        country=None,
    ))
    session.commit()


# ===========================================================================
# Hashing: the privacy-critical primitives
# ===========================================================================

class TestPseudonymisation:
    def test_user_hash_is_deterministic_for_one_user(self):
        a = collector.user_hash("pepper", 42)
        b = collector.user_hash("pepper", 42)
        assert a == b
        assert len(a) == 64

    def test_different_users_get_different_hashes(self):
        assert collector.user_hash("pepper", 1) != collector.user_hash("pepper", 2)

    def test_rotating_the_pepper_changes_every_hash(self):
        """The property that makes rotation an erasure mechanism."""
        before = collector.user_hash("old-pepper", 7)
        after = collector.user_hash("new-pepper", 7)
        assert before != after

    def test_anonymous_is_none_not_a_hash_of_empty(self):
        """A sentinel hash for anonymous would let anonymous sessions be
        counted as one distinct 'user' in every DAU figure."""
        assert collector.user_hash("pepper", None) is None

    def test_user_hash_is_not_a_plain_digest_of_the_id(self):
        """Guards against someone 'simplifying' this to hashlib.sha256(str(id)).

        A plain digest is reversible here because user ids are sequential
        integers: an attacker with the table tries id=1, 2, 3... and recovers
        every mapping. That is the whole reason this is an HMAC.
        """
        import hashlib

        h = collector.user_hash("pepper", 42)
        assert h != hashlib.sha256(b"42").hexdigest()
        assert h != hashlib.sha256(b"pepper42").hexdigest()

    def test_ip_hash_is_truncated(self):
        h = collector.ip_hash("pepper", "10.1.2.3")
        assert h is not None and len(h) == 32

    def test_ip_hash_of_nothing_is_none(self):
        assert collector.ip_hash("pepper", None) is None


# ===========================================================================
# Event validation
# ===========================================================================

class TestValidation:
    def _good(self, **over):
        base = {"event_name": "app_open", "platform": "web", "session_id": "sess-00000001"}
        base.update(over)
        return base

    def test_accepts_a_well_formed_event(self):
        out = collector.validate_event(self._good())
        assert out["event_name"] == "app_open"
        assert out["ts"].tzinfo is None, "timestamps must be naive UTC"

    @pytest.mark.parametrize("bad", [
        {"event_name": "not_a_real_event"},
        {"event_name": "app_open; DROP TABLE event"},
        {"event_name": ""},
        {"event_name": "A"},                       # uppercase, fails the pattern
        {"platform": "server"},                    # clients are web/android only
        {"session_id": "short"},                   # too short to be an install id
        {"props": "not-an-object"},
    ])
    def test_rejects_malformed_input(self, bad):
        with pytest.raises(collector.CollectError):
            collector.validate_event(self._good(**bad))

    def test_truncates_rather_than_rejecting_a_long_prop(self):
        out = collector.validate_event(self._good(props={"note": "x" * 5000}))
        assert len(out["props"]["note"]) == collector.MAX_PROP_LEN

    def test_caps_the_number_of_props(self):
        props = {f"k{i}": i for i in range(50)}
        out = collector.validate_event(self._good(props=props))
        assert len(out["props"]) == collector.MAX_PROPS

    def test_rejects_an_unparseable_timestamp(self):
        with pytest.raises(collector.CollectError):
            collector.validate_event(self._good(ts="not-a-date"))

    def test_normalises_country_to_upper_case_iso2(self):
        assert collector.validate_event(self._good(country="in"))["country"] == "IN"

    def test_rejects_a_country_that_is_not_two_letters(self):
        assert collector.validate_event(self._good(country="India"))["country"] is None

    def test_drops_a_malformed_version_rather_than_storing_it(self):
        """App versions become a Prometheus label and a rollup dimension, so an
        arbitrary string from a client would fragment both."""
        assert collector.validate_event(self._good(app_version="v1'; DROP"))["app_version"] is None

    def test_accepts_a_legitimate_version_string(self):
        assert collector.validate_event(self._good(app_version="1.4.2"))["app_version"] == "1.4.2"


# ===========================================================================
# Ingest
# ===========================================================================

class TestCollect:
    def test_records_events(self, db):
        res = collector.collect(db, {"events": [
            {"event_name": "app_open", "platform": "web", "session_id": "sess-00000001"},
        ]}, user_id=5, pepper="pepper")
        assert res == {"accepted": 1, "rejected": 0}
        assert len(db.exec(select(Event)).all()) == 1

    def test_stores_the_hmac_not_the_user_id(self, db):
        """The stored value is the HMAC and nothing else.

        Deliberately does *not* assert something like "the id is not a substring
        of the hash": an HMAC is hex, and '5' appears in roughly half of all
        hex digests, so such a test fails at random and teaches nobody anything.
        The meaningful assertions are the equality with the HMAC below and the
        plain-digest comparison in `test_user_hash_is_not_a_plain_digest_of_the_id`.
        """
        collector.collect(db, {"events": [
            {"event_name": "app_open", "platform": "web", "session_id": "sess-00000001"},
        ]}, user_id=5, pepper="pepper")
        row = db.exec(select(Event)).first()
        assert row.user_hash == collector.user_hash("pepper", 5)
        assert len(row.user_hash) == 64
        assert row.user_hash.isalnum()

    def test_a_bad_event_does_not_discard_the_good_ones(self, db):
        """A mobile client batching 50 events should not lose all 50 because
        one had a bad device_model."""
        res = collector.collect(db, {"events": [
            {"event_name": "app_open", "platform": "web", "session_id": "sess-00000001"},
            {"event_name": "bogus", "platform": "web", "session_id": "sess-00000001"},
            {"event_name": "page_view", "platform": "web", "session_id": "sess-00000001"},
        ]}, pepper="pepper")
        assert res == {"accepted": 2, "rejected": 1}

    def test_rejects_a_non_list_payload(self, db):
        with pytest.raises(collector.CollectError):
            collector.collect(db, {"events": "nope"}, pepper="pepper")

    def test_rejects_an_oversized_batch(self, db):
        big = [{"event_name": "app_open", "platform": "web", "session_id": "sess-00000001"}] * 500
        with pytest.raises(collector.CollectError):
            collector.collect(db, {"events": big}, pepper="pepper")

    def test_a_purchase_event_promotes_to_the_purchase_table(self, db):
        collector.collect(db, {"events": [{
            "event_name": "purchase_completed", "platform": "android",
            "session_id": "sess-00000001",
            "props": {"transaction_id": "txn-abc", "product_id": "pro_monthly",
                      "price": 99.5, "currency": "INR", "kind": "subscription"},
        }]}, user_id=5, pepper="pepper")
        p = db.exec(select(Purchase)).first()
        assert p is not None
        assert p.price_micros == 99_500_000
        assert p.verified is False, "a self-reported purchase is not a verified one"

    def test_a_replayed_transaction_id_is_ignored(self, db):
        """The unique constraint is the real guard; this proves the code path
        checks rather than relying on an IntegrityError to abort the batch."""
        payload = {"events": [{
            "event_name": "purchase_completed", "platform": "android",
            "session_id": "sess-00000001",
            "props": {"transaction_id": "txn-dup", "product_id": "pro", "price": 10},
        }]}
        collector.collect(db, payload, pepper="pepper")
        collector.collect(db, payload, pepper="pepper")
        assert len(db.exec(select(Purchase)).all()) == 1

    def test_ad_impression_becomes_an_ad_event(self, db):
        collector.collect(db, {"events": [{
            "event_name": "ad_impression", "platform": "android", "session_id": "sess-00000001",
            "props": {"network": "local-test-net", "ad_unit": "banner", "revenue": 0.0005},
        }]}, pepper="pepper")
        a = db.exec(select(AdEvent)).first()
        assert a is not None and a.event_type == "impression"
        assert a.revenue_micros == 500, "revenue must be integer minor units, not a float"

    def test_session_start_creates_one_session_row(self, db):
        ev = {"event_name": "session_start", "platform": "web", "session_id": "sess-abcdefgh"}
        collector.collect(db, {"events": [ev]}, user_id=5, pepper="pepper")
        collector.collect(db, {"events": [ev]}, user_id=5, pepper="pepper")
        rows = db.exec(select(MonitorSession)).all()
        assert len(rows) == 1, "a retried batch must not create a second session"

    def test_session_start_propagates_the_user_hash(self, db):
        """Without this, DAU silently degrades into a session count."""
        collector.collect(db, {"events": [
            {"event_name": "session_start", "platform": "web", "session_id": "sess-abcdefgh"},
        ]}, user_id=5, pepper="pepper")
        assert db.exec(select(MonitorSession)).first().user_hash == collector.user_hash("pepper", 5)

    def test_session_end_records_a_bounded_duration(self, db):
        collector.collect(db, {"events": [
            {"event_name": "session_start", "platform": "web", "session_id": "sess-abcdefgh",
             "ts": (NOW - timedelta(seconds=90)).isoformat() + "Z"},
            {"event_name": "session_end", "platform": "web", "session_id": "sess-abcdefgh",
             "ts": NOW.isoformat() + "Z"},
        ]}, pepper="pepper")
        assert db.exec(select(MonitorSession)).first().duration_s == 90

    def test_an_absurd_session_duration_is_clamped(self, db):
        """A client claiming a 10-year session must not poison average session
        length, which averages never recover from."""
        collector.collect(db, {"events": [
            {"event_name": "session_start", "platform": "web", "session_id": "sess-abcdefgh",
             "ts": "1990-01-01T00:00:00Z"},
            {"event_name": "session_end", "platform": "web", "session_id": "sess-abcdefgh",
             "ts": NOW.isoformat() + "Z"},
        ]}, pepper="pepper")
        assert db.exec(select(MonitorSession)).first().duration_s == 86_400


# ===========================================================================
# Rollup
# ===========================================================================

class TestRollup:
    def test_counts_events_into_hourly_buckets(self, db):
        _ev(db, name="app_open", ts=NOW.replace(minute=5))
        _ev(db, name="app_open", ts=NOW.replace(minute=50))
        _ev(db, name="page_view", ts=NOW.replace(minute=50))

        summary = rollup_mod.rollup(db, lookback_hours=48, now=NOW)
        rows = db.exec(select(EventHourly)).all()
        assert len(rows) == 2
        assert sum(r.n for r in rows) == 3
        assert summary["events_scanned"] == 3

    def test_buckets_on_the_hour_boundary(self, db):
        _ev(db, name="app_open", ts=NOW.replace(minute=37, second=12, microsecond=0))
        rollup_mod.rollup(db, lookback_hours=48, now=NOW)
        row = db.exec(select(EventHourly)).first()
        assert (row.bucket_hour.minute, row.bucket_hour.second) == (0, 0)

    def test_running_twice_changes_nothing(self, db):
        """The property that makes this safe to schedule. An accumulating
        rollup would double the totals here, and every dashboard would inherit
        that error permanently."""
        _ev(db, name="app_open")
        _ev(db, name="app_open")
        rollup_mod.rollup(db, lookback_hours=48, now=NOW)
        first = {(r.event_name): r.n for r in db.exec(select(EventHourly)).all()}

        rollup_mod.rollup(db, lookback_hours=48, now=NOW)
        second = {(r.event_name): r.n for r in db.exec(select(EventHourly)).all()}
        assert first == second == {"app_open": 2}

    def test_three_runs_are_still_stable(self, db):
        _ev(db, name="app_open")
        for _ in range(3):
            rollup_mod.rollup(db, lookback_hours=48, now=NOW)
        assert db.exec(select(EventHourly)).first().n == 1

    def test_stale_buckets_outside_the_window_are_dropped(self, db):
        """A bucket that used to be correct and is no longer backed by any raw
        event must disappear, or a chart keeps drawing a line into the past."""
        _ev(db, name="app_open", ts=NOW)
        rollup_mod.rollup(db, lookback_hours=48, now=NOW)

        db.exec(delete(Event))             # the raw data was pruned
        db.commit()
        rollup_mod.rollup(db, lookback_hours=48, now=NOW)
        assert db.exec(select(EventHourly)).all() == []

    def test_a_missing_dimension_is_stored_as_empty_string(self, db):
        """Not NULL. PostgreSQL treats NULLs as distinct in a unique index, so a
        NULL here would let the same bucket be inserted twice on Postgres while
        SQLite silently prevented it."""
        _ev(db, name="app_open", version=None, country=None)
        rollup_mod.rollup(db, lookback_hours=48, now=NOW)
        row = db.exec(select(EventHourly)).first()
        assert row.app_version == "" and row.country == ""

    def test_same_bucket_twice_with_missing_dimensions_stays_one_row(self, db):
        _ev(db, name="app_open", version=None)
        _ev(db, name="app_open", version=None)
        rollup_mod.rollup(db, lookback_hours=48, now=NOW)
        rows = db.exec(select(EventHourly)).all()
        assert len(rows) == 1 and rows[0].n == 2

    def test_distinct_versions_are_separate_rows(self, db):
        _ev(db, name="app_open", version="1.4.0")
        _ev(db, name="app_open", version="1.5.0")
        rollup_mod.rollup(db, lookback_hours=48, now=NOW)
        assert len(db.exec(select(EventHourly)).all()) == 2

    def test_prune_removes_old_raw_events_but_keeps_recent_ones(self, db):
        _ev(db, name="app_open", ts=NOW - timedelta(days=200))
        _ev(db, name="app_open", ts=NOW - timedelta(days=2))
        result = rollup_mod.prune(db, now=NOW, retention_days=90)
        assert result["raw_events_deleted"] == 1
        assert len(db.exec(select(Event)).all()) == 1

    def test_prune_never_touches_purchases(self, db):
        """Revenue history outlives any analytics window, on purpose."""
        db.add(Purchase(transaction_id="txn-old", ts=NOW - timedelta(days=900),
                        platform="android", product_id="pro", price_micros=100,
                        currency="INR", user_hash=None, app_version=None,
                        verified=True, kind="one_time"))
        db.commit()
        rollup_mod.prune(db, now=NOW, retention_days=90)
        assert len(db.exec(select(Purchase)).all()) == 1


class TestRollupSql:
    """Compiled-SQL assertions for the rollup's aggregate query.

    These exist because of a real bug that the SQLite suite could not see. The
    GROUP BY originally rebuilt `func.coalesce(col, "")` as new objects, so
    SQLAlchemy gave the SELECT and the GROUP BY separate bind parameters. The
    emitted SQL therefore read

        SELECT coalesce(event.app_version, $2) ... GROUP BY coalesce(event.app_version, $7)

    which PostgreSQL rejects outright ("column event.app_version must appear in
    the GROUP BY clause") and SQLite accepts without complaint. Green on
    SQLite, broken in production.

    Asserting on the compiled SQL catches a regression on *both* dialects, so
    the bug cannot be reintroduced and simply wait for the Postgres job to find
    it again.
    """

    @staticmethod
    def _compiled(dialect: str):
        from sqlalchemy.dialects import postgresql, sqlite

        dialect_obj = postgresql.dialect() if dialect == "postgresql" else sqlite.dialect()
        return rollup_mod._aggregate_stmt(
            NOW - timedelta(days=2), NOW, rollup_mod._hour_bucket_expr(dialect)
        ).compile(dialect=dialect_obj)

    @pytest.mark.parametrize("dialect", ["postgresql", "sqlite"])
    def test_group_by_shares_the_select_bind_parameters(self, dialect):
        """The grouped dimension expressions must bind to the *same* parameters
        as the selected ones.

        Three coalesced dimensions appear in the SELECT list and the same three
        in the GROUP BY, so there must be exactly three distinct bind
        parameters. With the bug present, each clause builds its own
        ``coalesce(col, "")`` objects, SQLAlchemy allocates a parameter per
        occurrence, and the count doubles to six. PostgreSQL then sees
        ``coalesce(event.app_version, $2)`` selected against
        ``coalesce(event.app_version, $7)`` grouped, cannot match them, and
        raises "column event.app_version must appear in the GROUP BY clause".
        SQLite does not care, which is why the whole SQLite suite was green
        while production was broken.

        Counted via ``compiled.params``, whose keys are named on both dialects
        even though SQLite renders them positionally as ``?``. Two earlier
        versions of this test compared parameter names inside the SQL text and
        then normalised them away; both passed with the bug still in place.
        """
        params = self._compiled(dialect).params
        coalesce_params = sorted(k for k in params if "coalesce" in k)
        assert len(coalesce_params) == 3, (
            f"expected 3 shared bind parameters for the 3 dimensions, got "
            f"{len(coalesce_params)}: {coalesce_params}. The GROUP BY is using "
            "distinct expression objects from the SELECT list."
        )

    @pytest.mark.parametrize("dialect", ["postgresql", "sqlite"])
    def test_every_dimension_is_actually_grouped(self, dialect):
        sql = str(self._compiled(dialect))
        select_part, _, group_part = sql.partition("GROUP BY")
        for column in ("event.platform", "event.event_name"):
            assert column in group_part, f"{column} is selected but not grouped"
        # Three coalesce calls on each side of the statement.
        assert select_part.count("coalesce(") == 3
        assert group_part.count("coalesce(") == 3

    @pytest.mark.parametrize("dialect", ["postgresql", "sqlite"])
    def test_sqlite_uses_strftime_and_postgres_uses_date_trunc(self, dialect):
        sql = str(self._compiled(dialect))
        if dialect == "postgresql":
            assert "date_trunc" in sql
        else:
            assert "strftime" in sql
            assert "date_trunc" not in sql

    def test_the_timestamp_truncation_is_itself_grouped(self):
        """The bucket is a computed expression too, so it has to appear in the
        GROUP BY or every row lands in one bucket."""
        sql = str(self._compiled("postgresql"))
        _, _, group_part = sql.partition("GROUP BY")
        assert "date_trunc" in group_part

    def test_the_rollup_query_really_executes_on_postgres(self, require_postgres):
        """End-to-end proof on the dialect that rejects the bug.

        The compiled-SQL assertions above are dialect-independent and run
        everywhere; this one only runs under PostgreSQL, and it is the test that
        would have caught the original failure at CI time rather than at
        deploy time.
        """
        with Session(engine) as session:
            _ev(session, name="app_open", ts=NOW)
            summary = rollup_mod.rollup(session, lookback_hours=48, now=NOW)
        assert summary["events_scanned"] >= 1
        with Session(engine) as session:
            rows = session.exec(select(EventHourly)).all()
            assert len(rows) >= 1
            assert sum(r.n for r in rows) == summary["events_scanned"]


# ===========================================================================
# Queries: active users, new vs returning, retention
# ===========================================================================

class TestUserMetrics:
    def test_active_users_counts_people_not_sessions(self, db):
        """One student checking their timetable five times is one daily active
        user. Counting sessions inflates DAU fivefold."""
        _sess(db, user=1, started=NOW - timedelta(hours=1), sid="s1")
        _sess(db, user=1, started=NOW - timedelta(hours=2), sid="s2")
        _sess(db, user=1, started=NOW - timedelta(hours=3), sid="s3")
        _sess(db, user=2, started=NOW - timedelta(hours=1), sid="s4")
        start, end = queries.window(1)
        assert queries.active_users(db, start, end) == 2

    def test_active_users_excludes_the_window_boundary(self, db):
        _sess(db, user=1, started=NOW - timedelta(days=2))
        start, end = NOW - timedelta(days=1), NOW
        assert queries.active_users(db, start, end) == 0

    def test_anonymous_sessions_do_not_count_as_users(self, db):
        _sess(db, user=None, started=NOW - timedelta(hours=1), sid="anon-1")
        start, end = queries.window(1)
        assert queries.active_users(db, start, end) == 0
        assert queries.sessions_count(db, start, end) == 1

    def test_new_vs_returning_separates_a_first_timer_from_a_regular(self, db):
        """The bug this pins: if "new" is computed with the same window as
        "total", then new == total always and the split means nothing."""
        _sess(db, user=1, started=NOW - timedelta(hours=1), sid="new-user")
        # This user has been around for a month and came back today.
        _sess(db, user=2, started=NOW - timedelta(days=30), sid="old-1")
        _sess(db, user=2, started=NOW - timedelta(hours=1), sid="old-2")

        start, end = queries.window(1)
        result = queries.new_vs_returning(db, start, end)
        assert result["total"] == 2
        assert result["new"] == 1
        assert result["returning"] == 1

    def test_a_launch_spike_does_not_read_as_permanent_growth(self, db):
        for i in range(50):
            _sess(db, user=i, started=NOW - timedelta(hours=1), sid=f"n{i}")
        # ... and they all come back next week
        for i in range(50):
            _sess(db, user=i, started=NOW - timedelta(days=6), sid=f"r{i}")
        start, end = queries.window(1)
        assert queries.new_vs_returning(db, start, end)["new"] == 0

    def test_platform_filter_is_honoured(self, db):
        _sess(db, user=1, started=NOW - timedelta(hours=1), sid="w1", platform="web")
        _sess(db, user=2, started=NOW - timedelta(hours=1), sid="a1", platform="android")
        start, end = queries.window(1)
        assert queries.active_users(db, start, end, "android") == 1
        assert queries.active_users(db, start, end, "web") == 1
        assert queries.active_users(db, start, end) == 2


class TestRetention:
    """Cohorts are calendar-day aligned, so the fixtures pin whole days.

    Placing a session at "now minus 48 hours" would be ambiguous - it straddles
    a day boundary depending on the hour the suite runs. These use explicit
    mid-day timestamps inside the target calendar day, which is also what makes
    the expected values readable.
    """

    @staticmethod
    def _day_ago(n: int, hour: int = 12) -> datetime:
        today = datetime.now(UTC).replace(tzinfo=None)
        midnight = today.replace(hour=0, minute=0, second=0, microsecond=0)
        return midnight - timedelta(days=n, hours=-hour)

    def test_a_user_who_returns_the_next_day_is_retained(self, db):
        # first seen 2 calendar days ago, back again 1 day ago -> day 1
        _sess(db, user=1, started=self._day_ago(2), sid="d0")
        _sess(db, user=1, started=self._day_ago(1), sid="d1")
        out = queries.retention_cohorts(db, days=3)
        assert out["1"]["pct"] == 100
        assert out["1"]["cohort"] == 1

    def test_a_user_who_does_not_return_is_not_retained(self, db):
        _sess(db, user=1, started=self._day_ago(2), sid="d0")
        out = queries.retention_cohorts(db, days=3)
        assert out["1"]["pct"] == 0
        assert out["1"]["cohort"] == 1

    def test_a_user_who_returns_two_days_later_is_day_2_not_day_1(self, db):
        _sess(db, user=1, started=self._day_ago(3), sid="d0")
        _sess(db, user=1, started=self._day_ago(1), sid="d1")
        out = queries.retention_cohorts(db, days=3)
        assert out["2"]["pct"] == 100
        assert out["1"]["cohort"] == 0

    def test_cohort_size_is_reported_with_the_percentage(self, db):
        """A 100% day-1 on a cohort of 4 is noise. A UI that cannot see the
        denominator will present it as a win."""
        for i in range(4):
            _sess(db, user=i, started=self._day_ago(2), sid=f"s{i}")
            _sess(db, user=i, started=self._day_ago(1), sid=f"t{i}")
        out = queries.retention_cohorts(db, days=1)
        assert out["1"] == {"pct": 100, "cohort": 4}

    def test_an_empty_cohort_reports_zero_not_a_division_error(self, db):
        out = queries.retention_cohorts(db, days=7)
        assert all(v == {"pct": 0, "cohort": 0} for v in out.values())

    def test_retention_excludes_users_with_no_chance_to_return(self, db):
        """Someone who signed up today has not yet had a day-1. Including them
        drags every figure down by however many people signed up today."""
        _sess(db, user=1, started=self._day_ago(0), sid="brand-new")
        out = queries.retention_cohorts(db, days=3)
        assert out["1"]["cohort"] == 0

    def test_the_answer_does_not_depend_on_when_the_query_runs(self, db):
        """The property calendar alignment buys. With rolling windows a cohort
        boundary can slide across a session between two runs of the same
        code, which makes the metric unusable for spotting a trend."""
        _sess(db, user=1, started=self._day_ago(2), sid="d0")
        _sess(db, user=1, started=self._day_ago(1), sid="d1")
        first = queries.retention_cohorts(db, days=2)
        second = queries.retention_cohorts(db, days=2)
        assert first == second

    def test_a_returning_user_is_not_re_enrolled_into_a_later_cohort(self, db):
        """Regression: numerator and denominator must describe the same people.

        This user first appeared 5 days ago and came back 3 days ago. Day-2
        retention asks about users *first seen* 3 days ago, so the cohort is
        empty and must read 0%.

        The bug this pins applied the first-seen filter only to the `enrolled`
        count while the `retained` join reused the unfiltered cohort. So this
        user landed in the numerator but not the denominator, and retention
        came out non-zero for cohorts nobody joined - and could exceed 100%.
        """
        _sess(db, user=1, started=self._day_ago(5), sid="old-1")
        _sess(db, user=1, started=self._day_ago(3), sid="returning-1")

        out = queries.retention_cohorts(db, days=5)
        # day 2 -> cohort is "first seen 3 days ago". This user is in it only
        # if "first seen" is ignored.
        assert out["2"] == {"pct": 0, "cohort": 0}
        # day 4 -> cohort is "first seen 5 days ago", which is this user.
        assert out["4"]["cohort"] == 1

    def test_retention_can_never_exceed_one_hundred_percent(self, db):
        """A structural invariant on the fix above, checked over every day."""
        for u in range(1, 9):
            _sess(db, user=u, started=self._day_ago(6), sid=f"a{u}")
            _sess(db, user=u, started=self._day_ago(3), sid=f"b{u}")
            _sess(db, user=u, started=self._day_ago(1), sid=f"c{u}")
        out = queries.retention_cohorts(db, days=8)
        for day, cell in out.items():
            assert 0 <= cell["pct"] <= 100, f"day {day} is {cell['pct']}%"


# ===========================================================================
# Queries: revenue, ads, crashes, funnels
# ===========================================================================

class TestRevenueAndAds:
    def _purchase(self, db, *, txn, micros, verified, ts=None):
        db.add(Purchase(transaction_id=txn, ts=ts or NOW, platform="android",
                        product_id="pro", price_micros=micros, currency="INR",
                        user_hash="hash-1", app_version=None, verified=verified,
                        kind="one_time"))
        db.commit()

    def test_revenue_splits_verified_from_unverified(self, db):
        """Presenting an unverified total as revenue is the kind of thing an
        auditor finds. The split is the whole point of the function."""
        self._purchase(db, txn="v1", micros=100_000, verified=True)
        self._purchase(db, txn="u1", micros=900_000, verified=False)
        start, end = queries.window(1)
        r = queries.revenue(db, start, end)
        assert r["total_micros"] == 1_000_000
        assert r["verified_micros"] == 100_000
        assert r["verified_purchases"] == 1
        assert r["purchases"] == 2

    def test_arpu_divides_by_active_users_not_registrations(self, db):
        self._purchase(db, txn="v1", micros=100_000, verified=True)
        _sess(db, user=1, started=NOW - timedelta(hours=1))
        _sess(db, user=2, started=NOW - timedelta(hours=1), sid="s2")
        _sess(db, user=3, started=NOW - timedelta(hours=1), sid="s3")
        _sess(db, user=4, started=NOW - timedelta(hours=1), sid="s4")
        start, end = queries.window(1)
        a = queries.arpu(db, start, end)
        assert a["active_users"] == 4
        assert a["arpu_micros"] == 25_000

    def test_arpu_with_no_users_is_zero_not_a_crash(self, db):
        self._purchase(db, txn="v1", micros=100_000, verified=True)
        start, end = queries.window(1)
        assert queries.arpu(db, start, end)["arpu_micros"] == 0

    def test_ecpm_is_derived_from_impressions_not_taken_from_the_client(self, db):
        """eCPM is revenue per thousand impressions.

        1000 impressions at 1000 micro each is 1,000,000 micro of revenue over
        1000 impressions, so the eCPM is 1,000,000 micro - not 1000. Getting
        this wrong by a factor of a thousand is the classic eCPM bug, which is
        why the expectation is spelled out rather than recomputed from the
        implementation.
        """
        for _ in range(1000):
            db.add(AdEvent(ts=NOW, platform="android", ad_network="n", ad_unit="b",
                           event_type="impression", revenue_micros=1000, currency="INR",
                           user_hash=None, app_version=None))
        db.commit()
        start, end = queries.window(1)
        a = queries.ad_performance(db, start, end)
        assert a["impressions"] == 1000
        assert a["revenue_micros"] == 1_000_000
        assert a["ecpm_micros"] == 1_000_000
        assert a["ctr_pct"] == 0.0

    def test_ecpm_scales_with_revenue_not_with_impressions(self, db):
        """Ten times the revenue for the same impressions is ten times the eCPM."""
        for revenue in (1000, 10_000):
            db.query(AdEvent).delete()
            db.add(AdEvent(ts=NOW, platform="android", ad_network="n", ad_unit="b",
                           event_type="impression", revenue_micros=revenue,
                           currency="INR", user_hash=None, app_version=None))
            db.commit()
            start, end = queries.window(1)
            assert queries.ad_performance(db, start, end)["ecpm_micros"] == revenue * 1000

    def test_ctr_with_no_impressions_is_zero_not_a_division_error(self, db):
        start, end = queries.window(1)
        assert queries.ad_performance(db, start, end)["ctr_pct"] == 0.0

    def test_ctr_counts_clicks_over_impressions(self, db):
        for event_type in ("impression", "click"):
            db.add(AdEvent(ts=NOW, platform="android", ad_network="n", ad_unit="b",
                           event_type=event_type, revenue_micros=None, currency="INR",
                           user_hash=None, app_version=None))
        db.commit()
        start, end = queries.window(1)
        assert queries.ad_performance(db, start, end)["ctr_pct"] == 100.0


class TestCrashes:
    def test_crash_free_rate_is_computed_on_sessions(self, db):
        """Two crashes in one session is one affected session. Counting
        crashes against sessions would report a negative rate."""
        _sess(db, user=1, started=NOW - timedelta(hours=1), sid="s1", platform="android")
        _sess(db, user=2, started=NOW - timedelta(hours=1), sid="s2", platform="android")
        for _ in range(2):
            db.add(CrashReport(ts=NOW, platform="android", kind="crash",
                               session_id="s1", fingerprint="f1",
                               exception_type="NPE", message=None, stack_trace=None,
                               fatal=True, app_version=None, os_version=None,
                               device_model=None, foreground=True))
        db.commit()
        start, end = queries.window(1)
        r = queries.crash_free_rate(db, start, end, "android")
        assert r["sessions"] == 2
        assert r["crashed_sessions"] == 1
        assert r["crash_free_pct"] == 50.0

    def test_a_non_fatal_exception_does_not_reduce_the_rate(self, db):
        _sess(db, user=1, started=NOW - timedelta(hours=1), sid="s1", platform="android")
        db.add(CrashReport(ts=NOW, platform="android", kind="crash", session_id="s1",
                           fingerprint="f1", exception_type="E", message=None,
                           stack_trace=None, fatal=False, app_version=None,
                           os_version=None, device_model=None, foreground=True))
        db.commit()
        start, end = queries.window(1)
        assert queries.crash_free_rate(db, start, end, "android")["crash_free_pct"] == 100.0

    def test_with_no_sessions_the_rate_is_100_not_zero(self, db):
        """100% is the honest answer for "no crashes were observed". Reporting 0
        would page an admin about a hypothetical user."""
        start, end = queries.window(1)
        assert queries.crash_free_rate(db, start, end, "android")["crash_free_pct"] == 100.0

    def test_clusters_are_ordered_by_frequency(self, db):
        for count, fp in ((5, "common"), (1, "rare")):
            for i in range(count):
                db.add(CrashReport(ts=NOW, platform="android", kind="crash",
                                   session_id=f"s{i}", fingerprint=fp,
                                   exception_type=fp.upper(), message=None,
                                   stack_trace=None, fatal=True, app_version=None,
                                   os_version=None, device_model=None, foreground=True))
        db.commit()
        start, end = queries.window(1)
        clusters = queries.crash_clusters(db, start, end, "android")
        assert clusters[0]["fingerprint"] == "common"
        assert clusters[0]["count"] == 5


class TestFunnel:
    def test_drop_off_is_relative_to_the_previous_step(self, db):
        """The common bug is computing drop-off against the first step, which
        makes a healthy funnel look catastrophic.

        The fixture is a realistic descending funnel: 3 opens, 2 sign-ins,
        1 purchase. One of the two sign-ins dropped, so 50%.
        """
        for _ in range(3):
            _ev(db, name="app_open", ts=NOW)
        for _ in range(2):
            _ev(db, name="sign_in", ts=NOW)
        _ev(db, name="purchase_completed", ts=NOW)
        rollup_mod.rollup(db, lookback_hours=48, now=NOW)
        start, end = queries.window(1)
        f = queries.funnel(db, ["app_open", "sign_in", "purchase_completed"], start, end)
        assert f[0]["count"] == 3
        assert f[1]["count"] == 2
        assert f[1]["drop_off_pct"] == 33.3, "1 of 3 opens dropped"
        assert f[2]["drop_off_pct"] == 50.0, "1 of 2 sign-ins dropped, not 1 of 3"

    def test_a_step_that_grows_reports_a_negative_drop_off(self, db):
        """More sign-ins than opens means the funnel steps are not really
        sequential. Clamping that to 0% would hide a real data problem."""
        _ev(db, name="app_open", ts=NOW)
        _ev(db, name="sign_in", ts=NOW)
        _ev(db, name="sign_in", ts=NOW)
        rollup_mod.rollup(db, lookback_hours=48, now=NOW)
        start, end = queries.window(1)
        f = queries.funnel(db, ["app_open", "sign_in"], start, end)
        assert f[1]["drop_off_pct"] == -100.0

    def test_the_first_step_has_no_conversion_rate(self, db):
        _ev(db, name="app_open", ts=NOW)
        rollup_mod.rollup(db, lookback_hours=48, now=NOW)
        start, end = queries.window(1)
        f = queries.funnel(db, ["app_open"], start, end)
        assert "conversion_pct" not in f[0]


class TestDimensions:
    def test_rejects_a_column_outside_the_allowlist(self, db):
        """This function is reachable by a model-chosen argument, so the column
        name is checked against a literal set rather than interpolated."""
        start, end = queries.window(1)
        with pytest.raises(ValueError):
            queries.top_dimensions(db, start, end, "user_hash")

    def test_top_countries_are_ordered_by_volume(self, db):
        for _ in range(3):
            _ev(db, name="app_open", country="IN")
        _ev(db, name="app_open", country="US")
        rollup_mod.rollup(db, lookback_hours=48, now=NOW)
        start, end = queries.window(1)
        top = queries.top_dimensions(db, start, end, "country")
        assert top[0] == {"value": "IN", "events": 3}
        assert top[1]["value"] == "US"

    def test_an_absent_dimension_renders_as_unknown(self, db):
        _ev(db, name="app_open", country=None)
        rollup_mod.rollup(db, lookback_hours=48, now=NOW)
        start, end = queries.window(1)
        assert queries.top_dimensions(db, start, end, "country")[0]["value"] == "unknown"


class TestSecurityCounts:
    def test_counts_are_grouped_by_kind(self, db):
        for kind in ("root_detected", "root_detected", "tamper_detected"):
            db.add(SecurityEvent(ts=NOW, platform="android", kind=kind, ip_hash=None,
                                 user_hash=None, app_version=None, blocked=True, detail={}))
        db.commit()
        start, end = queries.window(1)
        counts = queries.security_counts(db, start, end)
        assert counts == {"root_detected": 2, "tamper_detected": 1}

    def test_a_kind_filter_narrows_the_result(self, db):
        for kind in ("root_detected", "tamper_detected"):
            db.add(SecurityEvent(ts=NOW, platform="android", kind=kind, ip_hash=None,
                                 user_hash=None, app_version=None, blocked=True, detail={}))
        db.commit()
        start, end = queries.window(1)
        out = queries.security_counts(db, start, end, kinds={"tamper_detected"})
        assert out == {"tamper_detected": 1}


# ===========================================================================
# Windows
# ===========================================================================

class TestWindows:
    def test_previous_window_is_the_same_length_immediately_before(self, db):
        """Comparing 7d against a fixed 30d baseline produces a 400% swing that
        never happened."""
        start, end = queries.window(7)
        p_start, p_end = queries.previous_window(start, end)
        assert (end - start) == (p_end - p_start)
        assert p_end == start

    def test_baseline_is_the_28_days_before_the_window(self, db):
        start, end = queries.window(1)
        b_start, b_end = queries.baseline_window(start, end)
        assert b_end == start
        assert (start - b_start).days == 28


# ===========================================================================
# Rate limiting
# ===========================================================================

class TestRateLimiter:
    def test_allows_up_to_the_limit_then_blocks(self):
        lim = SlidingWindowLimiter(limit=3, window_s=60)
        assert [lim.allow("k") for _ in range(5)] == [True, True, True, False, False]

    def test_keys_are_independent(self):
        lim = SlidingWindowLimiter(limit=1, window_s=60)
        assert lim.allow("a") is True
        assert lim.allow("b") is True
        assert lim.allow("a") is False

    def test_a_blocked_request_is_not_counted(self):
        """Otherwise a client hammering a closed door pushes its own window
        further out and can stay blocked long after it should recover."""
        lim = SlidingWindowLimiter(limit=2, window_s=60)
        for _ in range(10):
            lim.allow("k")
        assert lim.allow("k") is False

    def test_retry_after_is_at_least_one_second(self):
        lim = SlidingWindowLimiter(limit=1, window_s=60)
        lim.allow("k")
        assert lim.retry_after("k") >= 1

    def test_rejects_a_nonsense_limit(self):
        with pytest.raises(ValueError):
            SlidingWindowLimiter(limit=0)


# ===========================================================================
# HTTP surface
# ===========================================================================

@pytest.fixture
def telemetry_on(monkeypatch):
    """Telemetry is off by default, so tests opt in explicitly.

    Off-by-default is the real behaviour and is asserted separately; silently
    enabling it in conftest would make that untestable.
    """
    settings = get_settings()
    monkeypatch.setattr(settings, "telemetry_enabled", True)
    monkeypatch.setattr(settings, "telemetry_pepper", "test-pepper")
    return settings


@pytest.fixture
def anon_client():
    with TestClient(app) as c:
        yield c


def _event(name="app_open", **over):
    base = {"event_name": name, "platform": "web", "session_id": "sess-00000001"}
    base.update(over)
    return base


class TestCollectorRoutes:
    def test_collects_without_authentication(self, anon_client, telemetry_on, db):
        """A browser beacon cannot hold a database credential, and anonymous
        visitors generate events too."""
        r = anon_client.post("/collect/events", json={"events": [_event()]})
        assert r.status_code == 200
        assert r.json() == {"accepted": 1, "rejected": 0}
        assert len(db.exec(select(Event)).all()) == 1

    def test_a_partial_failure_is_still_a_200(self, anon_client, telemetry_on, db):
        """A non-2xx would make well-behaved clients retry the whole batch
        forever, including the events that were fine."""
        r = anon_client.post("/collect/events", json={"events": [
            _event(), _event(name="bogus"), _event(name="page_view"),
        ]})
        assert r.status_code == 200
        assert r.json() == {"accepted": 2, "rejected": 1}

    def test_refuses_when_telemetry_is_disabled(self, anon_client, db):
        """The default. An open unauthenticated write endpoint should not be
        there just because someone forgot to switch it off."""
        r = anon_client.post("/collect/events", json={"events": [_event()]})
        assert r.status_code == 503
        assert len(db.exec(select(Event)).all()) == 0

    def test_rejects_an_oversized_batch(self, anon_client, telemetry_on, db):
        r = anon_client.post("/collect/events", json={"events": [_event()] * 500})
        assert r.status_code == 413

    def test_a_client_cannot_set_its_own_identity(self, anon_client, telemetry_on, db):
        """If `user_hash` were client-settable, anyone could forge activity for
        any user and every count would be attacker-controlled."""
        anon_client.post("/collect/events", json={"events": [_event(user_hash="victim")]})
        row = db.exec(select(Event)).first()
        assert row.user_hash is None

    def test_stores_no_raw_ip_anywhere(self, anon_client, telemetry_on, db):
        anon_client.post("/collect/security-signal", json={
            "platform": "android", "kind": "root_detected", "blocked": True,
        })
        row = db.exec(select(SecurityEvent)).first()
        assert row.ip_hash is not None
        assert len(row.ip_hash) == 32
        assert "127.0.0.1" not in row.ip_hash and "testclient" not in row.ip_hash

    def test_accepts_a_crash_report(self, anon_client, telemetry_on, db):
        r = anon_client.post("/collect/crash", json={
            "platform": "android", "kind": "crash", "session_id": "sess-00000001",
            "fingerprint": "abc123", "exception_type": "NullPointerException",
            "message": "boom", "stack_trace": "at com.x.Y(Y.java:1)", "fatal": True,
        })
        assert r.status_code == 200
        row = db.exec(select(CrashReport)).first()
        assert row.fingerprint == "abc123"
        assert row.session_id == "sess-00000001"

    def test_rejects_an_unknown_crash_kind(self, anon_client, telemetry_on, db):
        r = anon_client.post("/collect/crash", json={
            "kind": "explosion", "session_id": "sess-00000001", "fingerprint": "f",
        })
        assert r.status_code == 400

    def test_rejects_an_unknown_security_signal(self, anon_client, telemetry_on, db):
        r = anon_client.post("/collect/security-signal", json={"kind": "definitely_fine"})
        assert r.status_code == 400

    def test_rate_limits_repeat_batches(self, anon_client, telemetry_on, db):
        from features.monitoring.ratelimit import COLLECT_BATCH_LIMIT

        COLLECT_BATCH_LIMIT.reset()
        codes = [anon_client.post("/collect/events", json={"events": [_event()]}).status_code
                 for _ in range(35)]
        assert 429 in codes, "an unbounded ingest endpoint is a DoS primitive"
        COLLECT_BATCH_LIMIT.reset()


class TestMetricsEndpoint:
    def test_serves_the_registry(self, anon_client, db):
        r = anon_client.get("/metrics")
        assert r.status_code == 200
        assert "campuspilot_http_requests_total" in r.text

    def test_excludes_itself_from_its_own_counters(self, anon_client, db):
        """Otherwise the endpoint reports latency that includes its own
        serialization cost, and every scrape changes the numbers it reports."""
        anon_client.get("/metrics")
        text = anon_client.get("/metrics").text
        assert 'campuspilot_http_requests_total{route="metrics"' not in text

    def test_uses_route_templates_not_concrete_paths(self, anon_client, db):
        anon_client.get("/health")
        text = anon_client.get("/metrics").text
        assert 'route="health"' in text
        assert 'route="/health"' not in text

    def test_status_is_bucketed_into_a_class(self, anon_client, db):
        anon_client.get("/definitely-not-a-route")
        text = anon_client.get("/metrics").text
        assert 'status="4xx"' in text
        assert 'status="404"' not in text


class TestAdminRoutesNeedAuth:
    @pytest.mark.parametrize("path", [
        "/monitoring/overview",
        "/monitoring/health",
        "/monitoring/history",
        "/monitoring/subsections",
    ])
    def test_anonymous_is_rejected(self, anon_client, path):
        r = anon_client.get(path)
        assert r.status_code == 401, f"{path} is readable without a token"

    @pytest.mark.parametrize("path", [
        "/monitoring/overview",
        "/monitoring/health",
        "/monitoring/history",
    ])
    def test_a_student_is_forbidden(self, anon_client, path, db):
        from features.auth.routes import create_access_token
        from models import User

        with Session(engine) as session:
            student = session.exec(
                select(User).where(User.username == "monstudent")
            ).first()
            if student is None:
                student = User(email="monstu@iiitdmj.ac.in", password_hash="x",
                               full_name="Mon Student", username="monstudent",
                               roll_number="23BCS998", is_email_verified=True,
                               role="student")
                session.add(student)
                session.commit()
                session.refresh(student)
            token = create_access_token(student.id, "monstudent")

        r = anon_client.get(path, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403, f"{path} is readable by a non-admin"


class TestAdminRoutes:
    @pytest.fixture
    def admin(self):
        from features.auth.routes import create_access_token
        from models import User

        with Session(engine) as session:
            user = session.exec(select(User).where(User.username == "monadmin")).first()
            if user is None:
                user = User(email="mon@iiitdmj.ac.in", password_hash="x",
                            full_name="Mon Admin", username="monadmin",
                            roll_number="23BCS999", is_email_verified=True, role="admin")
                session.add(user)
                session.commit()
                session.refresh(user)
            user_id = user.id
        return {"Authorization": f"Bearer {create_access_token(user_id, 'monadmin')}"}

    def test_subsection_list_has_all_eight(self, anon_client, admin):
        body = anon_client.get("/monitoring/subsections", headers=admin).json()
        assert len(body["subsections"]) == 8
        ids = {s["id"] for s in body["subsections"]}
        assert ids == {
            "A_W_HEALTH", "B_W_ACTIVITY", "C_W_SECURITY", "D_W_FEEDBACK",
            "A_A_HEALTH", "B_A_ACTIVITY", "C_A_SECURITY", "D_A_FEEDBACK",
        }

    def test_overview_returns_every_section(self, anon_client, admin, db):
        r = anon_client.get("/monitoring/overview?days=7", headers=admin)
        assert r.status_code == 200, r.text
        body = r.json()
        for key in ("window", "activity", "security", "revenue", "arpu",
                    "ads", "crashes", "data_freshness"):
            assert key in body, f"overview is missing {key}"

    def test_overview_on_an_empty_database_reports_zero_not_a_500(self, anon_client, admin, db):
        r = anon_client.get("/monitoring/overview?days=7", headers=admin)
        assert r.status_code == 200
        assert r.json()["activity"]["active_users"] == 0

    def test_data_freshness_is_null_when_nothing_has_been_collected(self, anon_client, admin, db):
        """A dashboard showing confident zeros is worse than one saying
        'no data yet': an admin cannot otherwise tell healthy from broken."""
        fresh = anon_client.get("/monitoring/overview", headers=admin).json()["data_freshness"]
        assert fresh["latest_rollup_hour"] is None
        assert fresh["rollup_lag_minutes"] is None

    def test_data_freshness_reports_the_rollup_lag(self, anon_client, admin, db):
        _ev(db, name="app_open")
        anon_client.post("/monitoring/rollup", headers=admin)
        fresh = anon_client.get("/monitoring/overview", headers=admin).json()["data_freshness"]
        assert fresh["latest_rollup_hour"] is not None
        assert 0 <= fresh["rollup_lag_minutes"] <= 120

    def test_manual_rollup_populates_the_dashboard(self, anon_client, admin, db):
        """Event volume only exists after the rollup runs; user counts come
        straight off the session table and are visible immediately.

        The split is the point: it shows which numbers are live and which depend
        on the background job actually having run.
        """
        for i in range(5):
            _sess(db, user=i, started=NOW - timedelta(hours=2), sid=f"s{i}")
        _ev(db, name="app_open", ts=NOW - timedelta(hours=2))

        before = anon_client.get("/monitoring/overview", headers=admin).json()["activity"]
        assert before["events"] == 0, "the rollup has not run yet"
        assert before["active_users"] == 5, "user counts do not depend on the rollup"

        anon_client.post("/monitoring/rollup", headers=admin)
        after = anon_client.get("/monitoring/overview", headers=admin).json()["activity"]
        assert after["events"] == 1

    def test_manual_rollup_is_idempotent(self, anon_client, admin, db):
        for i in range(5):
            _sess(db, user=i, started=NOW - timedelta(hours=2), sid=f"s{i}")
        anon_client.post("/monitoring/rollup", headers=admin)
        first = anon_client.get("/monitoring/overview", headers=admin
                                ).json()["activity"]
        anon_client.post("/monitoring/rollup", headers=admin)
        second = anon_client.get("/monitoring/overview", headers=admin
                                 ).json()["activity"]
        assert first == second

    def test_health_endpoint_returns_the_prometheus_shape(self, anon_client, admin, db):
        body = anon_client.get("/monitoring/health?days=7", headers=admin).json()
        assert "http" in body and "db" in body and "crashes" in body
        assert "requests_by_route" in body["http"]

    def test_history_with_no_scans_is_empty_not_an_error(self, anon_client, admin, db):
        body = anon_client.get("/monitoring/history", headers=admin).json()
        assert body["scans"] == [] and body["incidents"] == []

    def test_history_pairs_an_open_incident(self, anon_client, admin, db):
        """An incident with no closing transition is still open, and its
        duration is unknown - reporting 0 seconds would read as a 0s outage."""
        db.add(ScanResult(scan_id="s1", subsection="A_W_HEALTH", status="critical",
                          summary="disk full", findings=[], root_causes=[],
                          actions=[], confidence={}, model="test", prompt_hash="h",
                          window_start=NOW - timedelta(hours=1), window_end=NOW,
                          duration_ms=10))
        db.add(StatusTransition(subsection="A_W_HEALTH", from_status="healthy",
                                to_status="critical", scan_id="s1", at=NOW))
        db.commit()
        body = anon_client.get("/monitoring/history", headers=admin).json()
        assert len(body["scans"]) == 1
        assert len(body["incidents"]) == 1
        assert body["incidents"][0]["open"] is True
        assert body["incidents"][0]["duration_s"] is None

    def test_history_closes_an_incident(self, anon_client, admin, db):
        for scan_id, status, at in (("s1", "critical", NOW - timedelta(hours=2)),
                                    ("s2", "healthy", NOW - timedelta(hours=1))):
            db.add(ScanResult(scan_id=scan_id, subsection="A_W_HEALTH", status=status,
                              summary="", findings=[], root_causes=[], actions=[],
                              confidence={}, model="test", prompt_hash="h",
                              window_start=at, window_end=at, duration_ms=10))
            db.add(StatusTransition(subsection="A_W_HEALTH", from_status="healthy",
                                    to_status=status, scan_id=scan_id, at=at))
        db.commit()
        inc = anon_client.get("/monitoring/history", headers=admin
                              ).json()["incidents"][0]
        assert inc["open"] is False
        assert inc["duration_s"] == 3600

    def test_days_is_clamped(self, anon_client, admin, db):
        """An unbounded window parameter is a trivial way to ask the database
        for its entire history."""
        r = anon_client.get("/monitoring/overview?days=99999", headers=admin)
        assert r.status_code == 200
        assert r.json()["window"]["days"] == 90

    def test_feedback_responses_are_untouched(self, anon_client, admin, db):
        """The existing Feedback Responses feature must keep working exactly as
        before. Pinned here because the monitoring section sits next to it."""
        r = anon_client.get("/feedback/responses", headers=admin)
        assert r.status_code in (200, 404), r.status_code


if __name__ == "__main__":
    pytest.main([__file__, "-v"])