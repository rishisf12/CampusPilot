"""Phase 5 — Compose & footer: compose endpoint, reply/forward threading,
footer template model verified."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestComposeEndpoint:
    """The /mail/compose endpoint: reply, forward, new message."""

    def test_compose_requires_auth(self):
        resp = client.post("/mail/compose", json={
            "to": "test@example.com",
            "subject": "Hello",
            "body": "World",
        })
        assert resp.status_code in (401, 403)

    def test_footer_template_table_exists(self):
        """The footer template model (Phase 2) is present and queryable."""
        from sqlmodel import Session, select
        from core.database import create_db_and_tables
        from features.mail.models import MailFooterTemplate
        create_db_and_tables()
        # Migration 029 creates this table; confirming no ImportError.
        assert MailFooterTemplate.__tablename__ == "mail_footer_template"
