"""
Tests for the room and instructor rules.

Every case here is a cell from the published timetable that the parser read
confidently and wrongly. A bad room is worse than no room - it sends a student to
the wrong building - so each one is pinned to what the grid actually said.

The disputed rooms that started this: "(C-1)", "(C-2)", "A-1", "B-1", "B-2",
"G-1", "G-2", "MAKE-5", "R-202", "SKJ-101", "AV-2F", "CC-2".
"""
import pytest

from features.timetable.parser import (
    _is_floor_token,
    _is_room,
    _is_room_token,
    split_slot_cell,
)


class TestGroupMarkers:
    """(C1), (C2) and (VF) describe the class, not where it meets."""

    def test_a_group_marker_is_not_a_room(self):
        course, instructor, room = split_slot_cell("IT2E01-SKT-CC-FF (C1)")
        assert (course, instructor, room) == ("IT2E01", "SKT", "CC-FF")

    def test_markers_are_stripped_before_anything_is_parsed(self):
        # The marker used to be the last token left over, so it became the room.
        for cell in ("IT2E01-SKT-L102 (C2)", "CS8013-VKJ (VF)-L202"):
            _course, _instructor, room = split_slot_cell(cell)
            assert not room.startswith("(")

    def test_two_papers_in_one_cell_lose_both_markers(self):
        course, _instructor, room = split_slot_cell(
            "EC2002L-TK-(C2) /IT2002-VF-CC-GF (C1)"
        )
        assert course == "EC2002L"
        assert room == "CC-GF"


class TestLabGroupsAreNotRooms:
    """A1, B1, B2, G1, G2 are lab groups in this document."""

    @pytest.mark.parametrize(
        "cell,code,instructor",
        [
            ("ES1002L-PKP-A1", "ES1002L", "PKP"),
            ("ES1002L-PR-B1", "ES1002L", "PR"),
            ("ES1002L-PR-B2", "ES1002L", "PR"),
            ("IT3E01-KD-G1", "IT3E01", "KD"),
            ("IT3E01-KD-G2", "IT3E01", "KD"),
        ],
    )
    def test_rejected_as_a_room_but_kept_as_the_instructor(self, cell, code, instructor):
        got_code, got_instructor, room = split_slot_cell(cell)
        assert got_code == code
        # The group label must not swallow the instructor either.
        assert got_instructor == instructor
        assert room == ""


class TestSpacedAndSwappedFields:
    def test_a_building_written_with_a_space_between_its_letters(self):
        # Was "R-202": the leading C was consumed as a course-code fragment.
        course, instructor, room = split_slot_cell("OE4L73-JAMF- C R 202")
        assert (course, instructor, room) == ("OE4L73", "JAMF", "CR-202")

    def test_an_instructor_followed_by_a_bare_number(self):
        # Was "SKJ-101", which swallowed the instructor and invented a building.
        course, instructor, room = split_slot_cell("OE4E21-SKJ- 101")
        assert (course, instructor, room) == ("OE4E21", "SKJ", "")

    def test_a_floor_written_before_its_building(self):
        # Was "AV-2F", using the instructor's initials as a building code.
        course, instructor, room = split_slot_cell("IT1002L-AV-2F-CC")
        assert (course, instructor, room) == ("IT1002L", "AV", "CC-2F")

    def test_a_trailing_floor_attaches_to_the_room(self):
        _course, instructor, room = split_slot_cell("SM3010L-ARR-Batch A -CC2- GF")
        assert room == "CC-2-GF"
        # "GF" is a floor, not a surname.
        assert "GF" not in instructor


class TestGarbledCells:
    def test_a_four_letter_prefix_is_not_a_building(self):
        # "MAKE5" fits letters-then-digits but names no building here.
        course, instructor, room = split_slot_cell("EC5M03-MAKE-5")
        assert course == "EC5M03"
        assert room == ""
        assert "MAKE" not in instructor

    def test_an_elective_group_label_is_not_a_room(self):
        # "OE3:" is a class label; left in, it becomes the room.
        assert not _is_room_token("OE3")
        assert not _is_room("OE3")


class TestRoomShapes:
    @pytest.mark.parametrize(
        "token",
        ["L102", "L-102", "CR104", "CR-104", "CC2", "CC-2", "CR-208", "B12"],
    )
    def test_accepted(self, token):
        assert _is_room(token)

    @pytest.mark.parametrize(
        "token",
        ["A1", "B1", "G1", "OE3", "MAKE5", "CS5031", "SKC", "CC", "101"],
    )
    def test_rejected(self, token):
        assert not _is_room(token)

    @pytest.mark.parametrize(
        "token",
        ["GF", "FF", "2F", "17F"],
    )
    def test_floors_are_recognised(self, token):
        assert _is_floor_token(token)

    def test_named_venues(self):
        assert _is_room_token("AUDITORIUM")

    def test_a_course_code_is_never_a_room(self):
        for code in ("CS5031", "ME3001", "OE3E33", "EC5C01", "CS3010L"):
            assert not _is_room(code), code

    def test_both_room_predicates_agree(self):
        """Two predicates with different limits is how A1 became a room."""
        for token in ("A1", "L102", "CR-104", "CC-2F", "OE3", "AUDITORIUM"):
            assert _is_room(token) == _is_room_token(token), token


class TestCoursesStillParse:
    """The room fixes must not cost a course code."""

    @pytest.mark.parametrize(
        "cell,code",
        [
            ("NS1002-MKR-L102", "NS1002"),
            ("HS 1001 -MA- L106", "HS1001"),
            ("OE3E33-SKC-L202", "OE3E33"),
            ("EC5C01-SKC-L102", "EC5C01"),
            ("IT2001-SKM-CC-3F", "IT2001"),
            ("CS8028-NA-CC 2F", "CS8028"),
            ("ME3001-SKC-CR-208", "ME3001"),
            ("CS3010L-AG-CC-3F", "CS3010L"),
            ("ES1003:LAB: AUDITORIUM", "ES1003"),
        ],
    )
    def test_course_code_survives(self, cell, code):
        assert split_slot_cell(cell)[0] == code

    @pytest.mark.parametrize(
        "cell,room",
        [
            ("CS8028-NA-CC 2F", "CC-2F"),
            ("IT2001-SKM-CC-3F", "CC-3F"),
            ("ME3001-SKC-CR-208", "CR-208"),
            ("CS8004-AO-CC-2F", "CC-2F"),
            ("EC5C01-SKC-L102", "L-102"),
            ("ES1003:LAB: AUDITORIUM", "AUDITORIUM"),
        ],
    )
    def test_room_survives(self, cell, room):
        assert split_slot_cell(cell)[2] == room


class TestInstructorNames:
    """Real surnames are written in mixed case and must not be thrown away."""

    @pytest.mark.parametrize(
        "cell,name",
        [
            ("CS8007-AnS (VF)-L107", "AnS"),
            ("OE3: CS8016-BiG (VF)-L107", "BiG"),
            ("CS3009-ShM-L104", "ShM"),
            ("CS2002-RKR-L206", "RKR"),
        ],
    )
    def test_kept(self, cell, name):
        assert split_slot_cell(cell)[1] == name

    def test_garbage_is_not_kept(self):
        # The name pattern was unanchored once, so "MAKE-5" matched on its first
        # letter alone and passed as a person.
        assert split_slot_cell("EC5M03-MAKE-5")[1] == ""
