"""Tests for feedback email ingestion endpoint."""
import base64
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

# The database URL is set by tests/conftest.py before any import of the app.
from core.database import create_db_and_tables, engine
from main import app
from models import User
from features.auth.routes import create_access_token


@pytest.fixture(scope="module")
def client():
    create_db_and_tables()
    with Session(engine) as session:
        user = User(
            email="ingest@iiitdmj.ac.in", password_hash="x", full_name="Ingest Test",
            username="ingestuser", roll_number="23BCS100", is_email_verified=True,
            role="student",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = user.id

    with TestClient(app) as test_client:
        yield {
            "client": test_client,
            "token": create_access_token(user_id, "ingestuser"),
            "user_id": user_id,
        }


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_ingest_feedback_basic(client):
    """Basic email ingestion without attachments."""
    payload = {
        "from_email": "test@iiitdmj.ac.in",
        "from_name": "Test Student",
        "subject": "Test feedback",
        "text": "This is a test message.",
        "html": "<p>This is a test message.</p>",
        "attachments": [],
    }
    resp = client["client"].post("/feedback/ingest", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Student"
    assert data["email"] == "test@iiitdmj.ac.in"
    assert data["subject"] == "Test feedback"
    assert data["message"] == "This is a test message."
    assert data["attachment_original"] is None
    assert data["user_id"] is None  # no matching user


def test_ingest_feedback_links_existing_user(client):
    """Email from existing user links to their account."""
    payload = {
        "from_email": "ingest@iiitdmj.ac.in",
        "from_name": "Ingest Test",
        "subject": "From existing user",
        "text": "This should link to my account.",
        "html": None,
        "attachments": [],
    }
    resp = client["client"].post("/feedback/ingest", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["user_id"] == client["user_id"]
    assert data["name"] == "Ingest Test"


def test_ingest_feedback_with_attachment(client):
    """Email ingestion with a base64-encoded attachment."""
    # Create a tiny PNG (1x1 pixel)
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    payload = {
        "from_email": "attach@iiitdmj.ac.in",
        "from_name": "Attach Test",
        "subject": "With attachment",
        "text": "Here is a screenshot.",
        "html": None,
        "attachments": [
            {
                "filename": "screenshot.png",
                "content": base64.b64encode(png_bytes).decode("ascii"),
                "content_type": "image/png",
            }
        ],
    }
    resp = client["client"].post("/feedback/ingest", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["attachment_original"] == "screenshot.png"
    assert data["attachment_size"] == len(png_bytes)


def test_ingest_feedback_multiple_attachments(client):
    """Multiple attachments concatenated in attachment_original."""
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    txt = base64.b64encode(b"log data").decode("ascii")
    payload = {
        "from_email": "multi@iiitdmj.ac.in",
        "from_name": "Multi Attach",
        "subject": "Multiple files",
        "text": "Two files attached.",
        "attachments": [
            {"filename": "image.png", "content": base64.b64encode(png).decode("ascii"), "content_type": "image/png"},
            {"filename": "log.txt", "content": txt, "content_type": "text/plain"},
        ],
    }
    resp = client["client"].post("/feedback/ingest", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert "image.png" in data["attachment_original"]
    assert "log.txt" in data["attachment_original"]


def test_ingest_feedback_rejects_empty_body(client):
    """Empty text and html should be rejected."""
    payload = {
        "from_email": "empty@iiitdmj.ac.in",
        "from_name": "Empty Body",
        "subject": "Empty",
        "text": "",
        "html": "",
        "attachments": [],
    }
    resp = client["client"].post("/feedback/ingest", json=payload)
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


def test_ingest_feedback_falls_back_to_html(client):
    """If text is empty but html exists, html is stripped and used."""
    payload = {
        "from_email": "html@iiitdmj.ac.in",
        "from_name": "HTML Only",
        "subject": "HTML fallback",
        "text": "",
        "html": "<p>Message from <strong>HTML</strong></p>",
        "attachments": [],
    }
    resp = client["client"].post("/feedback/ingest", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert "Message from HTML" in data["message"]


def test_ingest_feedback_rejects_large_attachment(client):
    """Attachments over size limit are skipped."""
    large = b"x" * (26 * 1024 * 1024)  # 26 MB, over 25 MB default limit
    payload = {
        "from_email": "large@iiitdmj.ac.in",
        "from_name": "Large File",
        "subject": "Too big",
        "text": "Should be rejected.",
        "attachments": [
            {"filename": "huge.pdf", "content": base64.b64encode(large).decode("ascii"), "content_type": "application/pdf"}
        ],
    }
    resp = client["client"].post("/feedback/ingest", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    # Attachment should be skipped, so no attachment_original
    assert data["attachment_original"] is None


def test_ingest_feedback_rejects_disallowed_extension(client):
    """Disallowed extensions (.exe, .py, etc.) are skipped."""
    payload = {
        "from_email": "bad@iiitdmj.ac.in",
        "from_name": "Bad Ext",
        "subject": "Bad file",
        "text": "Has .exe",
        "attachments": [
            {"filename": "malware.exe", "content": base64.b64encode(b"bad").decode("ascii"), "content_type": "application/octet-stream"}
        ],
    }
    resp = client["client"].post("/feedback/ingest", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["attachment_original"] is None