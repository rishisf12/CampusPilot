"""Unit tests for roll number parsing (exam seating)."""
import pytest
import re


def parse_roll(roll: str) -> tuple[str, int]:
    """Split roll like '23BCS003' -> ('23BCS', 3)."""
    match = re.match(r"^(.*[A-Za-z])(\d+)$", roll.strip())
    if not match:
        raise ValueError(f"Invalid roll format: {roll}")
    prefix = match.group(1).upper()
    num = int(match.group(2))
    return prefix, num


def roll_in_range(roll: str, start_prefix: str, start_num: int, end_num: int) -> bool:
    """Check if roll falls in [start_num, end_num] with same prefix."""
    prefix, num = parse_roll(roll)
    if prefix != start_prefix.upper():
        return False
    return start_num <= num <= end_num


def parse_roll_range(range_str: str) -> tuple[str, int, int]:
    """Parse '23BCS003 to 23BCS291' or '23BCS003-23BCS291'."""
    normalized = range_str.replace(" to ", "-").replace(" TO ", "-").replace(" To ", "-").replace("–", "-")
    parts = normalized.split("-")
    if len(parts) != 2:
        raise ValueError(f"Invalid range format: {range_str}")

    start_prefix, start_num = parse_roll(parts[0].strip())
    end_prefix, end_num = parse_roll(parts[1].strip())

    if start_prefix != end_prefix:
        raise ValueError(f"Prefix mismatch in range: {range_str}")

    if start_num > end_num:
        raise ValueError(f"Start > end in range: {range_str}")

    return start_prefix, start_num, end_num


class TestParseRoll:
    def test_standard(self):
        assert parse_roll("23BCS003") == ("23BCS", 3)

    def test_no_leading_zeros(self):
        assert parse_roll("23BCS3") == ("23BCS", 3)

    def test_longer_prefix(self):
        assert parse_roll("2023MTECHAI001") == ("2023MTECHAI", 1)

    def test_invalid(self):
        with pytest.raises(ValueError):
            parse_roll("ABC")
        with pytest.raises(ValueError):
            parse_roll("123")


class TestRollInRange:
    def test_in_range(self):
        assert roll_in_range("23BCS050", "23BCS", 1, 100) is True

    def test_at_boundaries(self):
        assert roll_in_range("23BCS001", "23BCS", 1, 100) is True
        assert roll_in_range("23BCS100", "23BCS", 1, 100) is True

    def test_out_of_range(self):
        assert roll_in_range("23BCS101", "23BCS", 1, 100) is False
        assert roll_in_range("23BCS000", "23BCS", 1, 100) is False

    def test_wrong_prefix(self):
        assert roll_in_range("23BEC050", "23BCS", 1, 100) is False

    def test_case_insensitive(self):
        assert roll_in_range("23bcs050", "23BCS", 1, 100) is True


def parse_roll_range(range_str: str) -> tuple[str, int, int]:
    """Parse '23BCS003 to 23BCS291' or '23BCS003-23BCS291'."""
    normalized = range_str.replace(" to ", "-").replace(" TO ", "-").replace(" To ", "-")
    parts = normalized.split("-")
    if len(parts) != 2:
        raise ValueError(f"Invalid range format: {range_str}")

    start_prefix, start_num = parse_roll(parts[0].strip())
    end_prefix, end_num = parse_roll(parts[1].strip())

    if start_prefix != end_prefix:
        raise ValueError(f"Prefix mismatch in range: {range_str}")

    if start_num > end_num:
        raise ValueError(f"Start > end in range: {range_str}")

    return start_prefix, start_num, end_num


class TestParseRollRange:
    def test_with_to(self):
        assert parse_roll_range("23BCS003 to 23BCS291") == ("23BCS", 3, 291)

    def test_with_dash(self):
        assert parse_roll_range("23BCS003-23BCS291") == ("23BCS", 3, 291)

    def test_mixed_case(self):
        assert parse_roll_range("23BCS003 TO 23BCS291") == ("23BCS", 3, 291)

    def test_invalid_prefix_mismatch(self):
        with pytest.raises(ValueError):
            parse_roll_range("23BCS003-23BEC291")

    def test_invalid_order(self):
        with pytest.raises(ValueError):
            parse_roll_range("23BCS291-23BCS003")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])