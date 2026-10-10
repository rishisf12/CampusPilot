"""Unit tests for timetable parser."""
import pytest
from datetime import time
from features.timetable.parser import (
    parse_time_str,
    parse_time_range,
    normalize_room,
)


class TestParseTimeStr:
    def test_standard(self):
        assert parse_time_str("9:00") == time(9, 0)
        assert parse_time_str("09:00") == time(9, 0)

    def test_dot_separator(self):
        assert parse_time_str("9.00") == time(9, 0)
        assert parse_time_str("14.30") == time(14, 30)

    def test_invalid(self):
        assert parse_time_str("25:00") is None
        assert parse_time_str("9:60") is None
        assert parse_time_str("abc") is None


class TestParseTimeRange:
    def test_standard(self):
        assert parse_time_range("9:00-10:00") == (time(9, 0), time(10, 0))
        assert parse_time_range("09:00 - 10:00") == (time(9, 0), time(10, 0))

    def test_dash_variants(self):
        assert parse_time_range("9:00–10:00") == (time(9, 0), time(10, 0))  # en-dash

    def test_dot_separator(self):
        assert parse_time_range("9.00-10.00") == (time(9, 0), time(10, 0))

    def test_single_time_fallback(self):
        assert parse_time_range("9:00") == (time(9, 0), time(10, 0))

    def test_invalid(self):
        assert parse_time_range("abc") == (None, None)


class TestNormalizeRoom:
    def test_space_to_dash(self):
        assert normalize_room("L 201") == "L-201"
        assert normalize_room("CR 103") == "CR-103"

    def test_already_normalized(self):
        assert normalize_room("L-201") == "L-201"
        assert normalize_room("CR-103") == "CR-103"

    def test_multiple_spaces(self):
        assert normalize_room("L   201") == "L-201"

    def test_case_insensitive(self):
        assert normalize_room("l 201") == "L-201"

    def test_empty(self):
        assert normalize_room("") == ""
        assert normalize_room(None) == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])