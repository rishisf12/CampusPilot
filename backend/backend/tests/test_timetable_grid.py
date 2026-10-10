"""
Tests for parsing the published day-section timetable grid.

The real document is organised as one section per weekday, not one column per
weekday, so the older column-per-day parser cannot read it at all. These tests
pin that layout down: the day marker, the time header, the semester bands, the
blank-cell branch continuation, and the packed ``code-instructor-room`` cells.
"""
from datetime import time

import pytest

from features.timetable.parser import (
    _split_cell_entries,
    parse_day_section_timetable,
    roman_to_int,
)

# A miniature version of the real grid: Monday, two semesters, CSE over two
# groups (the second continuing the branch on a blank leading cell) plus ECE.
DAY_SECTION_TABLE = [
    ["Time Table :Aug-Nov 2026", "", "", "", "", ""],
    ["Monday", "", "", "", "", ""],
    ["Time/Day", "Group", "8:00-8:55", "9:00-9:55", "10:00-10:55", "11:00-11:55"],
    ["I Sem", "", "", "", "", ""],
    ["CSE", "A", "", "NS1002-MKR-L102", "HS-1001-JAMF-L102", "NS1001-SSL-L102"],
    ["", "B", "", "NS1002-YSK-L202", "", "NS1001-LKB-L202"],
    ["ECE", "C", "HS 1001 -MA- L106", "NS1002-NRJ-L106", "EC1001-SKJ-L106", ""],
    ["V Sem", "", "", "", "", ""],
    ["CSE", "A", "CS3010L-AG-CC-3F", "", "HS3004-VF-L107", "CS3009-ShM-L104"],
    ["Tuesday", "", "", "", "", ""],
    ["Time/Day", "Group", "8:00-8:55", "9:00-9:55", "10:00-10:55", "11:00-11:55"],
    ["V Sem", "", "", "", "", ""],
    ["CSE", "A", "CS8028-NA-CC 2F", "", "OE3: CS8016-BiG (VF)-L107 OE4L01-VF-L202", ""],
]


class TestRomanNumerals:
    def test_single_digit(self):
        assert roman_to_int("I") == 1

    def test_v(self):
        assert roman_to_int("V") == 5

    def test_subtractive(self):
        assert roman_to_int("IV") == 4

    def test_vii(self):
        assert roman_to_int("VII") == 7

    def test_nonsense(self):
        assert roman_to_int("XYZ") is None


class TestDaySections:
    def test_reads_every_slot(self):
        slots, warnings = parse_day_section_timetable([DAY_SECTION_TABLE])
        assert warnings == []
        assert len(slots) == 13

    def test_days_come_from_the_section_markers(self):
        slots, _ = parse_day_section_timetable([DAY_SECTION_TABLE])
        assert {s["day"] for s in slots} == {"Mon", "Tue"}

    def test_times_come_from_the_header_row(self):
        slots, _ = parse_day_section_timetable([DAY_SECTION_TABLE])
        first = next(s for s in slots if s["course_code"] == "NS1002")
        assert first["start_time"] == time(9, 0)
        assert first["end_time"] == time(9, 55)

    def test_semester_bands_apply_to_the_rows_under_them(self):
        slots, _ = parse_day_section_timetable([DAY_SECTION_TABLE])
        assert {s["semester"] for s in slots if s["day"] == "Mon"} == {1, 5}

    def test_blank_leading_cell_continues_the_branch(self):
        """Group B has no branch of its own; it belongs to CSE above it."""
        slots, _ = parse_day_section_timetable([DAY_SECTION_TABLE])
        b_rows = [s for s in slots if s["instructor"] == "YSK"]
        assert b_rows and all(s["branch_or_program"] == "CSE" for s in b_rows)

    def test_the_other_branch_is_not_merged_in(self):
        slots, _ = parse_day_section_timetable([DAY_SECTION_TABLE])
        ece = [s for s in slots if s["branch_or_program"] == "ECE"]
        assert ece and all(s["course_code"].startswith(("HS", "NS", "EC")) for s in ece)

    def test_title_row_is_not_read_as_a_branch(self):
        slots, _ = parse_day_section_timetable([DAY_SECTION_TABLE])
        assert not any("Time Table" in s["branch_or_program"] for s in slots)


class TestPackedCells:
    def test_course_instructor_room(self):
        slots, _ = parse_day_section_timetable([DAY_SECTION_TABLE])
        entry = next(s for s in slots if s["course_code"] == "NS1002")
        assert entry["instructor"] == "MKR"
        assert entry["room"] == "L-102"

    def test_spaced_course_code(self):
        """The grid writes "HS 1001 -MA- L106" with spaces."""
        slots, _ = parse_day_section_timetable([DAY_SECTION_TABLE])
        entry = next(s for s in slots if s["course_code"].startswith("HS1001"))
        assert entry["instructor"] == "MA"
        assert entry["room"] == "L-106"

    def test_lab_course_code_keeps_its_trailing_letter(self):
        """'CS3010L' is a lab paper, not a room that swallowed the code."""
        slots, _ = parse_day_section_timetable([DAY_SECTION_TABLE])
        entry = next(s for s in slots if s["room"] == "CC-3F")
        assert entry["course_code"] == "CS3010L"
        assert entry["instructor"] == "AG"

    def test_group_label_and_several_papers_in_one_cell(self):
        """'OE3: CS8016-BiG (VF)-L107 OE4L01-VF-L202' is two papers."""
        slots, _ = parse_day_section_timetable([DAY_SECTION_TABLE])
        # Selected by room, not by instructor: "VF" means visiting faculty, which
        # is a category of teacher rather than a name and is now stored empty.
        tuesday = [s for s in slots if s["day"] == "Tue" and s["room"] in ("L-107", "L-202")]
        codes = {s["course_code"] for s in tuesday}
        assert "CS8016" in codes
        assert "OE4L01" in codes

    def test_visiting_faculty_is_kept_as_the_teacher(self):
        """
        "VF" means visiting faculty, and for those cells the document names
        nobody. Blanking it to a dash would lose that, so it is stored.

        A report grouped by lecturer must still skip it - that is the frontend's
        ``instructorFor``, not the parser's job.
        """
        slots, _ = parse_day_section_timetable([DAY_SECTION_TABLE])
        oe4l01 = next(s for s in slots if s["course_code"] == "OE4L01")
        assert oe4l01["instructor"] == "VF"


class TestCellSplitting:
    def test_single_entry(self):
        assert _split_cell_entries("CS3010L-AG-CC-3F") == ["CS3010L-AG-CC-3F"]

    def test_group_label_is_stripped(self):
        entries = _split_cell_entries("OE3: CS8016-BiG-L107 OE4L01-VF-L202")
        assert entries == ["CS8016-BiG-L107", "OE4L01-VF-L202"]

    def test_newline_separated(self):
        entries = _split_cell_entries("CS8016-BiG-L107\nOE4L01-VF-L202")
        assert entries == ["CS8016-BiG-L107", "OE4L01-VF-L202"]

    def test_empty_markers(self):
        assert _split_cell_entries("-") == []
        assert _split_cell_entries("NA") == []
        assert _split_cell_entries("") == []


class TestDegenerateInput:
    def test_empty_table(self):
        slots, warnings = parse_day_section_timetable([[]])
        assert slots == []
        assert warnings

    def test_table_without_a_day_section(self):
        slots, _ = parse_day_section_timetable([["Time/Day", "Group", "9:00-9:55"]])
        assert slots == []

    @pytest.mark.parametrize("row", [["Monday"], ["Tuesday", "x"]])
    def test_day_marker_without_a_time_header_yields_nothing(self, row):
        slots, _ = parse_day_section_timetable([[*row], ["CSE", "A", "CS5031-SKC-L202"]])
        assert slots == []
