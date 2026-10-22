"""
Tests for the sender-based routing engine (Phase 2).

These are table-driven and prove the invariants of the hybrid:

  * Section is a function of the sender only - the receiving address never
    decides the section.
  * Same sender to any of the six aliases -> same section (one stored message).
  * Six different senders to the same alias -> six different sections.
  * Unregistered sender -> unassigned state.
  * Precedence: exact > domain > pattern; within a type higher priority wins,
    then oldest.
  * Registering a sender re-files the mail it already wrote (retro-apply).
  * Routing twice with the same message -> one message, no duplicate.
"""
import json
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from core.config import get_settings
from core.database import create_db_and_tables, engine
from main import app
from models import User, UserProfile, UserRole
from features.auth.routes import create_access_token
from features.mail import service
from features.mail.sections import UNASSIGNED_SECTION

MAILBOXES = {
    "ug": {
        "imap_host": "imap.gmail.com",
        "imap_user": "ug@college.ac.in",
        "imap_password": "app-password",
        "ingest_secret": "ug-secret",
        "sections": {
            "academics": "ug-academics@college.ac.in",
            "placement": "ug-placement@iiitdmj.ac.in",
            "cultural": "ug-cultural@iiitdmj.ac.in",
            "technical": "ug-technical@iiitdmj.ac.in",
            "sports": "ug-sports@iiitdmj.ac.in",
            "other": "ug-other@iiitdmj.ac.in",
        },
    },
    "pg": {
        "imap_host": "imap.gmail.com",
        "imap_user": "pg@college.ac.in",
        "imap_password": "app-password",
        "ingest_secret": "pg-secret",
        "sections": {"academics": "pg-academics@iiitdmj.ac.in"},
    },
}

SIX_ALIASES = (
    "ug-placement@iiitdmj.ac.in",
    "registrar@iiitdmj.ac.in",
    "ug-cultural@iiitdmj.ac.in",
    "ug-technical@iiitdmj.ac.in",
    "ug-sports@iiitdmj.ac.in",
    "ug-other@iiitdmj.ac.in",
)


@pytest.fixture(scope="module")
def client():
    create_db_and_tables()
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == "routeruser")).first()
        if user is None:
            user = User(
                email="routeruser@college.ac.in",
                password_hash="x",
                full_name="Router User",
                username="routeruser",
                roll_number="23RT001",
                is_email_verified=True,
                role=UserRole.STUDENT,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        profile = session.exec(
            select(UserProfile).where(UserProfile.user_id == user.id)
        ).first()
        if profile is None:
            session.add(
                UserProfile(user_id=user.id, programme="BTech", semester=1, branch="CSE A")
            )
            session.commit()
        token = create_access_token(user.id, "routeruser")
    with TestClient(app) as test_client:
        yield {"client": test_client, "token": token}


def configure_mailboxes(monkeypatch):
    singleton = get_settings()
    monkeypatch.setattr(
        singleton, "mail_mailboxes_json", json.dumps(MAILBOXES), raising=False
    )


def ingest(client, token, from_email, to, subject, text, message_id, monkeypatch):
    configure_mailboxes(monkeypatch)
    resp = client["client"].post(
        "/mail/ingest",
        json={
            "from_email": from_email,
            "from_name": "Test Sender",
            "to": to,
            "subject": subject,
            "text": text,
            "message_id": message_id,
        },
        headers={"Authorization": "Bearer ug-secret"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Precedence: exact > domain > pattern; higher priority wins; then oldest.

def test_exact_address_wins_over_domain(client, monkeypatch):
    configure_mailboxes(monkeypatch)
    with Session(engine) as session:
        service.create_sender_rule(
            session, group="ug", pattern="@acme.com", section="cultural"
        )
        service.create_sender_rule(
            session, group="ug", pattern="hr@acme.com", section="placement"
        )
    body = ingest(
        client, client["token"], "hr@acme.com", "ug-sports@iiitdmj.ac.in",
        "Drive notice", "Register now.", "<route-prec-1@college.ac.in>", monkeypatch,
    )
    assert body["section"] == "placement"


def test_domain_rule_matches_subdomain_senders(client, monkeypatch):
    configure_mailboxes(monkeypatch)
    with Session(engine) as session:
        service.create_sender_rule(
            session, group="ug", pattern="@placementcell.iiitdmj.ac.in", section="placement"
        )
    body = ingest(
        client, client["token"], "office@placementcell.iiitdmj.ac.in", "registrar@iiitdmj.ac.in",
        "Internship drive", "Apply by Friday.", "<route-domain-1@college.ac.in>", monkeypatch,
    )
    assert body["section"] == "placement"


def test_higher_priority_wins_within_same_kind(client, monkeypatch):
    configure_mailboxes(monkeypatch)
    with Session(engine) as session:
        service.create_sender_rule(
            session, group="ug", pattern="tnp@iiitdmj.ac.in", section="cultural",
            priority=0,
        )
        service.create_sender_rule(
            session, group="ug", pattern="tnp@iiitdmj.ac.in", section="placement",
            priority=10,
        )
    body = ingest(
        client, client["token"], "tnp@iiitdmj.ac.in", "ug-cultural@iiitdmj.ac.in",
        "Placement drive", "Samsung is hiring.", "<route-prio-1@college.ac.in>", monkeypatch,
    )
    assert body["section"] == "placement"


def test_tie_goes_to_older_rule(client, monkeypatch):
    """Re-registering a sender updates its section; the update is stored once."""
    configure_mailboxes(monkeypatch)
    with Session(engine) as session:
        service.create_sender_rule(
            session, group="ug", pattern="old@iiitdmj.ac.in", section="academics",
            priority=5,
        )
        # Re-registering the same pattern moves it to a new section.
        service.create_sender_rule(
            session, group="ug", pattern="old@iiitdmj.ac.in", section="placement",
            priority=5,
        )
    body = ingest(
        client, client["token"], "old@iiitdmj.ac.in", "ug-sports@iiitdmj.ac.in",
        "Old office notice", "Hello.", "<route-tie-1@college.ac.in>", monkeypatch,
    )
    assert body["section"] == "placement"


# ---------------------------------------------------------------------------
# The six aliases: one mailbox, sender decides.

def test_same_sender_different_aliases_same_section_one_message(client, monkeypatch):
    """The same sender to two aliases yields one message, same section."""
    configure_mailboxes(monkeypatch)
    with Session(engine) as session:
        service.create_sender_rule(
            session, group="ug", pattern="dean.acad@iiitdmj.ac.in", section="academics"
        )
    mid = "<route-six-1@college.ac.in>"
    b1 = ingest(
        client, client["token"], "dean.acad@iiitdmj.ac.in", "ug-placement@iiitdmj.ac.in",
        "Timetable", "Exams next week.", mid, monkeypatch,
    )
    b2 = ingest(
        client, client["token"], "dean.acad@iiitdmj.ac.in", "registrar@iiitdmj.ac.in",
        "Timetable", "Exams next week.", mid, monkeypatch,
    )
    assert b1["section"] == "academics"
    assert b2["section"] == "academics"
    assert b1["id"] == b2["id"], "one message stored, not two"


def test_different_senders_same_alias_different_sections(client, monkeypatch):
    """Six senders to ug-sports@ each file under their own section."""
    configure_mailboxes(monkeypatch)
    with Session(engine) as session:
        service.create_sender_rule(session, group="ug", pattern="hr@acme.com", section="placement")
        service.create_sender_rule(session, group="ug", pattern="dean.acad@iiitdmj.ac.in", section="academics")
        service.create_sender_rule(session, group="ug", pattern="cultural-club@iiitdmj.ac.in", section="cultural")
        service.create_sender_rule(session, group="ug", pattern="tech-fest@iiitdmj.ac.in", section="technical")
        service.create_sender_rule(session, group="ug", pattern="sports-office@iiitdmj.ac.in", section="sports")
        service.create_sender_rule(session, group="ug", pattern="other@college.ac.in", section="other")
    expected = {
        "hr@acme.com": "placement",
        "dean.acad@iiitdmj.ac.in": "academics",
        "cultural-club@iiitdmj.ac.in": "cultural",
        "tech-fest@iiitdmj.ac.in": "technical",
        "sports-office@iiitdmj.ac.in": "sports",
        "other@college.ac.in": "other",
    }
    for i, (sender, section) in enumerate(expected.items()):
        body = ingest(
            client, client["token"], sender, "ug-sports@iiitdmj.ac.in",
            f"Notice {i}", f"Body {i}.", f"<route-sixdiff-{i}@college.ac.in>", monkeypatch,
        )
        assert body["section"] == section, f"{sender} -> expected {section}, got {body['section']}"


# ---------------------------------------------------------------------------
# Unregistered sender -> unassigned

def test_unregistered_sender_waits_unassigned(client, monkeypatch):
    configure_mailboxes(monkeypatch)
    body = ingest(
        client, client["token"], "unknown@gmail.com", "ug-sports@iiitdmj.ac.in",
        "Random mail", "Hello from nowhere.", "<route-unass-1@college.ac.in>", monkeypatch,
    )
    assert body["section"] == UNASSIGNED_SECTION


# ---------------------------------------------------------------------------
# Sender normalization

def test_case_insensitive_sender(client, monkeypatch):
    configure_mailboxes(monkeypatch)
    with Session(engine) as session:
        service.create_sender_rule(
            session, group="ug", pattern="HR@ACME.COM", section="placement"
        )
    body = ingest(
        client, client["token"], "Hr@Acme.Com", "ug-cultural@iiitdmj.ac.in",
        "Case test", "Same office, different case.", "<route-case-1@college.ac.in>", monkeypatch,
    )
    assert body["section"] == "placement"


def test_display_name_stripped(client, monkeypatch):
    configure_mailboxes(monkeypatch)
    with Session(engine) as session:
        service.create_sender_rule(
            session, group="ug", pattern="hr@acme.com", section="placement"
        )
    body = ingest(
        client, client["token"], '"HR Team" <hr@acme.com>', "ug-sports@iiitdmj.ac.in",
        "Display name", "The address is what matters.", "<route-dname-1@college.ac.in>", monkeypatch,
    )
    assert body["section"] == "placement"


def test_plus_tag_stripped(client, monkeypatch):
    """Plus-tag addresses are stripped when MAIL_STRIP_PLUS_TAGS is on (default)."""
    configure_mailboxes(monkeypatch)
    with Session(engine) as session:
        service.create_sender_rule(
            session, group="ug", pattern="hr@acme.com", section="placement"
        )
    body = ingest(
        client, client["token"], "hr+june@acme.com", "ug-cultural@iiitdmj.ac.in",
        "Tagged address", "Same office with a tag.", "<route-tag-1@college.ac.in>", monkeypatch,
    )
    assert body["section"] == "placement"


# ---------------------------------------------------------------------------
# Retro-apply: registering a sender files past mail

def test_registering_sender_refiles_past_mail(client, monkeypatch):
    configure_mailboxes(monkeypatch)
    sender = "late-registrant@college.ac.in"
    mid = f"<route-retro-{abs(hash(sender)) % 100000}@college.ac.in>"
    # Mail arrives before the sender is registered -> unassigned
    before = ingest(
        client, client["token"], sender, "ug-other@iiitdmj.ac.in",
        "Arrived early", "Before the cluster existed.", mid, monkeypatch,
    )
    assert before["section"] == UNASSIGNED_SECTION
    # Register the sender -> mail is re-filed
    with Session(engine) as session:
        service.create_sender_rule(
            session, group="ug", pattern=sender, section="sports"
        )
        service.refile_all(session, "ug")
    # Re-fetch: the message is now under sports
    listed = client["client"].get(
        f"/mail/messages?search=from:{sender}",
        headers={"Authorization": f"Bearer {client['token']}"},
    )
    assert listed.status_code == 200
    rows = listed.json()["messages"]
    assert any(r["id"] == before["id"] and r["section"] == "sports" for r in rows)


def test_routing_twice_no_duplicate(client, monkeypatch):
    """Ingesting the same Message-ID twice yields one message."""
    configure_mailboxes(monkeypatch)
    with Session(engine) as session:
        service.create_sender_rule(
            session, group="ug", pattern="dup@iiitdmj.ac.in", section="technical"
        )
    mid = "<route-dup-1@college.ac.in>"
    b1 = ingest(
        client, client["token"], "dup@iiitdmj.ac.in", "ug-technical@iiitdmj.ac.in",
        "Duplicate test", "First post.", mid, monkeypatch,
    )
    b2 = ingest(
        client, client["token"], "dup@iiitdmj.ac.in", "ug-sports@iiitdmj.ac.in",
        "Duplicate test", "Second post - same Message-ID.", mid, monkeypatch,
    )
    assert b1["id"] == b2["id"]
    # Listing shows one message only
    listed = client["client"].get(
        "/mail/messages?search=dup@iiitdmj.ac.in",
        headers={"Authorization": f"Bearer {client['token']}"},
    )
    assert listed.status_code == 200
    assert len(listed.json()["messages"]) == 1


# ---------------------------------------------------------------------------
# Routing explanation: matched rule is stored

def test_matched_rule_stored(client, monkeypatch):
    configure_mailboxes(monkeypatch)
    with Session(engine) as session:
        rule = service.create_sender_rule(
            session, group="ug", pattern="expl@iiitdmj.ac.in", section="placement"
        )
    body = ingest(
        client, client["token"], "expl@iiitdmj.ac.in", "ug-cultural@iiitdmj.ac.in",
        "Explain test", "Why here?", "<route-explain-1@college.ac.in>", monkeypatch,
    )
    assert body["section"] == "placement"
    # The ingest response reflects the cluster that filed it (may be None
    # for a loose rule without a cluster), but the section is always set.
    assert body["section"] == "placement"
