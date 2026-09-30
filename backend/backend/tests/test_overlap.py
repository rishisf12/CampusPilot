"""Unit tests for is_overlapping helper (used by vacant room finder)."""
import pytest
from datetime import time


def is_overlapping(start: time, end: time, query_time: time) -> bool:
    """Start-inclusive, end-exclusive overlap check."""
    return start <= query_time < end


class TestIsOverlapping:
    def test_exact_start(self):
        assert is_overlapping(time(9, 0), time(10, 0), time(9, 0)) is True

    def test_exact_end(self):
        assert is_overlapping(time(9, 0), time(10, 0), time(10, 0)) is False

    def test_middle(self):
        assert is_overlapping(time(9, 0), time(10, 0), time(9, 30)) is True

    def test_before(self):
        assert is_overlapping(time(9, 0), time(10, 0), time(8, 59)) is False

    def test_after(self):
        assert is_overlapping(time(9, 0), time(10, 0), time(10, 1)) is False

    def test_back_to_back(self):
        # Class ends at 10:00, next starts at 10:00 - no overlap
        assert is_overlapping(time(9, 0), time(10, 0), time(10, 0)) is False
        assert is_overlapping(time(10, 0), time(11, 0), time(10, 0)) is True

    def test_zero_duration(self):
        # start == end should never overlap (invalid slot)
        assert is_overlapping(time(9, 0), time(9, 0), time(9, 0)) is False

    def test_cross_midnight_not_supported(self):
        # We don't support cross-midnight; slots are within same day
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])