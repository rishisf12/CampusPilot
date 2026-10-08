"""Unit tests for the exam parser building blocks and branch inference."""
import pytest
from datetime import date, time

from features.exam.parser import (
    branch_matches,
    exam_row_visible,
    extract_roll_tokens,
    infer_branch_from_course,
    infer_branch_from_roll,
    infer_semester_from_course,
    is_open_elective,
    normalize_branch,
    parse_human_date,
    parse_meridiem_time,
    parse_semester_label,
    parse_slot_range,
    parse_weekday,
    roll_tokens_to_ranges,
    split_course_codes,
)


class TestParseMeridiemTime:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("08:00 AM", time(8, 0)),
            ("10.30AM", time(10, 30)),
            ("3:30PM", time(15, 30)),
            ("12:00 AM", time(0, 0)),
            ("12:30 PM", time(12, 30)),
            ("14:00", time(14, 0)),
            ("05:45 pm", time(17, 45)),
        ],
    )
    def test_parses(self, raw, expected):
        assert parse_meridiem_time(raw) == expected

    @pytest.mark.parametrize("raw", ["", "abc", "25:00", "10:99"])
    def test_rejects(self, raw):
        assert parse_meridiem_time(raw) is None


class TestParseSlotRange:
    def test_both_meridiems(self):
        assert parse_slot_range("10.30AM-12.30PM") == (time(10, 30), time(12, 30))

    def test_only_closing_meridiem_is_pm(self):
        """"3.30-5.30pm" means 15:30-17:30, not 03:30."""
        assert parse_slot_range("3.30-5.30pm") == (time(15, 30), time(17, 30))

    def test_only_closing_meridiem_is_am(self):
        """"11.30-1.30am" is 12-hour shorthand, so the end rolls past noon."""
        assert parse_slot_range("11.30-1.30am") == (time(11, 30), time(13, 30))

    def test_impossible_range_is_discarded(self):
        """Garbled text must not produce a start later than the end."""
        assert parse_slot_range("22.30-12.30PM") == (None, None)

    def test_empty(self):
        assert parse_slot_range("") == (None, None)


class TestParseHumanDate:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("21.09.2026(Monday)", date(2026, 9, 21)),
            ("29th Sept 2025", date(2025, 9, 29)),
            ("29 Sept 2025 Monday", date(2025, 9, 29)),
            ("6th Oct 2025", date(2025, 10, 6)),
            ("2025-10-06", date(2025, 10, 6)),
        ],
    )
    def test_parses(self, raw, expected):
        assert parse_human_date(raw) == expected

    def test_unparseable(self):
        assert parse_human_date("not a date") is None

    def test_weekday(self):
        assert parse_weekday("21.09.2026(Monday)") == "Monday"
        assert parse_weekday("29th Sept 2025 Tuesday") == "Tuesday"
        assert parse_weekday("no day") is None


class TestSplitCourseCodes:
    def test_batch_suffix_is_stripped(self):
        assert split_course_codes("NS1001 (Batch-A)") == ["NS1001"]

    def test_slash_split(self):
        assert split_course_codes("CS8031/CS8032") == ["CS8031", "CS8032"]

    def test_space_split_and_dedupe(self):
        assert split_course_codes("CS8037 CS8037") == ["CS8037"]

    def test_room_codes_are_ignored(self):
        """"CR103" is a hall, not a course."""
        assert split_course_codes("CR103") == []

    def test_mid_sem_codes(self):
        assert split_course_codes("EC5M03") == ["EC5M03"]

    def test_empty(self):
        assert split_course_codes("") == []


class TestRollTokens:
    def test_range(self):
        assert extract_roll_tokens("26BCS042 to 26BCS113") == ["26BCS042", "26BCS113"]

    def test_comma_list(self):
        assert extract_roll_tokens("23BCS125, 23BCS197, 23BCS294") == [
            "23BCS125",
            "23BCS197",
            "23BCS294",
        ]

    def test_pairs_into_ranges(self):
        assert roll_tokens_to_ranges(["26BCS042", "26BCS113"]) == [("26BCS", 42, 113)]

    def test_unpaired_token_becomes_single_roll(self):
        assert roll_tokens_to_ranges(["23BCS294"]) == [("23BCS", 294, 294)]

    def test_swapped_bounds_are_repaired(self):
        assert roll_tokens_to_ranges(["26BCS113", "26BCS042"]) == [("26BCS", 42, 113)]


class TestBranchInference:
    def test_odd_roll_is_section_a(self):
        assert infer_branch_from_roll("23BCS125") == "CSE A"

    def test_even_roll_is_section_b(self):
        assert infer_branch_from_roll("23BCS126") == "CSE B"

    @pytest.mark.parametrize(
        "roll,expected",
        [
            ("23BEC045", "ECE"),
            ("23BME010", "ME"),
            ("23BSM020", "SM"),
            ("26BDS001", "DS A"),
            ("23BCS999", "CSE A"),
        ],
    )
    def test_families(self, roll, expected):
        assert infer_branch_from_roll(roll) == expected

    def test_unknown_prefix(self):
        assert infer_branch_from_roll("23ZZZ001") is None

    def test_invalid_roll(self):
        assert infer_branch_from_roll("nonsense") is None

    def test_from_course(self):
        assert infer_branch_from_course("CS8036") == "CSE"
        assert infer_branch_from_course("EC5M03") == "ECE"
        assert infer_branch_from_course("OE3E33") is None


class TestSemesterInference:
    @pytest.mark.parametrize(
        "code,expected",
        [("CS8036", 8), ("CS3009", 3), ("DS1002", 1), ("ME3011", 3)],
    )
    def test_from_course(self, code, expected):
        assert infer_semester_from_course(code) == expected

    @pytest.mark.parametrize(
        "label,expected",
        [("Sem 5", 5), ("Sem-7", 7), ("PG/PhD", 9), ("3rd Sem", 3), ("", None)],
    )
    def test_from_label(self, label, expected):
        assert parse_semester_label(label) == expected


class TestNormalizeBranch:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("CSE A", "CSE A"),
            ("cse b", "CSE B"),
            ("BTech CSE", "CSE A"),
            ("BDS", "DS"),
            ("BTech ECE", "ECE"),
            ("MTech", "PG"),
            ("MDes", "MDes"),
            ("", None),
            ("unknown", None),
        ],
    )
    def test_normalizes(self, raw, expected):
        assert normalize_branch(raw) == expected


class TestExamRowVisible:
    """Rule 1: the filter stays in sync with the student's profile."""

    # Use tuple to avoid mutable class attribute (RUF012)
    profile = (("branch", "CSE A"), ("semester", 5), ("elective_codes", []))

    def _as_dict(self):
        return dict(self.profile)

    def test_same_branch_and_semester(self):
        assert exam_row_visible({"branch": "CSE", "semester": 5, "course_code": "CS5031"}, self._as_dict())

    def test_other_branch_is_hidden(self):
        assert not exam_row_visible({"branch": "ME", "semester": 5, "course_code": "ME5011"}, self._as_dict())

    def test_other_semester_is_hidden(self):
        assert not exam_row_visible({"branch": "CSE", "semester": 7, "course_code": "CS7036"}, self._as_dict())

    def test_pg_row_is_visible_to_a_pg_student(self):
        """Semester 9 marks PG/PhD rows, which are not tied to a BTech semester."""
        pg_profile = {"branch": "PG", "semester": 9, "elective_codes": []}
        assert exam_row_visible({"branch": "PG", "semester": 9, "course_code": "MT5003"}, pg_profile)

    def test_pg_row_is_hidden_from_a_cse_student(self):
        """...but a CSE student must not see PG papers."""
        assert not exam_row_visible(
            {"branch": "PG", "semester": 9, "course_code": "MT5003"}, self._as_dict()
        )

    def test_open_elective_is_always_visible(self):
        assert exam_row_visible({"branch": None, "semester": None, "course_code": "OE3E33"}, self._as_dict())

    def test_elected_course_is_visible_across_branches(self):
        profile = {"branch": "CSE A", "semester": 5, "elective_codes": ["OE3E33"]}
        assert exam_row_visible({"branch": "ME", "semester": 5, "course_code": "OE3E33"}, profile)

    def test_no_profile_shows_everything(self):
        assert exam_row_visible({"branch": "ME", "semester": 7, "course_code": "ME7011"}, None)

    def test_missing_metadata_shows_everything(self):
        assert exam_row_visible({"branch": None, "semester": None, "course_code": "NS1001"}, self._as_dict())


class TestBranchMatches:
    def test_family_match_across_sections(self):
        assert branch_matches("CSE", "CSE A")

    def test_different_families(self):
        assert not branch_matches("ME", "CSE A")

    def test_unknown_on_either_side(self):
        assert branch_matches(None, "CSE A")
        assert branch_matches("CSE A", None)

    def test_pg_does_not_match_cse(self):
        assert not branch_matches("PG", "CSE A")


def test_is_open_elective():
    assert is_open_elective("OE3E33")
    assert not is_open_elective("CS8036")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])