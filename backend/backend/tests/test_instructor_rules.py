"""
Tests for reading a teacher out of a packed timetable cell.

The grid writes a class and everything *about* it into one cell, and only the
initials are the teacher: "ME3010L-MZA-Batch A-CPPS Lab" is MZA, "EC5C01_MDB-"
is MDB, "ME2003-T SDP-CR202" is SDP. Getting these wrong used to cost the whole
instructor, because a trailing qualifier failed the name check and the entire
leftover was discarded.

Each test names the shape it is protecting, so a future change to the salvage
rules has to argue with a real cell from the published timetable.
"""
import pytest

from features.timetable.parser import _resolve_instructor, split_slot_cell


class TestSalvage:
    """The name is written first; the tail is noise and must not cost it."""

    @pytest.mark.parametrize(
        "cell,course,instructor",
        [
            ("ME3010L-MZA-Batch A-CPPS Lab", "ME3010L", "MZA"),
            ("SM3010L-ARR-Batch A -CC2- GF", "SM3010L", "ARR"),
            ("ME3011L-SKC-Batch A - HMT Lab", "ME3011L", "SKC"),
            ("SM3012L-Batch A-SA-CPPS Lab", "SM3012L", "SA"),
            ("SM2002L-Batch A-KP-Workshop", "SM2002L", "KP"),
            ("SM3011L-Batch A -TS-CPPS Lab", "SM3011L", "TS"),
            ("ME2002L-MS-Batch A-Workshop", "ME2002L", "MS"),
            ("SM3009L-KP-Batch B -AMP Lab", "SM3009L", "KP"),
        ],
    )
    def test_batch_and_venue_words_do_not_cost_the_teacher(self, cell, course, instructor):
        assert split_slot_cell(cell)[:2] == (course, instructor)

    def test_a_slash_joined_cell_keeps_its_teacher(self):
        # "EC204a/EC204b" is two papers; only one becomes the course code, and the
        # other must not be mistaken for a person.
        course, instructor, room = split_slot_cell("EC204a/EC204b-PR/KD/SNS-L201")
        assert course == "EC204A"
        assert instructor == "PR KD SNS"
        assert room == "L-201"

    def test_an_extra_marker_does_not_cost_the_teacher(self):
        assert split_slot_cell("HS 1001- MA- L206 (Extra)")[:2] == ("HS1001", "MA")

    def test_a_venue_only_cell_drops_the_venue_not_the_teacher(self):
        assert split_slot_cell("OE2D11:PT: Lab: Design Studio")[:2] == ("OE2D11", "PT")


class TestWeldedCodes:
    """A code and its teacher with nothing between them."""

    def test_underscore_separates_code_and_initials(self):
        assert split_slot_cell("EC5C01_MDB-")[:2] == ("EC5C01", "MDB")

    def test_trailing_initials_are_not_part_of_the_code(self):
        assert split_slot_cell("ME8016HSN-CR107")[:3] == ("ME8016", "HSN", "CR-107")

    def test_a_lab_suffix_stays_with_the_code(self):
        """"CS3010L" is a lab paper, not a code plus initials."""
        course, instructor, _room = split_slot_cell("CS3010L-AG-CC-3F")
        assert course == "CS3010L"
        assert instructor == "AG"


class TestOnePersonOneSpelling:
    """The same teacher is written several ways; they must collapse."""

    def test_a_teaching_assistant_prefix_is_dropped(self):
        assert split_slot_cell("ME2003-T SDP-CR202")[1] == "SDP"

    def test_a_batch_letter_suffix_is_dropped(self):
        assert split_slot_cell("IT2002L-JKT O-L102")[1] == "JKT"

    def test_the_same_name_reads_the_same_both_ways(self):
        with_prefix = split_slot_cell("ME2003-T SDP-CR202")[1]
        without = split_slot_cell("ME2003-SDP-CR202")[1]
        assert with_prefix == without == "SDP"


class TestNotAPerson:
    """Categories and placeholders are not people."""

    def test_a_venue_label_is_not_a_teacher(self):
        """'LAB' describes the class; the code already says so with its L."""
        _course, instructor, _room = split_slot_cell("ES1003:LAB: AUDITORIUM")
        assert instructor in ("", None)

    @pytest.mark.parametrize(
        "cell", ["IT2002-VF-L201", "HS3004-VF-L107", "OE4L01-VF-L202"]
    )
    def test_visiting_faculty_is_stored_because_it_is_all_there_is(self, cell):
        """
        'VF' is the document's only answer for those cells.

        Blanking it would show a student and an admin report the same thing for
        "no name given" and "taught by visiting faculty". Kept, and skipped only
        where people are counted (the frontend's instructorFor).
        """
        _course, instructor, _room = split_slot_cell(cell)
        assert instructor == "VF"

    def test_a_garbled_cell_yields_no_teacher(self):
        assert split_slot_cell("EC5M03-MAKE-5")[1] in ("", None)

    def test_resolve_handles_no_input(self):
        assert _resolve_instructor([], "CS3009") == ""
        assert _resolve_instructor(["A", "B"], "") == "A B"


class TestStillCorrect:
    """The ordinary shapes must not regress."""

    @pytest.mark.parametrize(
        "cell,course,instructor",
        [
            ("NS1002-MKR-L102", "NS1002", "MKR"),
            ("HS 1001 -MA- L106", "HS1001", "MA"),
            ("OE3E33-SKC-L202", "OE3E33", "SKC"),
            ("EC5C01-SKC-L102", "EC5C01", "SKC"),
            ("IT2001-SKM-CC-3F", "IT2001", "SKM"),
            ("CS8028-NA-CC 2F", "CS8028", "NA"),
            ("CS8007-AnS (VF)-L107", "CS8007", "AnS"),
            ("ME3001-SKC-CR-208", "ME3001", "SKC"),
            ("EC203a/EC203b-SKT-L201", "EC203A", "SKT"),
        ],
    )
    def test_unchanged(self, cell, course, instructor):
        assert split_slot_cell(cell)[:2] == (course, instructor)
