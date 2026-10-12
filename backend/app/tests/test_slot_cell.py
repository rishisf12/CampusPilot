"""
Tests for splitting a timetable cell into course, instructor and room.

Cells in the college timetable pack the three fields together with a separator
that is not consistent across the document - ``ME3001-SKC-CR208``,
``CS5031:SKC:CR208``, ``CS5031 | R.K.S | L-202`` and plain whitespace all occur.
The dash is the awkward one, because it is both a field separator and part of a
room (``CR-208``).

These cases lock in the behaviour that was hard-won: a room is never mistaken
for a course, an elective keeps its ``OE`` prefix, and a missing field does not
drag its neighbour in with it.
"""
from features.timetable.parser import _is_course, _is_room, split_slot_cell


class TestSeparators:
    def test_dash_separated(self):
        assert split_slot_cell("ME3001-SKC-CR208") == ("ME3001", "SKC", "CR-208")

    def test_colon_separated(self):
        assert split_slot_cell("CS5031:SKC:CR208") == ("CS5031", "SKC", "CR-208")

    def test_pipe_separated_with_dotted_initials(self):
        assert split_slot_cell("CS5031 | R.K.S | L-202") == ("CS5031", "R.K.S", "L-202")

    def test_slash_separated(self):
        assert split_slot_cell("ME3001/SKC/CR-208") == ("ME3001", "SKC", "CR-208")

    def test_whitespace_separated(self):
        assert split_slot_cell("ME3001 SKC CR208") == ("ME3001", "SKC", "CR-208")

    def test_surrounding_whitespace_is_ignored(self):
        assert split_slot_cell("  ME3001 - SKC - CR208  ") == ("ME3001", "SKC", "CR-208")

    def test_empty_cell(self):
        assert split_slot_cell("") == ("", "", "")


class TestRoomsKeepTheirDash:
    def test_room_keeps_internal_dash(self):
        """'CR-208' is one room, not a course, a stray 'CR' and a stray '208'."""
        code, _, room = split_slot_cell("CS5031-SKC-CR-108")
        assert room == "CR-108"
        assert code == "CS5031"

    def test_room_without_dash_is_still_a_room(self):
        assert split_slot_cell("HS1001-AM-L104")[2] == "L-104"

    def test_room_only_cell_has_no_course(self):
        assert split_slot_cell("CR208") == ("", "", "CR-208")


class TestCourseShapes:
    def test_regular_course(self):
        assert split_slot_cell("ME3001-SKC-CR208")[0] == "ME3001"

    def test_open_elective_keeps_prefix(self):
        """The OE prefix is the only thing marking it as an elective."""
        assert split_slot_cell("OE3E33-SKC-L202")[0] == "OE3E33"

    def test_letter_inside_the_number(self):
        """'EC5C01' is ECE, not a room."""
        assert split_slot_cell("EC5C01-SKC-L102")[0] == "EC5C01"

    def test_course_code_only(self):
        assert split_slot_cell("CS5031") == ("CS5031", "", "")

    def test_rooms_are_never_courses(self):
        for token in ("L202", "CR208", "AB12", "CR-208", "L-202"):
            assert _is_room(token), token
            assert not _is_course(token), token

    def test_courses_are_never_rooms(self):
        for token in ("CS5031", "ME3001", "OE3E33", "EC5C01", "SM3012"):
            assert _is_course(token), token
            assert not _is_room(token), token


class TestMissingFields:
    def test_instructor_missing_keeps_the_room(self):
        """'ME3001/L-202' must not leave 'L' behind as a bogus instructor."""
        code, instructor, room = split_slot_cell("ME3001/L-202")
        assert code == "ME3001"
        assert room == "L-202"
        assert instructor == ""

    def test_room_missing_keeps_the_instructor(self):
        assert split_slot_cell("CS5031-SKC") == ("CS5031", "SKC", "")

    def test_both_missing(self):
        assert split_slot_cell("CS5031-SKC-L202")[1] == "SKC"


class TestCourseCodeOnlyCell:
    def test_lone_token_is_the_course(self):
        assert split_slot_cell("ME3001")[0] == "ME3001"

    def test_placeholder_is_not_treated_as_a_course(self):
        """
        A cell the parser does not understand should not be invented into a
        course code. The grid parser skips cells with no usable course.
        """
        code, _, _ = split_slot_cell("TBA")
        assert code == ""
