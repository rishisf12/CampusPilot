"""The roll lookup and the exam timetable show the same papers.

The student's own courses decide the list. A paper they do not sit never
appears - an elective they never opted into is not their exam - and a paper
they do sit always does, even where the seating index has no block for their
roll: a missing hall is better than a missing exam.

The two screens read one list, so they cannot drift apart.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from core.database import engine
from features.auth.routes import create_access_token
from main import app
from models import ExamSeating, MidSemSchedule, TimetableSlot, User, UserProfile, UserRole

#: Codes the parser accepts (`[A-Z]{2,3}\d{1,4}`) that no other test file
#: could plausibly seed. The electives carry the ``OE`` prefix the parser
#: recognises, so "opted into" means something.
CORE_COURSE = "ZS4001"
SECOND_COURSE = "ZS4002"
ELECTIVE = "OE4003"
NOT_THEIRS = "OE4005"
FOREIGN_COURSE = "ZS4006"

SEEDED_CODES = (CORE_COURSE, SECOND_COURSE, ELECTIVE, NOT_THEIRS, FOREIGN_COURSE)

ROLL = "23BCS005"
EXAM_DATE = "2026-09-21"
NEXT_DAY = "2026-09-22"
THIRD_DAY = "2026-09-23"


@pytest.fixture
def anon_client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def student_headers():
    with Session(engine) as s:
        user = s.exec(select(User).where(User.username == "papers_student")).first()
        if user is None:
            user = User(
                email="papers_student@iiitdmj.ac.in",
                password_hash="x",
                full_name="papers_student",
                username="papers_student",
                roll_number=ROLL,
                is_email_verified=True,
                role=UserRole.STUDENT,
            )
            s.add(user)
            s.commit()
            s.refresh(user)
        user_id = user.id

        profile = s.exec(
            select(UserProfile).where(UserProfile.user_id == user_id)
        ).first()
        if profile is None:
            profile = UserProfile(user_id=user_id)
        profile.branch = "ME"
        profile.semester = 3
        profile.elective_codes = [ELECTIVE]
        s.add(profile)
        s.commit()
    return {"Authorization": f"Bearer {create_access_token(user_id, 'papers_student')}"}


@pytest.fixture(autouse=True)
def clean_seeded_rows():
    """The exam rows this file seeds, and nothing else, are removed after it."""
    yield
    with Session(engine) as s:
        s.exec(delete(ExamSeating).where(ExamSeating.course_code.in_(SEEDED_CODES)))
        s.exec(delete(MidSemSchedule).where(MidSemSchedule.course_code.in_(SEEDED_CODES)))
        s.exec(delete(TimetableSlot).where(TimetableSlot.course_code.in_(SEEDED_CODES)))
        s.commit()


def _seed_subject_slots():
    """The regular timetable: it is what gives the student their courses."""
    from datetime import time as time_type

    with Session(engine) as s:
        # The electives are in the timetable too: a course the student never
        # opted into is not theirs even when the timetable lists it.
        for code in (CORE_COURSE, SECOND_COURSE, ELECTIVE, NOT_THEIRS):
            s.add(
                TimetableSlot(
                    day="Mon",
                    start_time=time_type(9, 0),
                    end_time=time_type(9, 55),
                    room="L-1",
                    course_code=code,
                    instructor="AM",
                    branch_or_program="ME",
                    semester=3,
                )
            )
        s.commit()


def _seed_exam_timetable():
    """The exam timetable: the papers, with the slots they run in."""
    from datetime import date as date_type
    from datetime import time as time_type

    with Session(engine) as s:
        rows = [
            (CORE_COURSE, date_type(2026, 9, 21), time_type(15, 0), time_type(17, 0)),
            (SECOND_COURSE, date_type(2026, 9, 22), time_type(11, 0), time_type(13, 0)),
            (ELECTIVE, date_type(2026, 9, 23), time_type(11, 0), time_type(13, 0)),
            # A course of another branch, and a course the student never
            # opted into: neither is the student's exam.
            (FOREIGN_COURSE, date_type(2026, 9, 21), time_type(8, 0), time_type(10, 0)),
            (NOT_THEIRS, date_type(2026, 9, 23), time_type(11, 0), time_type(13, 0)),
        ]
        for code, when, start, end in rows:
            s.add(
                MidSemSchedule(
                    schedule_date=when,
                    start_time=start,
                    end_time=end,
                    course_code=code,
                    room="",
                    branch=None,
                    semester=None,
                )
            )
        s.commit()


def _seed_seating():
    """The seating index: the halls, and the blocks the roll sits in."""
    from datetime import date as date_type
    from datetime import time as time_type

    with Session(engine) as s:
        rows = [
            # The student's own block.
            (CORE_COURSE, date_type(2026, 9, 21), time_type(15, 0), time_type(17, 0), "L-101", 1, 10),
            (SECOND_COURSE, date_type(2026, 9, 22), time_type(11, 0), time_type(13, 0), "L-202", 1, 10),
            (ELECTIVE, date_type(2026, 9, 23), time_type(11, 0), time_type(13, 0), "L-303", 1, 10),
            # A course the student does not sit, in a block that holds the roll.
            (NOT_THEIRS, date_type(2026, 9, 23), time_type(11, 0), time_type(13, 0), "L-404", 1, 10),
            # The same course in another band: the hall of another band is
            # not the hall of this one.
            (SECOND_COURSE, date_type(2026, 9, 22), time_type(15, 0), time_type(17, 0), "L-999", 1, 10),
        ]
        for code, when, start, end, room, first, last in rows:
            s.add(
                ExamSeating(
                    roll_start_prefix="23BCS",
                    roll_start_num=first,
                    roll_end_num=last,
                    room=room,
                    seating_date=when,
                    start_time=start,
                    end_time=end,
                    course_code=code,
                    branch=None,
                    semester=None,
                    is_extra=False,
                )
            )
        s.commit()


@pytest.fixture
def seeded(student_headers):
    _seed_subject_slots()
    _seed_exam_timetable()
    _seed_seating()
    return student_headers


def _lookup(client, headers, roll=ROLL):
    response = client.get(f"/exam/lookup?roll={roll}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _timetable(client, headers):
    response = client.get("/exam/timetable", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_the_lookup_shows_the_papers_the_student_sits(anon_client, seeded):
    """Their courses, their electives - and nothing else."""
    body = _lookup(anon_client, seeded)
    codes = {exam["course_code"] for exam in body["exams"]}
    assert codes == {CORE_COURSE, SECOND_COURSE, ELECTIVE}


def test_a_course_the_student_does_not_sit_never_appears(anon_client, seeded):
    """
    A block that holds the roll is not enough to make a paper theirs.

    The index says this roll sits in that hall - for a course the student
    never opted into. The exam is theirs by course, not by hall.
    """
    body = _lookup(anon_client, seeded)
    codes = {exam["course_code"] for exam in body["exams"]}
    assert NOT_THEIRS not in codes
    assert FOREIGN_COURSE not in codes


def test_the_lookup_and_the_timetable_agree(anon_client, seeded):
    """One list, two screens: same papers, same slots, same halls."""
    body = _lookup(anon_client, seeded)
    looked_up = {
        (exam["course_code"], exam["date"], exam["start_time"], exam["end_time"], exam["room"])
        for exam in body["exams"]
    }
    timetabled = {
        (
            exam["course_code"],
            exam["schedule_date"],
            exam["start_time"],
            exam["end_time"],
            exam["room"],
        )
        for day in _timetable(anon_client, seeded)["days"]
        for exam in day["exams"]
    }
    assert looked_up == timetabled


def test_the_hall_is_the_block_the_roll_sits_in(anon_client, seeded):
    """The hall of the block the roll is in, not the hall of another band."""
    body = _lookup(anon_client, seeded)
    rooms = {exam["course_code"]: exam["room"] for exam in body["exams"]}
    assert rooms[CORE_COURSE] == "L-101"
    # L-999 is the same course in the 3 PM band; the paper runs at 11 AM.
    assert rooms[SECOND_COURSE] == "L-202"
    assert rooms[ELECTIVE] == "L-303"


def test_a_paper_the_index_has_no_block_for_still_appears(anon_client, seeded):
    """
    A thin index must not cost the student an exam.

    The index has no block holding this roll for the course, so the hall
    comes from the course's own block - and the paper is still listed.
    """
    with Session(engine) as s:
        s.exec(
            delete(ExamSeating).where(ExamSeating.course_code == SECOND_COURSE)
        )
        s.commit()
    _seed_seating_for_only_one()

    body = _lookup(anon_client, seeded)
    exams = [exam for exam in body["exams"] if exam["course_code"] == SECOND_COURSE]
    assert len(exams) == 1, body
    assert exams[0]["date"] == NEXT_DAY
    assert exams[0]["start_time"] == "11:00"


def _seed_seating_for_only_one():
    """Re-seed the index without the course whose block was removed."""
    from datetime import date as date_type
    from datetime import time as time_type

    with Session(engine) as s:
        s.add(
            ExamSeating(
                roll_start_prefix="23BCS",
                roll_start_num=100,
                roll_end_num=200,
                room="L-777",
                seating_date=date_type(2026, 9, 22),
                start_time=time_type(11, 0),
                end_time=time_type(13, 0),
                course_code=SECOND_COURSE,
                branch=None,
                semester=None,
                is_extra=False,
            )
        )
        s.commit()
