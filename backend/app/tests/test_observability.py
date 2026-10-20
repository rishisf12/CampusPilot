"""Tests for the in-house observability bundle (Phase 2 of the MCP plan).

Two collectors, and the properties each must guarantee:

* `observability.host` - honest host numbers. Every metric is either a real
  reading or None; network bytes are deltas against the previous sample, so
  the first sample is None rather than a lifetime total, and a boot-time
  counter reset reads 0 rather than a negative number.
* `observability.uptime` - availability derived at read time. Pinned against
  hand-computed coverage over known row layouts, with the None/0 distinction
  ("cannot say" vs "everything missing") asserted separately, because that is
  the difference between unknown and an incident.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, delete

from core.database import engine
from core.config import settings
from features.monitoring.domain.models import HealthMetric
from observability import host as host_mod
from observability.uptime import coverage_pct


def _utc(naive: bool = True) -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(tzinfo=None, microsecond=0) if naive else now


@pytest.fixture
def db_session():
    """A session with `telemetry.health_metric` emptied first."""
    with Session(engine) as session:
        session.exec(delete(HealthMetric))
        session.commit()
        yield session
        session.exec(delete(HealthMetric))
        session.commit()


# ---------------------------------------------------------------------------
# host sampler
# ---------------------------------------------------------------------------

class _FakeVM:
    def __init__(self, percent: float) -> None:
        self.percent = percent


class _FakeDisk:
    def __init__(self, percent: float) -> None:
        self.percent = percent


class _FakeIO:
    def __init__(self, rx: int, tx: int) -> None:
        self.bytes_recv = rx
        self.bytes_sent = tx


class _FakePsutil:
    """The three psutil calls the sampler makes, pinned by the test."""

    def __init__(self, *, cpu: float, ram: float, disk: float, rx: int, tx: int) -> None:
        self._cpu, self._ram, self._disk, self._rx, self._tx = cpu, ram, disk, rx, tx

    def cpu_percent(self, interval=None):
        return self._cpu

    def virtual_memory(self):
        return _FakeVM(self._ram)

    def disk_usage(self, path):
        return _FakeDisk(self._disk)

    def net_io_counters(self):
        return _FakeIO(self._rx, self._tx)


def test_sample_host_reports_pinned_numbers(monkeypatch):
    monkeypatch.setattr(
        host_mod, "psutil", _FakePsutil(cpu=12.34, ram=55.56, disk=88.9, rx=1000, tx=2000)
    )
    host_mod._reset_host_state()

    first = host_mod.sample_host()

    assert first["cpu_pct"] == 12.3
    assert first["ram_pct"] == 55.6
    assert first["disk_pct"] == 88.9
    # First sample has no baseline: None, not a lifetime total.
    assert first["network_rx_bytes"] is None
    assert first["network_tx_bytes"] is None

    # Second sample reports the delta, and a counter that went backwards
    # (host reboot) reads as 0 rather than negative.
    monkeypatch.setattr(
        host_mod, "psutil", _FakePsutil(cpu=30.0, ram=60.0, disk=90.0, rx=1500, tx=1800)
    )
    second = host_mod.sample_host()
    assert second["network_rx_bytes"] == 500
    assert second["network_tx_bytes"] == 0


def test_sample_host_degrades_without_psutil(monkeypatch):
    monkeypatch.setattr(host_mod, "psutil", None)
    out = host_mod.sample_host()
    assert out == {
        "cpu_pct": None,
        "ram_pct": None,
        "disk_pct": None,
        "network_rx_bytes": None,
        "network_tx_bytes": None,
    }


def test_sample_once_fills_host_columns(db_session, monkeypatch):
    """`sample_once` (the only health_metric writer) records host numbers."""
    from features.monitoring.infrastructure import health

    monkeypatch.setattr(
        host_mod, "psutil", _FakePsutil(cpu=40.0, ram=70.0, disk=50.0, rx=10, tx=20)
    )
    health._reset_counter_state()
    host_mod._reset_host_state()

    row = health.sample_once(db_session)

    assert row.cpu_pct == 40.0
    assert row.ram_pct == 70.0
    assert row.disk_pct == 50.0
    # A second sample picks up counter deltas.
    row2 = health.sample_once(db_session)
    assert row2.network_rx_bytes == 0
    assert row2.network_tx_bytes == 0


# ---------------------------------------------------------------------------
# uptime coverage
# ---------------------------------------------------------------------------

def _insert_rows(db_session, ts_values, platform="web"):
    for ts in ts_values:
        db_session.add(HealthMetric(ts=ts, platform=platform))
    db_session.commit()


def test_coverage_full_window_is_100(db_session, monkeypatch):
    monkeypatch.setattr(settings, "health_sample_interval_s", 60)
    start = _utc()
    # Samples at 0, 60, 120s in a 3-minute window: 3 intervals, 3 rows.
    _insert_rows(db_session, [start, start + timedelta(seconds=60), start + timedelta(seconds=120)])

    pct = coverage_pct(
        db_session,
        start=start,
        end=start + timedelta(seconds=180),
        interval_s=60,
    )
    assert pct == 100.0


def test_coverage_counts_missing_intervals(db_session, monkeypatch):
    monkeypatch.setattr(settings, "health_sample_interval_s", 60)
    start = _utc()
    # Middle sample lost (the process may have been down for that minute).
    _insert_rows(db_session, [start, start + timedelta(seconds=120)])

    pct = coverage_pct(
        db_session,
        start=start,
        end=start + timedelta(seconds=180),
        interval_s=60,
    )
    assert pct == round(2 / 3 * 100, 2)  # 66.67


def test_coverage_full_gap_reads_zero_when_sampler_was_running(db_session):
    start = _utc()
    # A row from before the window proves the sampler was already expected;
    # nothing inside the window means every interval went missing.
    _insert_rows(db_session, [start - timedelta(minutes=10)])

    pct = coverage_pct(
        db_session,
        start=start,
        end=start + timedelta(minutes=5),
        interval_s=60,
    )
    assert pct == 0.0


def test_coverage_returns_none_without_any_data(db_session):
    start = _utc()
    assert (
        coverage_pct(
            db_session,
            start=start,
            end=start + timedelta(minutes=5),
            interval_s=60,
        )
        is None
    )


def test_coverage_bootstrap_does_not_masquerade_as_downtime(db_session):
    """The sampler was enabled mid-window: coverage anchors to the first row
    instead of declaring the pre-enable period downtime."""
    start = _utc()
    _insert_rows(
        db_session,
        [start + timedelta(seconds=60), start + timedelta(seconds=120)],
    )
    pct = coverage_pct(
        db_session,
        start=start,
        end=start + timedelta(seconds=180),
        interval_s=60,
    )
    # 2 intervals after the anchor, 2 rows present.
    assert pct == 100.0


def test_coverage_is_platform_scoped(db_session):
    start = _utc()
    _insert_rows(db_session, [start], platform="android")

    assert (
        coverage_pct(
            db_session,
            platform="web",
            start=start,
            end=start + timedelta(minutes=5),
            interval_s=60,
        )
        is None
    )


def test_coverage_uses_the_configured_interval(db_session, monkeypatch):
    """No explicit interval: the configured sampling cadence is the truth."""
    monkeypatch.setattr(settings, "health_sample_interval_s", 60)
    start = _utc()
    _insert_rows(db_session, [start, start + timedelta(seconds=60), start + timedelta(seconds=120)])

    assert (
        coverage_pct(
            db_session,
            start=start,
            end=start + timedelta(seconds=180),
        )
        == 100.0
    )


def test_sample_once_rows_drive_the_scan_uptime(db_session, monkeypatch):
    """The A_W collector reads uptime from coverage, not from the row's NULL."""
    from features.monitoring.services.scan_service import _collect_a_w_health_data

    monkeypatch.setattr(settings, "health_sample_interval_s", 60)
    start = _utc()
    _insert_rows(
        db_session,
        [start, start + timedelta(seconds=60), start + timedelta(seconds=120)],
    )

    data = _collect_a_w_health_data(
        db_session,
        start=start,
        end=start + timedelta(seconds=180),
        platform="web",
    )
    assert data["uptime_pct"] == 100.0
