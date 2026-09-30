"""Unit tests for attendance calculations."""
import pytest
from services.attendance_service import (
    calculate_percentage,
    get_status,
    classes_can_miss,
    classes_to_attend,
)


class TestCalculatePercentage:
    def test_zero_classes(self):
        assert calculate_percentage(0, 0) == 100.0

    def test_all_present(self):
        assert calculate_percentage(10, 0) == 100.0

    def test_half_present(self):
        assert calculate_percentage(5, 5) == 50.0

    def test_typical(self):
        assert calculate_percentage(8, 2) == 80.0

    def test_rounding(self):
        assert calculate_percentage(1, 2) == 33.33


class TestGetStatus:
    def test_safe(self):
        assert get_status(75) == "Safe"
        assert get_status(80) == "Safe"
        assert get_status(100) == "Safe"

    def test_warning(self):
        assert get_status(74.99) == "Warning"
        assert get_status(70) == "Warning"
        assert get_status(65) == "Warning"

    def test_critical(self):
        assert get_status(64.99) == "Critical"
        assert get_status(50) == "Critical"
        assert get_status(0) == "Critical"


class TestClassesCanMiss:
    def test_already_critical(self):
        # 5 present, 5 absent = 50%, can't miss any to stay at 75%
        assert classes_can_miss(5, 5) == 0

    def test_safe_can_miss_some(self):
        # 9 present, 1 absent = 90%, can miss 1 and stay at 75%
        # 9 / (10 + x) >= 0.75 -> 9 >= 7.5 + 0.75x -> 1.5 >= 0.75x -> x <= 2
        assert classes_can_miss(9, 1) == 2

    def test_exact_threshold(self):
        # 3 present, 1 absent = 75% exactly
        assert classes_can_miss(3, 1) == 0


class TestClassesToAttend:
    def test_already_safe(self):
        assert classes_to_attend(8, 2) == 0  # 80%

    def test_needs_some(self):
        # 5 present, 5 absent = 50%, need to attend consecutive to reach 75%
        # (5 + x) / (10 + x) >= 0.75 -> 5 + x >= 7.5 + 0.75x -> 0.25x >= 2.5 -> x >= 10
        assert classes_to_attend(5, 5) == 10

    def test_zero_classes(self):
        assert classes_to_attend(0, 0) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])