"""
Tests for the email-backed hackathon feed.

The interesting behaviour is all defensive: a public mailbox means the input is
hostile, and retention means the sweep has to remove files as well as rows.
Both are silent when broken, so they are pinned here rather than checked by eye.
"""
import datetime
import email.message
from email.message import EmailMessage
from pathlib import Path

import pytest
from sqlmodel import select

from core.database import create_db_and_tables
from features.teams import feed


@pytest.fixture(autouse=True)
def fresh_team_tables():
    """Empty the team/feed tables around each feed test (module-scoped).

    Row deletes rather than drop_all: on Windows the scratch SQLite file is
    locked while the engine pool holds it, so dropping fails. Other modules
    build their own data in module-scoped fixtures, so a wipe here cannot
    strand them.
    """
    from sqlmodel import Session

    from core.database import create_db_and_tables, engine
    from models import FeedCursor, Hackathon, JoinRequest, Team, TeamMember, User, UserProfile

    def wipe():
        create_db_and_tables()
        with Session(engine) as session:
            for model in (FeedCursor, Hackathon, JoinRequest, TeamMember, Team, UserProfile, User):
                for row in session.exec(select(model)).all():
                    session.delete(row)
            session.commit()

    wipe()
    yield
    wipe()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as test_client:
        yield test_client


def build_message(subject="Smart India Hackathon", body="", html=None, sender="sender@example.com", attachments=(), date="Mon, 05 Oct 2026 09:00:00 +0530"):
    """
    Build a message. `html` sets an HTML-only body when `body` is left blank -
    `add_alternative` alongside `set_content` would always yield a text/plain
    alternative too, which is not what an HTML-only mail looks like.
    """
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    if date:
        message["Date"] = date
    if html is not None:
        message.set_content(html, subtype="html")
    else:
        message.set_content(body)
    for name, data, subtype in attachments:
        maintype, _, sub = subtype.partition("/")
        message.add_attachment(data, maintype=maintype, subtype=sub or "octet-stream", filename=name)
    return message


class TestSanitisation:
    """The feed renders attacker-controlled email, so flattening matters."""

    def test_script_tags_are_removed_with_their_content(self):
        text, _ = feed.html_to_text("<p>Hello</p><script>alert('xss')</script>")
        assert "Hello" in text
        assert "alert" not in text
        assert "script" not in text.lower()

    def test_style_and_head_content_is_removed(self):
        text, _ = feed.html_to_text("<style>body{display:none}</style><p>Visible</p>")
        assert "Visible" in text
        assert "display" not in text

    def test_iframe_is_dropped(self):
        text, _ = feed.html_to_text("<p>Hi</p><iframe src='http://evil.test'></iframe>")
        assert "Hi" in text
        assert "iframe" not in text.lower()

    def test_markup_is_stripped_but_text_survives(self):
        text, _ = feed.html_to_text("<div><h1>SIH 2026</h1><p>Registrations open.</p></div>")
        assert "SIH 2026" in text
        assert "Registrations open." in text
        assert "<" not in text and ">" not in text

    def test_javascript_urls_are_refused(self):
        assert feed.is_safe_url("javascript:alert(1)") is False
        assert feed.is_safe_url("data:text/html;base64,PHNjcmlwdD4=") is False
        assert feed.is_safe_url("vbscript:msgbox") is False

    def test_http_and_https_are_kept(self):
        assert feed.is_safe_url("https://sih.gov.in") is True
        assert feed.is_safe_url("http://example.test/x") is True

    def test_javascript_href_is_not_collected(self):
        _, links = feed.html_to_text('<a href="javascript:alert(1)">click</a>')
        assert all(feed.is_safe_url(link) for link in links)

    def test_safe_href_is_collected(self):
        _, links = feed.html_to_text('<a href="https://sih.gov.in/apply">Apply</a>')
        assert "https://sih.gov.in/apply" in links

    def test_anchor_label_does_not_merge_into_the_prose(self):
        """Two adjacent links must not run together as one word.

        The href is rendered separately from `links`, so keeping the visible
        label as well produced read-on strings like `badApply`.
        """
        text, links = feed.html_to_text(
            '<p>Registrations open.</p>'
            '<a href="javascript:alert(1)">bad</a>'
            '<a href="https://sih.gov.in">Apply</a>'
        )
        assert "Registrations open." in text
        assert "badApply" not in text
        assert "bad" not in text
        assert "Apply" not in text
        assert links == ["https://sih.gov.in"]

    def test_prose_around_a_link_survives(self):
        text, _ = feed.html_to_text(
            'Register <a href="https://x.test">here</a> before Friday.'
        )
        assert "Register" in text
        assert "before Friday." in text

    def test_malformed_html_does_not_raise(self):
        text, _ = feed.html_to_text("<p>unclosed <b>bold <script>x(")
        assert isinstance(text, str)

    def test_empty_input(self):
        assert feed.html_to_text("") == ("", [])

    def test_html_alternative_is_used_when_no_plain_part(self):
        message = build_message(html="<p>From HTML</p>")
        assert message.is_multipart() is False
        text, _ = feed.sanitize_body(message)
        assert "From HTML" in text

    def test_plain_part_is_preferred_over_html(self):
        message = EmailMessage()
        message["Subject"] = "Both"
        message.set_content("plain version")
        message.add_alternative("<p>html version</p>", subtype="html")
        text, _ = feed.sanitize_body(message)
        assert "plain version" in text
        assert "html version" not in text


class TestReplyChain:
    def test_quoted_history_is_cut(self):
        body = "Real notice here.\n\n-----Original Message-----\nold stuff"
        text, _ = feed.sanitize_body(build_message(body=body))
        assert "Real notice here." in text
        assert "old stuff" not in text

    def test_forwarded_block_is_cut(self):
        body = "Real notice.\n\nOn Mon, someone wrote:\nprevious chatter"
        text, _ = feed.sanitize_body(build_message(body=body))
        assert "Real notice." in text
        assert "previous chatter" not in text

    def test_angled_quote_is_cut(self):
        body = "Real notice.\n> someone else said this"
        text, _ = feed.sanitize_body(build_message(body=body))
        assert "someone else said this" not in text


class TestTitle:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Smart India Hackathon", "Smart India Hackathon"),
            ("Re: Smart India Hackathon", "Smart India Hackathon"),
            ("Fwd: Smart India Hackathon", "Smart India Hackathon"),
            ("RE: FW: SIH", "SIH"),
            ("  spaced  ", "spaced"),
            ("", "(no subject)"),
            (None, "(no subject)"),
        ],
    )
    def test_prefixes_stripped(self, raw, expected):
        assert feed.subject_to_title(raw) == expected

    def test_title_is_length_capped(self):
        assert len(feed.subject_to_title("x" * 900)) <= 200


class TestSender:
    def test_name_and_address_kept(self):
        assert feed.sender_of(build_message(sender="Diya Nair <diya@iiitdmj.ac.in>")) == (
            "Diya Nair <diya@iiitdmj.ac.in>"
        )

    def test_bare_address(self):
        assert feed.sender_of(build_message(sender="noreply@hack.test")) == "noreply@hack.test"

    def test_reply_to_wins(self):
        message = build_message(sender="bot@hack.test")
        message["Reply-To"] = "organisers@hack.test"
        assert "organisers@hack.test" in feed.sender_of(message)

    def test_missing_header(self):
        message = build_message()
        del message["From"]
        assert feed.sender_of(message) is None


class TestReceivedAt:
    def test_uses_the_date_header_not_import_time(self):
        """Retention must count from when the notice was sent.

        A two-month-old newsletter imported today would otherwise stay a full
        month and defeat the whole point of the window.
        """
        message = build_message(date="Mon, 01 Jun 2026 09:00:00 +0530")
        parsed = feed.received_at_of(message)
        assert parsed.month == 6
        assert parsed.year == 2026

    def test_bad_date_falls_back_to_now(self):
        message = build_message(date="not a date")
        assert isinstance(feed.received_at_of(message), datetime.datetime)

    def test_absent_date_falls_back_to_now(self):
        message = build_message(date=None)
        assert isinstance(feed.received_at_of(message), datetime.datetime)

    def test_result_is_naive_for_the_column(self):
        assert feed.received_at_of(build_message()).tzinfo is None


class TestAttachments:
    def test_allowed_type_gets_a_generated_name(self):
        stored, display = feed.safe_filename("poster.pdf", b"%PDF-1.7 stuff")
        assert stored.endswith(".pdf")
        assert display == "poster.pdf"
        assert stored != "poster.pdf"

    def test_executable_extension_is_refused(self):
        assert feed.safe_filename("payload.exe", b"MZ\x90\x00")[0] == ""
        assert feed.safe_filename("run.sh", b"#!/bin/sh")[0] == ""
        assert feed.safe_filename("x.msi", b"\xd0\xcf")[0] == ""

    def test_mislabelled_executable_is_refused_by_magic_bytes(self):
        """
        The extension allowlist only covers the name. A `.pdf` carrying an MZ
        header has to be refused too, or this mailbox is a file host.
        """
        assert feed.safe_filename("innocent.pdf", b"MZ\x90\x00binary")[0] == ""
        assert feed.safe_filename("rules.txt", b"\x7fELF\x02\x01\x01")[0] == ""
        assert feed.safe_filename("notes.txt", b"#!/bin/sh\nrm -rf /")[0] == ""

    def test_extensionless_binary_is_identified_from_content(self):
        stored, _ = feed.safe_filename("blob", b"\x89PNG\r\n\x1a\n" + b"rest")
        assert stored.endswith(".png")

    def test_unknown_binary_is_refused(self):
        assert feed.safe_filename("mystery", b"\x01\x02\x03\x04\x05")[0] == ""

    def test_path_traversal_in_filename_is_neutralised(self):
        stored, display = feed.safe_filename("../../etc/passwd.txt", b"hello")
        assert "/" not in stored and ".." not in stored
        assert display == "passwd.txt"

    def test_windows_path_in_filename_is_neutralised(self):
        _, display = feed.safe_filename(r"C:\windows\system32\evil.txt", b"hello")
        assert "\\" not in display

    def test_save_respects_the_attachment_count_cap(self, monkeypatch):
        monkeypatch.setattr(feed.settings, "feed_max_attachments", 2)
        message = build_message(
            attachments=[
                (f"a{i}.txt", b"hello", "text/plain") for i in range(5)
            ]
        )
        stored, _ = feed.save_attachments(message)
        assert len(stored) == 2

    def test_save_respects_the_size_cap(self, monkeypatch, tmp_path):
        monkeypatch.setattr(feed.settings, "feed_media_dir", tmp_path)
        monkeypatch.setattr(feed.settings, "feed_max_attachment_bytes", 10)
        message = build_message(attachments=[("big.txt", b"x" * 500, "text/plain")])
        assert feed.save_attachments(message) == ([], [])


class TestDeleteMedia:
    def test_removes_a_stored_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr(feed.settings, "feed_media_dir", tmp_path)
        target = tmp_path / "abc123.pdf"
        target.write_bytes(b"%PDF")
        assert feed.delete_media(["abc123.pdf"]) == 1
        assert not target.exists()

    def test_refuses_to_escape_the_directory(self, monkeypatch, tmp_path):
        monkeypatch.setattr(feed.settings, "feed_media_dir", tmp_path / "media")
        (tmp_path / "media").mkdir()
        outside = tmp_path / "precious.txt"
        outside.write_text("keep me")

        assert feed.delete_media(["../precious.txt"]) == 0
        assert outside.exists()

    def test_missing_file_is_not_an_error(self, monkeypatch, tmp_path):
        monkeypatch.setattr(feed.settings, "feed_media_dir", tmp_path)
        assert feed.delete_media(["gone.pdf"]) == 0


class TestRetention:
    def test_cutoff_is_the_configured_window(self):
        assert feed.settings.feed_retention_days == 30
        assert (datetime.datetime.utcnow() - feed.cutoff()).days == 30

    def test_purge_removes_old_rows(self, client):
        from core.database import engine as _  # noqa: F401
        from sqlmodel import Session, select
        from models import Hackathon

        from core.database import engine

        with Session(engine) as session:
            old = Hackathon(title="Ancient", created_at=datetime.datetime.utcnow() - datetime.timedelta(days=45))
            new = Hackathon(title="Fresh", created_at=datetime.datetime.utcnow() - datetime.timedelta(days=3))
            session.add(old)
            session.add(new)
            session.commit()

            result = feed.purge_expired(session)
            assert result["entries"] == 1

            remaining = session.exec(select(Hackathon)).all()
            assert [row.title for row in remaining] == ["Fresh"]

    def test_purge_also_deletes_the_attachment_files(self, client, monkeypatch, tmp_path):
        from sqlmodel import Session
        from models import Hackathon

        from core.database import engine

        monkeypatch.setattr(feed.settings, "feed_media_dir", tmp_path)
        stored = tmp_path / "old.pdf"
        stored.write_bytes(b"%PDF-1.7")

        with Session(engine) as session:
            session.add(
                Hackathon(
                    title="Ancient with paper",
                    attachments=["old.pdf"],
                    created_at=datetime.datetime.utcnow() - datetime.timedelta(days=90),
                )
            )
            session.commit()

            result = feed.purge_expired(session)

        assert result == {"entries": 1, "files": 1}
        assert not stored.exists()

    def test_purge_with_nothing_to_do(self, client):
        from sqlmodel import Session
        from core.database import engine

        with Session(engine) as session:
            assert feed.purge_expired(session) == {"entries": 0, "files": 0}


class TestOrphanSweep:
    """
    Rows and files are written separately, so a crash between them leaves files
    behind with no owning row. The window exists to bound disk use, so a sweep
    that only walked rows would leak forever.
    """

    def test_orphaned_file_is_detected_and_removed(self, client, monkeypatch, tmp_path):
        from sqlmodel import Session
        from models import Hackathon
        from core.database import engine

        monkeypatch.setattr(feed.settings, "feed_media_dir", tmp_path)
        kept = tmp_path / "kept.pdf"
        kept.write_bytes(b"%PDF-1.7")
        lost = tmp_path / "lost.pdf"
        lost.write_bytes(b"%PDF-1.7")

        with Session(engine) as session:
            session.add(Hackathon(title="Kept", attachments=["kept.pdf"]))
            session.commit()

            assert feed.orphan_media(session) == ["lost.pdf"]
            assert feed.sweep_orphans(session) == 1

        assert kept.exists()
        assert not lost.exists()

    def test_purge_also_collects_orphans(self, client, monkeypatch, tmp_path):
        from sqlmodel import Session
        from core.database import engine

        monkeypatch.setattr(feed.settings, "feed_media_dir", tmp_path)
        stray = tmp_path / "stray.png"
        stray.write_bytes(b"\x89PNG\r\n\x1a\n")

        with Session(engine) as session:
            result = feed.purge_expired(session)

        assert result["files"] == 1
        assert not stray.exists()

    def test_no_media_dir_is_not_an_error(self, client, monkeypatch, tmp_path):
        from sqlmodel import Session
        from core.database import engine

        monkeypatch.setattr(feed.settings, "feed_media_dir", tmp_path / "does-not-exist")
        with Session(engine) as session:
            assert feed.orphan_media(session) == []


class TestExpiryReporting:
    """
    The card says when an entry will be swept. Measuring that from a single
    global expiry instead of per row returns zero for everything, because the
    global expiry *is* `now` - so the field silently reads as "expires today".
    """

    def _entry(self, client, age_days):
        """Days-to-expiry reported for an entry that arrived `age_days` ago."""
        from sqlmodel import Session

        from core.database import engine
        from models import Hackathon, User
        from features.auth.routes import create_access_token

        title = f"Aged {age_days}"
        with Session(engine) as session:
            session.add(
                Hackathon(
                    title=title,
                    body_text="body",
                    created_at=datetime.datetime.utcnow() - datetime.timedelta(days=age_days),
                )
            )
            user = User(
                email="feedalice@iiitdmj.ac.in", password_hash="x",
                full_name="Feed Alice", username="feedalice",
                is_email_verified=True, role="student",
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            token = create_access_token(user.id, user.username)
        response = client.get(
            "/hackathons", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, response.text
        payload = response.json()

        for row in payload["hackathons"]:
            if row["title"] == title:
                return row["expires_in_days"]
        raise AssertionError("entry missing from the feed")

    def test_fresh_entry_has_the_full_window(self, client):
        assert self._entry(client, 0) == 30

    def test_entry_aged_ten_days_expires_in_twenty(self, client):
        assert self._entry(client, 10) == 20

    def test_entry_aged_twenty_five_expires_in_five(self, client):
        assert self._entry(client, 25) == 5

    def test_never_reports_negative(self, client):
        assert self._entry(client, 29) >= 0

    def test_window_is_the_configured_retention(self, client):
        from sqlmodel import Session

        from core.database import engine
        from models import User
        from features.auth.routes import create_access_token

        with Session(engine) as session:
            user = User(
                email="feedbob@iiitdmj.ac.in", password_hash="x",
                full_name="Feed Bob", username="feedbob",
                is_email_verified=True, role="student",
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            token = create_access_token(user.id, user.username)
        response = client.get(
            "/hackathons", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.json()["retention_days"] == 30


class TestIngestionIsSafeWhenUnconfigured:
    def test_disabled_without_credentials(self, client):
        from sqlmodel import Session
        from core.database import engine

        assert feed.settings.feed_enabled is False
        with Session(engine) as session:
            result = feed.ingest_once(session)
        assert result["ok"] is False
        assert "not configured" in result["reason"]
        assert result["added"] == 0

    def test_no_network_call_when_disabled(self, client, monkeypatch):
        """Must not attempt a connection, so the endpoint is safe to expose."""
        import imaplib

        from sqlmodel import Session
        from core.database import engine

        def explode(*args, **kwargs):
            raise AssertionError("imaplib must not be touched when unconfigured")

        monkeypatch.setattr(feed.imaplib, "IMAP4_SSL", explode)

        with Session(engine) as session:
            assert feed.ingest_and_purge(session)["ok"] is False


class TestEntryConstruction:
    def test_builds_an_entry_from_a_message(self, client, monkeypatch, tmp_path):
        from sqlmodel import Session
        from core.database import engine

        monkeypatch.setattr(feed.settings, "feed_media_dir", tmp_path)
        message = EmailMessage()
        message["Subject"] = "CodeSprint Finals"
        message["From"] = "organisers@codesprint.test"
        message["Date"] = "Mon, 05 Oct 2026 09:00:00 +0530"
        message.set_content(
            '<p>Twelve hours, one theme.</p><a href="https://codesprint.test">Register</a>',
            subtype="html",
        )
        message.add_attachment(
            b"\x89PNG\r\n\x1a\ndata", maintype="image", subtype="png", filename="poster.png"
        )

        with Session(engine) as session:
            entry = feed._entry_from(message, uid=42)
            assert entry is not None
            assert entry.title == "CodeSprint Finals"
            assert "Twelve hours, one theme." in entry.body_text
            # Anchor text is part of the prose once HTML is flattened, so it
            # shows in the dropdown too. The href is what gets vetted.
            assert entry.link == "https://codesprint.test"
            assert entry.source == "email"
            assert entry.feed_uid == 42
            assert len(entry.attachments) == 1

    def test_empty_message_is_dropped(self, client, monkeypatch, tmp_path):
        monkeypatch.setattr(feed.settings, "feed_media_dir", tmp_path)
        message = build_message(subject="", body="")
        assert feed._entry_from(message, uid=1) is None

    def test_body_is_length_capped(self, client, monkeypatch, tmp_path):
        from sqlmodel import Session
        from core.database import engine

        monkeypatch.setattr(feed.settings, "feed_media_dir", tmp_path)
        monkeypatch.setattr(feed.settings, "feed_max_body_chars", 50)
        with Session(engine) as session:
            entry = feed._entry_from(build_message(body="y" * 900), uid=7)
        assert len(entry.body_text) <= 50
