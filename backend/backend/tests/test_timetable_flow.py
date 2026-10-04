"""
Class timetable upload, exercised through the CSV path.

The weekly timetable PDF is not available here, but the whole pipeline behind it
is: upload -> parse -> store -> attendance subject sync -> live schedule ->
vacant room lookup. Running it with a CSV fixture proves every step of that
chain works, so only the PDF file itself remains outstanding.
"""
import io

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

# The database URL is set by tests/conftest.py before any import of the app.
from database import create_db_and_tables, engine  # noqa: E402
from main import app  # noqa: E402
from models import Course, TimetableSlot, User, UserProfile  # noqa: E402
from routes.auth import create_access_token  # noqa: E402

TIMETABLE_CSV = """day,start_time,end_time,room,course_code,branch_or_program,semester
Monday,09:00,10:00,L-101,CS5031,BTech CSE,5
Monday,11:00,12:00,L-102,ME5011,BTech ME,5
Monday,14:00,15:00,CR-101,CS5031,BTech CSE,5
Tuesday,09:00,10:00,L-101,CS5032,BTech CSE,5
Tuesday,11:00,12:00,L-103,OE3E33,BTech,5
Wednesday,10:00,11:00,L-102,SM2002,BTech SM,5
"""


@pytest.fixture(scope="module")
def context():
    create_db_and_tables()
    with Session(engine) as session:
        user = User(
            email="timetable@iiitdmj.ac.in", password_hash="x", full_name="TT Student",
            username="ttuser", roll_number="23BCS060", is_email_verified=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        session.add(UserProfile(user_id=user.id, programme="BTech", semester=5, branch="CSE A"))
        # Own the codes used here so other fixtures cannot interfere.
        session.exec(delete(TimetableSlot))
        session.exec(delete(Course).where(Course.code.in_(["CS5031", "ME5011", "CS5032",
                                                           "OE3E33", "SM2002"])))
        session.commit()
        user_id = user.id

    with TestClient(app) as test_client:
        yield test_client, create_access_token(user_id, "ttuser")


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def upload(client, token, body=TIMETABLE_CSV, filename="timetable.csv"):
    return client.post(
        "/timetable/upload",
        headers=auth(token),
        files={"file": (filename, io.BytesIO(body.encode()), "text/csv")},
    )


class TestTimetableUpload:
    def test_upload_stores_every_valid_slot(self, context):
        client, token = context
        res = upload(client, token)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["slots_inserted"] == 6
        assert body["slots_found"] == 6
        assert body["warnings"] == []

    def test_upload_syncs_courses_for_attendance(self, context):
        """Attendance is driven by the timetable, so courses appear immediately."""
        client, token = context
        with Session(engine) as session:
            codes = {c.code for c in session.exec(select(Course)).all()}
        assert {"CS5031", "ME5011", "CS5032", "OE3E33", "SM2002"} <= codes

        subjects = client.get("/attendance/subjects", headers=auth(token)).json()
        listed = {s["course_code"] for s in subjects["subjects"]}
        # A CSE A sem 5 student sees the CSE courses plus their own elective.
        assert "CS5031" in listed
        assert "CS5032" in listed

    def test_live_schedule_reports_current_and_next(self, context):
        client, token = context
        body = client.get("/schedule/now", headers=auth(token)).json()
        assert "current_class" in body
        assert "next_class" in body
        assert "current_time" in body

    def test_vacant_rooms_uses_the_uploaded_timetable(self, context):
        client, token = context
        body = client.get(
            "/rooms/vacant",
            headers=auth(token),
            params={"mode": "manual", "day": "Mon", "hour": "09:30"},
        ).json()
        assert body["has_timetable"] is True
        # L-101 is busy 09:00-10:00 on Monday, so it must not be offered.
        assert "L-101" not in body["vacant_rooms"]
        assert "L-101" in {o["room"] for o in body["occupied_rooms"]}
        assert "CR-101" in body["vacant_rooms"]

    def test_rooms_all_lists_every_hall(self, context):
        client, token = context
        rooms = client.get("/rooms/all", headers=auth(token)).json()["rooms"]
        assert set(rooms) == {"L-101", "L-102", "L-103", "CR-101"}

    def test_timetable_options_reports_discovered_values(self, context):
        client, token = context
        body = client.get("/timetable/options", headers=auth(token)).json()
        assert body["total_slots"] == 6
        assert 5 in body["semesters"]
        assert "CS5031" in body["courses"]

    def test_slots_endpoint_serialises_times_as_strings(self, context):
        """Regression: this used to 500 because time objects were returned."""
        client, token = context
        res = client.get("/timetable/slots", headers=auth(token))
        assert res.status_code == 200, res.text
        first = res.json()[0]
        assert isinstance(first["start_time"], str)
        assert first["start_time"] == first["start_time"].strip()
        assert len(first["start_time"]) == 5  # "09:00"

    def test_malformed_rows_are_reported_not_fatal(self, context):
        client, token = context
        body = (
            "day,start_time,end_time,room,course_code,branch_or_program,semester\n"
            "Monday,09:00,10:00,L-101,CS5031,BTech CSE,5\n"
            "Funday,09:00,10:00,L-101,CS5031,BTech CSE,5\n"   # invalid day
            "Monday,99:99,10:00,L-101,CS5031,BTech CSE,5\n"   # invalid time
            "Tuesday,11:00,12:00,L-104,CS5033,BTech CSE,5\n"
        )
        res = upload(client, token, body=body, filename="partial.csv")
        assert res.status_code == 200
        result = res.json()
        assert result["slots_inserted"] == 2
        assert len(result["warnings"]) == 2

    def test_missing_columns_is_a_clear_error(self, context):
        client, token = context
        res = upload(client, token, body="day,room\nMonday,L-101\n", filename="bad.csv")
        assert res.status_code == 400
        assert "missing columns" in res.json()["detail"].lower()

    def test_reupload_replaces_previous_slots(self, context):
        client, token = context
        upload(client, token)
        body = (
            "day,start_time,end_time,room,course_code,branch_or_program,semester\n"
            "Friday,09:00,10:00,L-999,CS5099,BTech CSE,5\n"
        )
        res = upload(client, token, body=body, filename="replacement.csv")
        assert res.status_code == 200
        slots = client.get("/timetable/slots", headers=auth(token)).json()
        assert len(slots) == 1
        assert slots[0]["room"] == "L-999"

    def test_clear_removes_everything(self, context):
        client, token = context
        assert client.delete("/timetable", headers=auth(token)).status_code == 204
        body = client.get("/rooms/vacant", headers=auth(token)).json()
        assert body["has_timetable"] is False
        assert "upload the class timetable" in (body["message"] or "").lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])