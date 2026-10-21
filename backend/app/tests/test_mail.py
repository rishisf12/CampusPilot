"""Tests for the mail app: ingest auth, filing by receiving address, group scoping.

The endpoint contract under test:
 * nobody ingests without a group's secret - not even anonymously;
 * a message is filed under the section whose receiving mail id it was
   sent to, and only under a keyword rule when no address matches;
 * a student reads their own group's mail and nobody else's.
"""
import json
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

# The database URL is set by tests/conftest.py before any import of the app.
from core.config import get_settings
from core.database import create_db_and_tables, engine
from main import app
from models import User, UserProfile, UserRole
from features.auth.routes import create_access_token


MAILBOXES = {
    "ug": {
        "imap_host": "imap.gmail.com",
        "imap_user": "ug@college.ac.in",
        "imap_password": "app-password",
        "ingest_secret": "ug-secret",
        "sections": {
            "academics": "ug-academics@college.ac.in",
            "placement": "ug-placement@college.ac.in",
        },
    },
    "pg": {
        "imap_host": "imap.gmail.com",
        "imap_user": "pg@college.ac.in",
        "imap_password": "app-password",
        "ingest_secret": "pg-secret",
        "sections": {"academics": "pg-academics@college.ac.in"},
    },
}


@pytest.fixture(scope="module")
def client():
    create_db_and_tables()
    with Session(engine) as session:
        accounts = {}
        for name, role, programme in (
            ("mailug", UserRole.STUDENT, "BTech"),
            ("mailpg", UserRole.STUDENT, "MTech"),
        ):
            user = session.exec(select(User).where(User.username == name)).first()
            if user is None:
                user = User(
                    email=f"{name}@college.ac.in",
                    password_hash="x",
                    full_name=f"Mail {name}",
                    username=name,
                    roll_number="23MAIL01" if role == UserRole.STUDENT else None,
                    is_email_verified=True,
                    role=role,
                )
                session.add(user)
                session.commit()
                session.refresh(user)
            profile = session.exec(
                select(UserProfile).where(UserProfile.user_id == user.id)
            ).first()
            if profile is None:
                session.add(
                    UserProfile(
                        user_id=user.id, programme=programme, semester=1, branch="CSE A"
                    )
                )
                session.commit()
            accounts[name] = create_access_token(user.id, name)
    with TestClient(app) as test_client:
        yield {"client": test_client, **accounts}


def configure_mailboxes(monkeypatch):
    """Point the settings singleton at the test mailboxes."""
    singleton = get_settings()
    monkeypatch.setattr(
        singleton, "mail_mailboxes_json", json.dumps(MAILBOXES), raising=False
    )


def test_ingest_requires_a_secret(client, monkeypatch):
    """No mailboxes configured: no presented secret is good enough."""
    payload = {
        "from_email": "registrar@college.ac.in",
        "subject": "Probe",
        "text": "hello",
    }
    anon = client["client"].post("/mail/ingest", json=payload)
    assert anon.status_code == 401

    wrong = client["client"].post(
        "/mail/ingest",
        json=payload,
        headers={"Authorization": "Bearer not-the-secret"},
    )
    assert wrong.status_code == 401

    configure_mailboxes(monkeypatch)
    stranger = client["client"].post(
        "/mail/ingest",
        json=payload,
        headers={"Authorization": "Bearer not-the-secret"},
    )
    assert stranger.status_code == 401


def test_ingest_files_by_receiving_address(client, monkeypatch):
    """An address on the section list decides the section, not keywords."""
    configure_mailboxes(monkeypatch)
    resp = client["client"].post(
        "/mail/ingest",
        json={
            "from_email": "registrar@college.ac.in",
            "from_name": "Registrar",
            "to": "ug-academics@college.ac.in",
            "subject": "Mid semester timetable",
            "text": "The mid semester exam timetable is out.",
            "message_id": "<mail-academics-1@college.ac.in>",
        },
        headers={"Authorization": "Bearer ug-secret"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["group"] == "ug"
    assert body["section"] == "academics"


def test_ingest_unknown_address_uses_keywords(client, monkeypatch):
    """An unlisted address falls through to the keyword classification."""
    configure_mailboxes(monkeypatch)
    resp = client["client"].post(
        "/mail/ingest",
        json={
            "from_email": "cells@college.ac.in",
            "to": "notices@college.ac.in",
            "subject": "Smart India Hackathon registrations",
            "text": "Register your hackathon teams.",
            "message_id": "<mail-hackathon-1@college.ac.in>",
        },
        headers={"Authorization": "Bearer ug-secret"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["group"] == "ug"
    assert body["section"] == "technical"


def test_ingest_files_into_the_posted_group(client, monkeypatch):
    """The pg secret files pg mail even for the same receiving address."""
    configure_mailboxes(monkeypatch)
    resp = client["client"].post(
        "/mail/ingest",
        json={
            "from_email": "registrar@college.ac.in",
            "to": "pg-academics@college.ac.in",
            "subject": "PG course registration",
            "text": "Course registration opens Monday.",
            "message_id": "<mail-pg-1@college.ac.in>",
        },
        headers={"Authorization": "Bearer pg-secret"},
    )
    assert resp.status_code == 201
    assert resp.json()["group"] == "pg"


def test_student_reads_only_their_group(client):
    """The BTech student sees the ug inbox, not the pg one."""
    ug = client["client"].get(
        "/mail/messages",
        headers={"Authorization": f"Bearer {client['mailug']}"},
    )
    assert ug.status_code == 200
    data = ug.json()
    assert [group["id"] for group in data["groups"]] == ["ug"]
    assert all(message["group"] == "ug" for message in data["messages"])

    # Asking for the other group's parameter changes nothing for a student.
    sneak = client["client"].get(
        "/mail/messages?group=pg",
        headers={"Authorization": f"Bearer {client['mailug']}"},
    )
    assert sneak.status_code == 200
    assert all(message["group"] == "ug" for message in sneak.json()["messages"])

    pg = client["client"].get(
        "/mail/messages",
        headers={"Authorization": f"Bearer {client['mailpg']}"},
    )
    assert pg.status_code == 200
    assert [group["id"] for group in pg.json()["groups"]] == ["pg"]


def test_section_filter_uses_the_navigation_ids(client):
    """A section parameter must be one the Important navigation shows."""
    headers = {"Authorization": f"Bearer {client['mailug']}"}
    unknown = client["client"].get("/mail/messages?section=wrong", headers=headers)
    assert unknown.status_code == 400

    known = client["client"].get("/mail/messages?section=academics", headers=headers)
    assert known.status_code == 200
    assert all(row["section"] == "academics" for row in known.json()["messages"])


def test_read_and_star(client, monkeypatch):
    """The per-message endpoints toggle their one flag and nothing else."""
    configure_mailboxes(monkeypatch)
    created = client["client"].post(
        "/mail/ingest",
        json={
            "from_email": "registrar@college.ac.in",
            "to": "ug-academics@college.ac.in",
            "subject": "Grade card released",
            "text": "Grade cards are available in the portal.",
            "message_id": "<mail-grade-1@college.ac.in>",
        },
        headers={"Authorization": "Bearer ug-secret"},
    )
    message_id = created.json()["id"]
    headers = {"Authorization": f"Bearer {client['mailug']}"}

    starred = client["client"].post(f"/mail/messages/{message_id}/star", headers=headers)
    assert starred.status_code == 200
    assert starred.json()["is_starred"] is True
    unstarred = client["client"].post(f"/mail/messages/{message_id}/star", headers=headers)
    assert unstarred.json()["is_starred"] is False

    read = client["client"].post(f"/mail/messages/{message_id}/read", headers=headers)
    assert read.status_code == 200
    assert read.json()["is_read"] is True
