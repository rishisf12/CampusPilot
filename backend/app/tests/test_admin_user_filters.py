"""The admin's user list filters by who people are.

An administrator does not think "which accounts have the role student" -
they think "which faculty", "the BTech 2024 batch", "the CRs of ME sem 3".
The list could only be cut by the role column, so those questions had
nothing to filter on.

These tests pin the filters down, and the rule that makes them meaningful:
the admin can describe a person (their programme, batch, class, and whether
they are faculty or a class representative), and the filters find them.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from core.database import engine
from features.auth.routes import create_access_token
from main import app
from models import User, UserProfile, UserRole

#: Usernames this file owns, so its cleanup cannot touch anybody else's.
TEST_USERNAMES = ("filter_admin", "filter_faculty", "filter_student", "filter_cr")


@pytest.fixture
def anon_client():
    with TestClient(app) as c:
        yield c


def _account(username, role, **profile):
    """One account with a profile, created if it is not there yet."""
    with Session(engine) as s:
        user = s.exec(select(User).where(User.username == username)).first()
        if user is None:
            user = User(
                email=f"{username}@iiitdmj.ac.in",
                password_hash="x",
                full_name=username,
                username=username,
                roll_number="23BCS001",
                is_email_verified=True,
                role=role,
            )
            s.add(user)
            s.commit()
            s.refresh(user)
        user.role = role
        s.add(user)
        s.commit()
        s.refresh(user)

        row = s.exec(
            select(UserProfile).where(UserProfile.user_id == user.id)
        ).first()
        if row is None:
            row = UserProfile(user_id=user.id)
        row.programme = profile.get("programme")
        row.semester = profile.get("semester", 1)
        row.branch = profile.get("branch")
        row.batch_year = profile.get("batch_year")
        row.is_faculty = profile.get("is_faculty", False)
        row.is_class_representative = profile.get("is_class_representative", False)
        s.add(row)
        s.commit()
        user_id = user.id
    return {"Authorization": f"Bearer {create_access_token(user_id, username)}"}


@pytest.fixture
def admin():
    return _account("filter_admin", UserRole.ADMIN, programme="BTech")


@pytest.fixture
def seeded():
    """One of each kind, so every filter has something to find."""
    _account(
        "filter_faculty",
        UserRole.STUDENT,
        programme="MTech",
        semester=2,
        branch="PG",
        batch_year=2023,
        is_faculty=True,
    )
    _account(
        "filter_student",
        UserRole.STUDENT,
        programme="BTech",
        semester=5,
        branch="ME",
        batch_year=2024,
    )
    _account(
        "filter_cr",
        UserRole.STUDENT,
        programme="BDes",
        semester=3,
        branch="DS",
        batch_year=2022,
        is_class_representative=True,
    )
    yield


@pytest.fixture(autouse=True)
def clean():
    yield
    with Session(engine) as s:
        for username in TEST_USERNAMES:
            user = s.exec(select(User).where(User.username == username)).first()
            if user is None:
                continue
            s.exec(delete(UserProfile).where(UserProfile.user_id == user.id))
            s.delete(user)
        s.commit()


def _list(client, headers, query=""):
    response = client.get(f"/admin/users{query}", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    return {row["username"] for row in body["users"]}, body["total"]


def test_the_faculty_are_the_ones_marked_as_faculty(anon_client, admin, seeded):
    """The faculty are not the accounts whose email says so."""
    names, _ = _list(anon_client, admin, "?category=faculty")
    assert names == {"filter_faculty"}


def test_the_students_are_not_the_faculty(anon_client, admin, seeded):
    names, _ = _list(anon_client, admin, "?category=students")
    assert names == {"filter_student", "filter_cr"}


def test_the_class_representatives_are_found(anon_client, admin, seeded):
    names, _ = _list(anon_client, admin, "?category=cr")
    assert names == {"filter_cr"}


def test_the_admins_are_found(anon_client, admin, seeded):
    names, _ = _list(anon_client, admin, "?category=admin")
    assert "filter_admin" in names


def test_undergraduates_are_undergraduates(anon_client, admin, seeded):
    """A level is a way of asking about the students, not a role."""
    names, _ = _list(anon_client, admin, "?category=students&group=UG")
    assert names == {"filter_student", "filter_cr"}


def test_the_postgraduates_are_their_own(anon_client, admin, seeded):
    """The postgraduate group is MTech and MDes - and the PhD scholars with
    them."""
    names, _ = _list(anon_client, admin, "?group=PG")
    assert names == {"filter_faculty"}
    # Nobody who is a *student* is a postgraduate here: the only MTech
    # account is the member of the faculty.
    names, _ = _list(anon_client, admin, "?category=students&group=PG")
    assert names == set()


def test_a_programme_narrows_the_level(anon_client, admin, seeded):
    names, _ = _list(anon_client, admin, "?category=students&group=UG&programme=BDes")
    assert names == {"filter_cr"}


def test_the_batch_year_finds_a_batch(anon_client, admin, seeded):
    names, _ = _list(anon_client, admin, "?batch_year=2024")
    assert names == {"filter_student"}


def test_the_branch_and_semester_find_a_class(anon_client, admin, seeded):
    names, _ = _list(anon_client, admin, "?branch=ME&semester=5")
    assert names == {"filter_student"}


def test_the_filters_combine(anon_client, admin, seeded):
    names, _ = _list(
        anon_client, admin, "?category=students&group=UG&programme=BTech&batch_year=2024"
    )
    assert names == {"filter_student"}


def test_nothing_filtered_is_every_account(anon_client, admin, seeded):
    """An unset filter filters nothing: the list opens as every account."""
    names, total = _list(anon_client, admin)
    assert {"filter_admin", "filter_faculty", "filter_student", "filter_cr"} <= names
    assert total >= 4


def test_clubs_are_not_available_yet(anon_client, admin, seeded):
    """There are no clubs to filter, and the list says so rather than
    answering with everything."""
    response = anon_client.get("/admin/users?category=clubs", headers=admin)
    assert response.status_code == 400
    assert "clubs" in response.json()["detail"].lower()


def test_an_unknown_category_is_refused(anon_client, admin, seeded):
    response = anon_client.get("/admin/users?category=wizards", headers=admin)
    assert response.status_code == 400


def test_the_rows_carry_the_fields_they_are_filtered_by(anon_client, admin, seeded):
    """A list that filters on fields it does not show is a list the admin
    cannot read."""
    response = anon_client.get("/admin/users?search=filter_student", headers=admin)
    assert response.status_code == 200
    row = response.json()["users"][0]
    assert row["programme"] == "BTech"
    assert row["semester"] == 5
    assert row["branch"] == "ME"
    assert row["batch_year"] == 2024
    assert row["is_faculty"] is False
    assert row["is_class_representative"] is False


def test_the_admin_can_describe_an_account(anon_client, admin, seeded):
    """Who represents a class and who teaches here is the college's call."""
    with Session(engine) as s:
        user = s.exec(select(User).where(User.username == "filter_student")).first()
        user_id = user.id

    response = anon_client.patch(
        f"/admin/users/{user_id}",
        headers=admin,
        json={"is_class_representative": True, "batch_year": 2025},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_class_representative"] is True
    assert body["batch_year"] == 2025

    # And the filter finds them under the new description.
    names, _ = _list(anon_client, admin, "?category=cr")
    assert "filter_student" in names
    names, _ = _list(anon_client, admin, "?batch_year=2025")
    assert "filter_student" in names


def test_a_nonsense_batch_year_is_refused(anon_client, admin, seeded):
    with Session(engine) as s:
        user = s.exec(select(User).where(User.username == "filter_student")).first()
        user_id = user.id
    response = anon_client.patch(
        f"/admin/users/{user_id}", headers=admin, json={"batch_year": 12}
    )
    assert response.status_code == 400


def test_the_filter_facets_are_the_colleges_own(anon_client, admin, seeded):
    """The branches and the semesters are the timetable's lists, and the
    batch years are the ones the accounts actually carry."""
    response = anon_client.get("/admin/users/filters", headers=admin)
    assert response.status_code == 200
    body = response.json()
    assert "CSE A" in body["branches"]
    assert 1 in body["semesters"]
    assert 2024 in body["batch_years"]


def test_the_filters_are_admin_only(anon_client, seeded):
    student = _account("filter_student", UserRole.STUDENT, programme="BTech")
    assert anon_client.get("/admin/users", headers=student).status_code == 403
    assert anon_client.get("/admin/users").status_code == 401
