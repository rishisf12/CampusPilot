"""Unit tests for schedule service."""
import pytest
from datetime import time
from features.schedule.service import (
    time_to_minutes,
    minutes_to_time,
    is_time_between,
)


class TestTimeConversion:
    def test_time_to_minutes(self):
        assert time_to_minutes(time(0, 0)) == 0
        assert time_to_minutes(time(9, 0)) == 540
        assert time_to_minutes(time(13, 30)) == 810
        assert time_to_minutes(time(23, 59)) == 1439

    def test_minutes_to_time(self):
        assert minutes_to_time(0) == time(0, 0)
        assert minutes_to_time(540) == time(9, 0)
        assert minutes_to_time(810) == time(13, 30)
        assert minutes_to_time(1439) == time(23, 59)

    def test_roundtrip(self):
        for h in range(24):
            for m in range(0, 60, 15):
                t = time(h, m)
                assert minutes_to_time(time_to_minutes(t)) == t


class TestIsTimeBetween:
    def test_basic(self):
        assert is_time_between(time(9, 30), time(9, 0), time(10, 0)) is True
        assert is_time_between(time(9, 0), time(9, 0), time(10, 0)) is True  # start inclusive
        assert is_time_between(time(10, 0), time(9, 0), time(10, 0)) is False  # end exclusive

    def test_before(self):
        assert is_time_between(time(8, 59), time(9, 0), time(10, 0)) is False

    def test_after(self):
        assert is_time_between(time(10, 1), time(9, 0), time(10, 0)) is False

    def test_lunch_break(self):
        assert is_time_between(time(13, 15), time(13, 0), time(14, 0)) is True
        assert is_time_between(time(13, 0), time(13, 0), time(14, 0)) is True
        assert is_time_between(time(14, 0), time(13, 0), time(14, 0)) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])