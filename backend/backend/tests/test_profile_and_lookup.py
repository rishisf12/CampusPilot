"""Unit tests for profile normalisation and the three-rule exam lookup."""
import pytest
from datetime import date, time

from features.exam.lookup import is_continuous_range_dict
from features.profile.service import profile_to_filter
from models import UserProfile


def make_profile(**overrides):
    defaults = {
        "user_id": 1,
        "programme": "BTech",
        "semester": 5,
        "branch": "CSE A",
        "elective_codes": [],
    }
    defaults.update(overrides)
    return UserProfile(id=1, **defaults)


class TestProfileToFilter:
    def test_normalises_the_branch(self):
        assert profile_to_filter(make_profile(branch="cse b"))["branch"] == "CSE B"

    def test_keeps_elective_codes_as_a_list(self):
        profile = make_profile(elective_codes=["OE3E33", "oe4m76"])
        assert profile_to_filter(profile)["elective_codes"] == ["OE3E33", "oe4m76"]

    def test_none_profile_returns_defaults(self):
        result = profile_to_filter(None)
        assert result["branch"] == "CSE A"
        assert result["semester"] == 1

    def test_exposes_branch_change_state(self):
        profile = make_profile(
            original_branch="CSE A",
            branch_change_requested=True,
            requested_branch="ECE",
        )
        result = profile_to_filter(profile)
        assert result["original_branch"] == "CSE A"
        assert result["branch_change_requested"] is True
        assert result["requested_branch"] == "ECE"


class TestContinuousRange:
    """Rule 2 only applies to unbroken ranges."""

    def test_typical_range(self):
        assert is_continuous_range_dict({"roll_start_num": 3, "roll_end_num": 109}) is True

    def test_single_roll_counts(self):
        assert is_continuous_range_dict({"roll_start_num": 294, "roll_end_num": 294}) is True

    def test_implausibly_wide_range_is_not_continuous(self):
        """A 3000-student span is a scattered list, not a hall allocation."""
        assert is_continuous_range_dict({"roll_start_num": 1, "roll_end_num": 3000}) is False

    def test_missing_bounds(self):
        assert is_continuous_range_dict({"roll_start_num": None, "roll_end_num": None}) is False


@pytest.mark.parametrize(
    "roll,expected",
    [
        ("23BCS125", ("23BCS", 125)),
        ("26bds001", ("26BDS", 1)),
        ("25MECV02", ("25MECV", 2)),
    ],
)
def test_roll_prefix_split(roll, expected):
    from features.exam.parser import parse_roll

    assert parse_roll(roll) == expected


def test_date_and_time_column_names_are_used_by_the_models():
    """The lookup reads ``seating_date``; the old ``exam_date`` name must be gone."""
    from models import ExamSeating, MidSemSchedule

    assert "seating_date" in ExamSeating.model_fields
    assert "exam_date" not in ExamSeating.model_fields
    assert "schedule_date" in MidSemSchedule.model_fields
    assert isinstance(date(2026, 9, 21), date)
    assert isinstance(time(8, 0), time)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])