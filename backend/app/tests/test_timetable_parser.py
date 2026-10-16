"""Unit tests for timetable parser."""
import pytest
from datetime import time
from features.timetable.parser import (
    parse_time_str,
    parse_time_range,
    normalize_room,
    _tokenize_cell,
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


class TestTokenizeCellSlashHandling:
    """Slash handling in _tokenize_cell: join two real course codes,
    split course/instructor/room, and keep leading group digits with a course."""

    def test_two_course_codes_joined_by_slash_stay_together(self):
        # "OE3M27/ME5D02" is two real course codes - the slash keeps them as one token
        assert _tokenize_cell("OE3M27/ME5D02") == ["OE3M27/ME5D02"]

    def test_course_instructor_room_split_on_slash(self):
        # "ME3001/SKC/CR-208" is course + instructor + room - the slashes split
        assert _tokenize_cell("ME3001/SKC/CR-208") == ["ME3001", "SKC", "CR-208"]

    def test_leading_group_digit_with_course_code_stays_together(self):
        # "27/ME5D02" - the "27" is a group digit prefix, not a separate field
        assert _tokenize_cell("27/ME5D02") == ["27/ME5D02"]

    def test_three_fields_course_instructor_room(self):
        assert _tokenize_cell("CS5031/VKG/L-202") == ["CS5031", "VKG", "L-202"]

    def test_collaborated_faculty_split_on_slash(self):
        # "CS5031/VKG/SKJ/CR-208" - course + two instructors + room
        assert _tokenize_cell("CS5031/VKG/SKJ/CR-208") == ["CS5031", "VKG", "SKJ", "CR-208"]

    def test_course_instructor_room_with_dash_separator(self):
        # Mixed separators: dash splits course from instructor, slash splits instructor from room
        assert _tokenize_cell("ME3001-SKC/CR-208") == ["ME3001", "SKC", "CR-208"]

    def test_bug_me3001_skc_cr208_not_merged(self):
        # Regression test: "ME3001/SKC/CR-208" must not be kept as one token.
        # The old single-character alnum check wrongly joined course/instructor/room.
        assert _tokenize_cell("ME3001/SKC/CR-208") != ["ME3001/SKC/CR-208"]
        assert _tokenize_cell("ME3001/SKC/CR-208") == ["ME3001", "SKC", "CR-208"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])