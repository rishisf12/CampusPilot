"""Unit tests for room service (vacant room finder)."""
import pytest
from datetime import time
from services.room_service import is_overlapping


class TestIsOverlapping:
    """Tests for is_overlapping helper (start-inclusive, end-exclusive)."""

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

    def test_back_to_back_classes(self):
        """Class ends at 10:00, next starts at 10:00 - no overlap."""
        assert is_overlapping(time(9, 0), time(10, 0), time(10, 0)) is False
        assert is_overlapping(time(10, 0), time(11, 0), time(10, 0)) is True

    def test_zero_duration_slot(self):
        """Start == end should never overlap (invalid slot)."""
        assert is_overlapping(time(9, 0), time(9, 0), time(9, 0)) is False

    def test_lunch_break_boundary(self):
        """Lunch 13:00-14:00 boundaries."""
        assert is_overlapping(time(13, 0), time(14, 0), time(13, 0)) is True
        assert is_overlapping(time(13, 0), time(14, 0), time(13, 30)) is True
        assert is_overlapping(time(13, 0), time(14, 0), time(14, 0)) is False

    def test_college_hours_boundary(self):
        """College 09:00-17:00 boundaries."""
        assert is_overlapping(time(9, 0), time(17, 0), time(9, 0)) is True
        assert is_overlapping(time(9, 0), time(17, 0), time(16, 59)) is True
        assert is_overlapping(time(9, 0), time(17, 0), time(17, 0)) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])