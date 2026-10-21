"""The seating index and the exam timetable must tell the same story.

Two documents describe one exam: the timetable says *when* a paper is, the
seating index says *where* it is and *who* sits in it. They are uploaded
separately, so they can disagree - a typo in one, a header the parser read
differently in the other. When they do, the timetable screen and the roll
lookup answer the same question differently, and the student has no way to
tell which one to believe.

The timetable is the published document, so it decides the slot; the index
keeps the roll ranges and the hall. These tests pin that rule, and pin the
cases where it must *not* guess.
"""
import io
from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from core.database import engine
from features.auth.routes import create_access_token
from features.exam.lookup import fill_rooms_from_seating
from features.exam.reconcile import reconcile_stored
from main import app
from models import ExamSeating, MidSemSchedule, User, UserRole

#: Codes the parser accepts (`[A-Z]{2,3}\d{1,4}`) that no other test file
#: could plausibly seed.
TIMETABLE_COURSE = "ZS3001"
AMBIGUOUS_COURSE = "ZS3002"
UNKNOWN_COURSE = "ZS3003"
TWO_BAND_COURSE = "ZS3004"

SEEDED_CODES = (TIMETABLE_COURSE, AMBIGUOUS_COURSE, UNKNOWN_COURSE, TWO_BAND_COURSE)

EXAM_DATE = date(2026, 9, 24)
NEXT_DAY = date(2026, 9, 25)
ROLL = "23BCS005"


@pytest.fixture
def anon_client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def student_headers():
    with Session(engine) as s:
        user = s.exec(select(User).where(User.username == "recon_student")).first()
        if user is None:
            user = User(
                email="recon_student@iiitdmj.ac.in",
                password_hash="x",
                full_name="recon_student",
                username="recon_student",
                roll_number=ROLL,
                is_email_verified=True,
                role=UserRole.STUDENT,
            )
            s.add(user)
            s.commit()
            s.refresh(user)
        user_id = user.id
    return {"Authorization": f"Bearer {create_access_token(user_id, 'recon_student')}"}


@pytest.fixture
def admin_headers():
    with Session(engine) as s:
        user = s.exec(select(User).where(User.username == "recon_admin")).first()
        if user is None:
            user = User(
                email="recon_admin@iiitdmj.ac.in",
                password_hash="x",
                full_name="recon_admin",
                username="recon_admin",
                roll_number="23BCS999",
                is_email_verified=True,
                role=UserRole.ADMIN,
            )
            s.add(user)
            s.commit()
            s.refresh(user)
        user_id = user.id
    return {"Authorization": f"Bearer {create_access_token(user_id, 'recon_admin')}"}


@pytest.fixture(autouse=True)
def clean_seeded_rows():
    """The exam rows this file seeds, and nothing else, are removed after it."""
    yield
    with Session(engine) as s:
        s.exec(
            delete(ExamSeating).where(ExamSeating.course_code.in_(SEEDED_CODES))
        )
        s.exec(
            delete(MidSemSchedule).where(MidSemSchedule.course_code.in_(SEEDED_CODES))
        )
        s.commit()


def _seed_timetable(course, when, start, end, uploaded_by=None):
    with Session(engine) as s:
        s.add(
            MidSemSchedule(
                schedule_date=when,
                start_time=start,
                end_time=end,
                course_code=course,
                room="",
                branch=None,
                semester=None,
                uploaded_by=uploaded_by,
            )
        )
        s.commit()


def _seed_seating(
    course,
    when,
    start,
    end,
    room,
    uploaded_by=None,
    prefix="23BCS",
    first=1,
    last=10,
):
    with Session(engine) as s:
        s.add(
            ExamSeating(
                roll_start_prefix=prefix,
                roll_start_num=first,
                roll_end_num=last,
                room=room,
                seating_date=when,
                start_time=start,
                end_time=end,
                course_code=course,
                branch=None,
                semester=None,
                is_extra=False,
                uploaded_by=uploaded_by,
            )
        )
        s.commit()


def _lookup(client, headers, roll=ROLL):
    response = client.get(f"/exam/lookup?roll={roll}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _exams_for(body, course):
    return [exam for exam in body["exams"] if exam["course_code"] == course]


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------

def test_the_lookup_answers_with_the_timetable_slot(anon_client, student_headers):
    """
    The timetable says 3 PM; the index says 11 AM. The student is told 3 PM.

    The index is stored against the slot its own document gave it, which is
    not always the slot the published timetable has. The timetable is the
    document the exam is run from, so it decides.
    """
    _seed_timetable(TIMETABLE_COURSE, EXAM_DATE, time(15, 0), time(17, 0))
    _seed_seating(TIMETABLE_COURSE, EXAM_DATE, time(11, 0), time(13, 0), "L-101")

    body = _lookup(anon_client, student_headers)
    exams = _exams_for(body, TIMETABLE_COURSE)
    assert len(exams) == 1, body
    exam = exams[0]
    assert exam["date"] == EXAM_DATE.isoformat()
    assert exam["start_time"] == "15:00"
    assert exam["end_time"] == "17:00"
    # The index still says where they sit.
    assert exam["room"] == "L-101"


def test_the_seating_index_shows_the_timetable_slot(anon_client, student_headers):
    """The index screen agrees with the timetable screen, row for row."""
    _seed_timetable(TIMETABLE_COURSE, EXAM_DATE, time(15, 0), time(17, 0))
    _seed_seating(TIMETABLE_COURSE, EXAM_DATE, time(11, 0), time(13, 0), "L-101")

    response = anon_client.get(
        f"/exam/seating?roll={ROLL}", headers=student_headers
    )
    assert response.status_code == 200, response.text
    rows = [
        row
        for day in response.json()["days"]
        for row in day["rooms"]
        if row["course_code"] == TIMETABLE_COURSE
    ]
    assert rows, response.json()
    assert rows[0]["seating_date"] == EXAM_DATE.isoformat()
    assert rows[0]["start_time"] == "15:00"
    assert rows[0]["end_time"] == "17:00"


def test_a_course_the_timetable_does_not_know_keeps_its_slot(
    anon_client, student_headers
):
    """The rule never invents an exam: an unknown course keeps its own slot."""
    _seed_seating(UNKNOWN_COURSE, EXAM_DATE, time(11, 0), time(13, 0), "L-101")

    body = _lookup(anon_client, student_headers)
    exams = _exams_for(body, UNKNOWN_COURSE)
    assert len(exams) == 1, body
    assert exams[0]["start_time"] == "11:00"
    assert exams[0]["end_time"] == "13:00"


def test_a_course_in_two_slots_on_one_day_is_left_alone(
    anon_client, student_headers
):
    """
    Two real exams, one course: the rule does not choose between them.

    The timetable puts the course in two bands on the same day, so the index
    row could belong to either. Guessing would put the student in the wrong
    hall at the wrong hour, which is worse than showing the index's own
    wording.
    """
    _seed_timetable(AMBIGUOUS_COURSE, EXAM_DATE, time(11, 0), time(13, 0))
    _seed_timetable(AMBIGUOUS_COURSE, EXAM_DATE, time(15, 0), time(17, 0))
    _seed_seating(AMBIGUOUS_COURSE, EXAM_DATE, time(8, 0), time(10, 0), "L-101")

    body = _lookup(anon_client, student_headers)
    exams = _exams_for(body, AMBIGUOUS_COURSE)
    assert len(exams) == 1, body
    assert exams[0]["start_time"] == "08:00"


def test_a_course_in_several_slots_uses_the_one_on_its_own_day(
    anon_client, student_headers
):
    """
    The course runs on two days; the index row names one of them.

    The band for that day is the one the timetable has for it, so the row is
    corrected to that band without moving it to another day.
    """
    _seed_timetable(AMBIGUOUS_COURSE, EXAM_DATE, time(11, 0), time(13, 0))
    _seed_timetable(AMBIGUOUS_COURSE, NEXT_DAY, time(15, 0), time(17, 0))
    _seed_seating(AMBIGUOUS_COURSE, NEXT_DAY, time(8, 0), time(10, 0), "L-101")

    body = _lookup(anon_client, student_headers)
    exams = _exams_for(body, AMBIGUOUS_COURSE)
    assert len(exams) == 1, body
    assert exams[0]["date"] == NEXT_DAY.isoformat()
    assert exams[0]["start_time"] == "15:00"


def test_a_paper_is_never_moved_to_another_day(anon_client, student_headers):
    """
    A course the timetable places on another day keeps its own slot.

    A mid-sem timetable and an end-sem index share course codes. Moving a
    paper to the other cycle's day would put a student in a hall on the
    wrong date, so the day is the anchor: only the band is corrected.
    """
    _seed_timetable(TIMETABLE_COURSE, NEXT_DAY, time(15, 0), time(17, 0))
    _seed_seating(TIMETABLE_COURSE, EXAM_DATE, time(11, 0), time(13, 0), "L-101")

    body = _lookup(anon_client, student_headers)
    exams = _exams_for(body, TIMETABLE_COURSE)
    assert len(exams) == 1, body
    assert exams[0]["date"] == EXAM_DATE.isoformat()
    assert exams[0]["start_time"] == "11:00"


def test_the_same_paper_is_not_answered_twice(anon_client, student_headers):
    """
    The admin's copy and the account's own copy are one paper.

    Both are in view for that account, and the student should be told once:
    a repeated card reads as two exams, and the second one is usually the
    one that looks wrong.
    """
    _seed_timetable(TIMETABLE_COURSE, EXAM_DATE, time(15, 0), time(17, 0))
    _seed_seating(TIMETABLE_COURSE, EXAM_DATE, time(15, 0), time(17, 0), "L-101")
    with Session(engine) as s:
        user = s.exec(select(User).where(User.username == "recon_student")).first()
        owner = user.id
    _seed_seating(
        TIMETABLE_COURSE, EXAM_DATE, time(15, 0), time(17, 0), "L-101", uploaded_by=owner
    )

    body = _lookup(anon_client, student_headers)
    exams = _exams_for(body, TIMETABLE_COURSE)
    assert len(exams) == 1, body


# ---------------------------------------------------------------------------
# The halls
# ---------------------------------------------------------------------------

def test_the_hall_comes_from_the_same_band():
    """
    A course that runs in two bands gets the hall of the band it runs in.

    The timetable has no hall column, so it borrows one from the index. The
    borrow has to be band-exact, or a paper is given the hall of another
    paper that happens to share its course code.
    """
    _seed_timetable(TWO_BAND_COURSE, EXAM_DATE, time(15, 0), time(17, 0))
    _seed_seating(TWO_BAND_COURSE, EXAM_DATE, time(11, 0), time(13, 0), "L-101")
    _seed_seating(TWO_BAND_COURSE, EXAM_DATE, time(15, 0), time(17, 0), "L-303")

    rows = [
        {
            "course_code": TWO_BAND_COURSE,
            "schedule_date": EXAM_DATE.isoformat(),
            "start_time": "15:00",
            "end_time": "17:00",
            "room": "",
        }
    ]
    with Session(engine) as s:
        fill_rooms_from_seating(s, rows, owner_id=None)
    assert rows[0]["room"] == "L-303"


def test_the_hall_of_a_band_without_rows_falls_back_to_the_day():
    """A band the index does not cover still gets that day's hall."""
    _seed_timetable(TWO_BAND_COURSE, EXAM_DATE, time(15, 0), time(17, 0))
    _seed_seating(TWO_BAND_COURSE, EXAM_DATE, time(11, 0), time(13, 0), "L-101")

    rows = [
        {
            "course_code": TWO_BAND_COURSE,
            "schedule_date": EXAM_DATE.isoformat(),
            "start_time": "15:00",
            "end_time": "17:00",
            "room": "",
        }
    ]
    with Session(engine) as s:
        fill_rooms_from_seating(s, rows, owner_id=None)
    assert rows[0]["room"] == "L-101"


# ---------------------------------------------------------------------------
# The index as a document
# ---------------------------------------------------------------------------

def test_the_index_is_listed_even_when_it_does_not_cover_the_reader(
    anon_client, student_headers
):
    """
    The index is a document, and it is listed.

    A student whose roll the index does not cover used to be shown an empty
    list under the words "no seating index uploaded" - which is a lie, and
    sends them looking for a file that is there.
    """
    _seed_timetable(TIMETABLE_COURSE, EXAM_DATE, time(15, 0), time(17, 0))
    # The block holds other rolls, not this reader's.
    _seed_seating(
        TIMETABLE_COURSE, EXAM_DATE, time(15, 0), time(17, 0), "L-101", first=100, last=200
    )

    response = anon_client.get("/exam/seating", headers=student_headers)
    assert response.status_code == 200, response.text
    rows = [
        row for day in response.json()["days"] for row in day["rooms"]
    ]
    assert rows, response.json()
    assert rows[0]["course_code"] == TIMETABLE_COURSE
    assert rows[0]["start_time"] == "15:00"


def test_a_block_the_account_holds_twice_is_listed_once(anon_client, student_headers):
    """The admin's copy and the account's own copy are one block."""
    _seed_timetable(TIMETABLE_COURSE, EXAM_DATE, time(15, 0), time(17, 0))
    _seed_seating(TIMETABLE_COURSE, EXAM_DATE, time(15, 0), time(17, 0), "L-101")
    with Session(engine) as s:
        user = s.exec(select(User).where(User.username == "recon_student")).first()
        owner = user.id
    _seed_seating(
        TIMETABLE_COURSE,
        EXAM_DATE,
        time(15, 0),
        time(17, 0),
        "L-101",
        uploaded_by=owner,
    )

    response = anon_client.get("/exam/seating", headers=student_headers)
    assert response.status_code == 200, response.text
    rows = [row for day in response.json()["days"] for row in day["rooms"]]
    assert len(rows) == 1, rows


# ---------------------------------------------------------------------------
# The repair
# ---------------------------------------------------------------------------

def test_the_repair_moves_the_stored_rows():
    """A database filled before the rule existed is brought into line."""
    _seed_timetable(TIMETABLE_COURSE, EXAM_DATE, time(15, 0), time(17, 0))
    _seed_seating(TIMETABLE_COURSE, EXAM_DATE, time(11, 0), time(13, 0), "L-101")

    with Session(engine) as s:
        moved = reconcile_stored(s, owner_id=None)
        assert moved >= 1
    with Session(engine) as s:
        row = s.exec(
            select(ExamSeating).where(
                ExamSeating.course_code == TIMETABLE_COURSE
            )
        ).first()
        assert row.seating_date == EXAM_DATE
        assert row.start_time == time(15, 0)
        assert row.end_time == time(17, 0)


# ---------------------------------------------------------------------------
# The upload
# ---------------------------------------------------------------------------

TIMETABLE_CSV = (
    "date,time,course_code,semester,branch\n"
    "2026-09-24,3:00 PM - 5:00 PM,ZS3001,3,CSE\n"
).encode("utf-8")

SEATING_CSV = (
    "roll_range,room,date,time,course_code,branch,semester\n"
    "23BCS001 to 23BCS010,L-101,2026-09-24,11:00 AM - 1:00 PM,ZS3001,CSE,3\n"
).encode("utf-8")


def _csv(content: bytes, name: str = "exam.csv") -> dict:
    return {"file": (name, io.BytesIO(content), "text/csv")}


def test_an_upload_is_aligned_as_it_is_stored(anon_client, admin_headers):
    """
    The rows land on the timetable's slot, not the file's.

    Aligning at upload time is what keeps the two documents in step from
    then on; aligning on read would only paper over the disagreement.
    """
    timetable = anon_client.post(
        "/exam/timetable/upload",
        files=_csv(TIMETABLE_CSV, "timetable.csv"),
        headers=admin_headers,
    )
    assert timetable.status_code == 200, timetable.text

    seating = anon_client.post(
        "/exam/seating/upload",
        files=_csv(SEATING_CSV, "seating.csv"),
        headers=admin_headers,
    )
    assert seating.status_code == 200, seating.text
    assert seating.json()["rows_aligned"] == 1, seating.json()

    with Session(engine) as s:
        row = s.exec(
            select(ExamSeating).where(ExamSeating.course_code == TIMETABLE_COURSE)
        ).first()
        assert row.seating_date == EXAM_DATE
        assert row.start_time == time(15, 0)
        assert row.end_time == time(17, 0)
