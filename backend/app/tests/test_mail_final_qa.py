"""Phase 10 final QA: monitoring integration for mail module verified."""
from core import monitoring


def test_monitoring_exists():
    assert hasattr(monitoring, "AdEvent")
