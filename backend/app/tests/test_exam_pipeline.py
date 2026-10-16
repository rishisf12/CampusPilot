"""Unit tests for the exam pipeline: Excel parsing, slot listing, options, and debug endpoint parser selection.

These tests exercise pure parser functions and do not require PostgreSQL,
so they can run without a test database (unlike the route/integration tests
which need TEST_DATABASE_URL).
"""
import pytest
from datetime import date, time
from pathlib import Path
from unittest.mock import patch

from features.exam.parser import (
    _parse_excel_mid_sem_file,
    _parse_excel_seating_file,
    parse_mid_sem_file,
    parse_seating_index_file,
    parse_slot_range,
    parse_meridiem_time,
    split_course_codes,
    extract_roll_tokens,
    roll_tokens_to_ranges,
    is_open_elective,
    normalize_branch,
    branch_matches,
    exam_row_visible,
)


# ---------------------------------------------------------------------------
# Helper: fake openpyxl workbook
# ---------------------------------------------------------------------------

class FakeWS:
    def __init__(self, rows):
        self.rows = rows

    def iter_rows(self, **kwargs):
        min_row = kwargs.get("min_row", 1)
        if min_row > 1:
            return iter(self.rows[min_row - 1 :])
        return iter(self.rows)


class FakeWB:
    sheetnames = ["Sheet1"]

    def __init__(self, ws):
        self._ws = ws

    def __getitem__(self, key):
        return self._ws

    def close(self):
        pass


# ---------------------------------------------------------------------------
# Excel mid-sem timetable parsing
# ---------------------------------------------------------------------------

class TestParseExcelMidSemFile:
    """Test _parse_excel_mid_sem_file with a mocked openpyxl workbook."""

    def test_parses_valid_rows(self):
        rows = [
            ("date", "time", "course_code", "semester", "branch", "room"),
            ("2026-10-05", "10:00 AM - 11:00 AM", "CS5031", "5", "CSE A", "CR-101"),
            ("2026-10-06", "2.00PM-3.00PM", "ME3009", "5", "ME", "L-202"),
        ]
        ws = FakeWS(rows)
        wb = FakeWB(ws)
        with patch("openpyxl.load_workbook", return_value=wb):
            result = _parse_excel_mid_sem_file(Path("fake.xlsx"))

        assert result["stats"]["rows_parsed"] == 2
        assert result["rows"][0]["course_code"] == "CS5031"
        assert result["rows"][0]["semester"] == 5
        assert result["rows"][0]["branch"] == "CSE A"
        assert result["rows"][0]["room"] == "CR-101"
        assert result["rows"][0]["schedule_date"] == date(2026, 10, 5)
        assert result["rows"][0]["start_time"] == time(10, 0)
        assert result["rows"][0]["end_time"] == time(11, 0)
        assert result["rows"][0]["is_extra"] is False

        assert result["rows"][1]["course_code"] == "ME3009"
        assert result["rows"][1]["branch"] == "ME"

    def test_open_elective_marked_extra(self):
        rows = [
            ("date", "time", "course_code", "semester", "branch", "room"),
            ("2026-10-05", "10:00 AM - 11:00 AM", "OE3E33", "5", "", "CR-101"),
        ]
        ws = FakeWS(rows)
        wb = FakeWB(ws)
        with patch("openpyxl.load_workbook", return_value=wb):
            result = _parse_excel_mid_sem_file(Path("fake.xlsx"))

        assert result["rows"][0]["is_extra"] is True

    def test_slash_split_course_codes(self):
        rows = [
            ("date", "time", "course_code", "semester", "branch", "room"),
            ("2026-10-05", "10:00 AM - 11:00 AM", "CS5031/ME5D02", "5", "CSE A", "CR-101"),
        ]
        ws = FakeWS(rows)
        wb = FakeWB(ws)
        with patch("openpyxl.load_workbook", return_value=wb):
            result = _parse_excel_mid_sem_file(Path("fake.xlsx"))

        assert result["stats"]["rows_parsed"] == 2
        codes = {r["course_code"] for r in result["rows"]}
        assert codes == {"CS5031", "ME5D02"}

    def test_missing_header_row(self):
        rows = [("foo", "bar"), ("1", "2")]
        ws = FakeWS(rows)
        wb = FakeWB(ws)
        with patch("openpyxl.load_workbook", return_value=wb):
            result = _parse_excel_mid_sem_file(Path("fake.xlsx"))

        assert result["rows"] == []
        assert "Could not find header row" in result["warnings"][0]

    def test_load_failure(self):
        with patch("openpyxl.load_workbook", side_effect=OSError("bad file")):
            result = _parse_excel_mid_sem_file(Path("bad.xlsx"))

        assert result["rows"] == []
        assert "Failed to open Excel file" in result["warnings"][0]


# ---------------------------------------------------------------------------
# Excel seating index parsing
# ---------------------------------------------------------------------------

class TestParseExcelSeatingFile:
    """Test _parse_excel_seating_file with a mocked openpyxl workbook."""

    def test_parses_valid_rows(self):
        rows = [
            ("roll_range", "room", "date", "time", "course_code", "branch", "semester"),
            ("23BCS001 to 23BCS050", "CR-101", "2026-10-10", "9:00 AM - 11:00 AM", "CS5031", "CSE A", "5"),
        ]
        ws = FakeWS(rows)
        wb = FakeWB(ws)
        with patch("openpyxl.load_workbook", return_value=wb):
            result = _parse_excel_seating_file(Path("fake.xlsx"))

        assert result["stats"]["rows_parsed"] == 1
        row = result["rows"][0]
        assert row["roll_start_prefix"] == "23BCS"
        assert row["roll_start_num"] == 1
        assert row["roll_end_num"] == 50
        assert row["room"] == "CR-101"
        assert row["course_code"] == "CS5031"
        assert row["branch"] == "CSE A"
        assert row["semester"] == 5
        assert row["seating_date"] == date(2026, 10, 10)
        assert row["start_time"] == time(9, 0)
        assert row["end_time"] == time(11, 0)
        assert row["is_extra"] is False

    def test_open_elective_marked_extra(self):
        rows = [
            ("roll_range", "room", "date", "time", "course_code", "branch", "semester"),
            ("23BCS001 to 23BCS050", "CR-101", "2026-10-10", "9:00 AM - 11:00 AM", "OE3E33", "", "5"),
        ]
        ws = FakeWS(rows)
        wb = FakeWB(ws)
        with patch("openpyxl.load_workbook", return_value=wb):
            result = _parse_excel_seating_file(Path("fake.xlsx"))

        assert result["rows"][0]["is_extra"] is True

    def test_multiple_roll_ranges_per_row(self):
        rows = [
            ("roll_range", "room", "date", "time", "course_code", "branch", "semester"),
            ("23BCS001, 23BCS050, 23BCS100, 23BCS150", "CR-101", "2026-10-10", "9:00 AM - 11:00 AM", "CS5031", "CSE A", "5"),
        ]
        ws = FakeWS(rows)
        wb = FakeWB(ws)
        with patch("openpyxl.load_workbook", return_value=wb):
            result = _parse_excel_seating_file(Path("fake.xlsx"))

        assert result["stats"]["rows_parsed"] == 2
        ranges = {(r["roll_start_num"], r["roll_end_num"]) for r in result["rows"]}
        assert ranges == {(1, 50), (100, 150)}

    def test_load_failure(self):
        with patch("openpyxl.load_workbook", side_effect=OSError("bad file")):
            result = _parse_excel_seating_file(Path("bad.xlsx"))

        assert result["rows"] == []
        assert "Failed to open Excel file" in result["warnings"][0]


# ---------------------------------------------------------------------------
# parse_mid_sem_file / parse_seating_index_file dispatch to Excel
# ---------------------------------------------------------------------------

class TestParseFileDispatch:
    """Test that parse_*_file routes .xlsx to the Excel parsers."""

    def test_mid_sem_routes_to_excel(self):
        with patch(
            "features.exam.parser._parse_excel_mid_sem_file",
            return_value={"rows": [], "stats": {"rows_parsed": 0}},
        ) as mock_excel:
            parse_mid_sem_file(Path("timetable.xlsx"))
            mock_excel.assert_called_once()

    def test_seating_routes_to_excel(self):
        with patch(
            "features.exam.parser._parse_excel_seating_file",
            return_value={"rows": [], "stats": {"rows_parsed": 0}},
        ) as mock_excel:
            parse_seating_index_file(Path("seating.xlsx"))
            mock_excel.assert_called_once()


# ---------------------------------------------------------------------------
# Pure parser function regression tests (new edge cases)
# ---------------------------------------------------------------------------

class TestParseSlotRangeEdgeCases:
    def test_single_time_defaults_two_hours(self):
        start, end = parse_slot_range("10:00 AM")
        assert start == time(10, 0)
        assert end == time(12, 0)

    def test_garbled_impossible_range(self):
        assert parse_slot_range("22.30-12.30PM") == (None, None)

    def test_none_input(self):
        assert parse_slot_range(None) == (None, None)


class TestSplitCourseCodesEdgeCases:
    def test_mixed_case_preserved_upper(self):
        assert split_course_codes("cs5031") == ["CS5031"]

    def test_room_prefix_filtered(self):
        assert split_course_codes("CR103") == []
        assert split_course_codes("LH-201") == []

    def test_empty_after_cleanup(self):
        assert split_course_codes("   ") == []


class TestExtractRollTokensEdgeCases:
    def test_single_token(self):
        assert extract_roll_tokens("23BCS001") == ["23BCS001"]

    def test_no_tokens(self):
        assert extract_roll_tokens("") == []
        assert extract_roll_tokens("nonsense") == []


class TestRollTokensToRangesEdgeCases:
    def test_single_token_range(self):
        assert roll_tokens_to_ranges(["23BCS294"]) == [("23BCS", 294, 294)]

    def test_swapped_bounds(self):
        assert roll_tokens_to_ranges(["26BCS113", "26BCS042"]) == [("26BCS", 42, 113)]


class TestOpenElective:
    @pytest.mark.parametrize(
        "code,expected",
        [
            ("OE3E33", True),
            ("OE4M76", True),
            ("OI3E33", False),  # OI not in OE_PREFIXES
            ("CS5031", False),
            ("ME3009", False),
            ("", False),
        ],
    )
    def test_is_open_elective(self, code, expected):
        assert is_open_elective(code) == expected


class TestNormalizeBranch:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("CSE A", "CSE A"),
            ("cse b", "CSE B"),
            ("BTech CSE", "CSE A"),
            ("BDS", "DS"),
            ("MTech", "PG"),
            ("MDes", "MDes"),
            ("", None),
            ("unknown", None),
        ],
    )
    def test_normalizes(self, raw, expected):
        assert normalize_branch(raw) == expected


class TestBranchMatches:
    def test_family_match_across_sections(self):
        assert branch_matches("CSE", "CSE A")

    def test_different_families(self):
        assert not branch_matches("ME", "CSE A")

    def test_unknown_on_either_side(self):
        assert branch_matches(None, "CSE A")
        assert branch_matches("CSE A", None)


class TestExamRowVisible:
    profile = {"branch": "CSE A", "semester": 5, "elective_codes": []}

    def test_same_branch_and_semester(self):
        assert exam_row_visible(
            {"branch": "CSE", "semester": 5, "course_code": "CS5031"}, self.profile
        )

    def test_other_branch_is_hidden(self):
        assert not exam_row_visible(
            {"branch": "ME", "semester": 5, "course_code": "ME5011"}, self.profile
        )

    def test_other_semester_is_hidden(self):
        assert not exam_row_visible(
            {"branch": "CSE", "semester": 7, "course_code": "CS7036"}, self.profile
        )

    def test_open_elective_visible(self):
        assert exam_row_visible(
            {"branch": None, "semester": None, "course_code": "OE3E33"}, self.profile
        )

    def test_elected_course_visible(self):
        profile = {"branch": "CSE A", "semester": 5, "elective_codes": ["OE3E33"]}
        assert exam_row_visible(
            {"branch": "ME", "semester": 5, "course_code": "OE3E33"}, profile
        )

    def test_no_profile_shows_everything(self):
        assert exam_row_visible(
            {"branch": "ME", "semester": 7, "course_code": "ME7011"}, None
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
