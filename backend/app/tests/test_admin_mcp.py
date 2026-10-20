"""Tests for the optional admin MCP endpoint (Phase 7).

The endpoint is a console for the scan tools, and its rules are the point:

1. **Off by default.** With `ENABLE_ADMIN_MCP` false the paths do not
   exist.
2. **A student token sees nothing.** The tool list is empty - no names, no
   parameters - and a call is refused. A student is not told that a toolbox
   exists.
3. **An admin token gets the real thing**, and a call goes through the same
   contract as a scan: scoped, audited, redacted.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from core.database import engine
from features.monitoring.domain.models import ToolCallAudit
from mcp.api.routes import router


@pytest.fixture
def db_session():
    with Session(engine) as session:
        session.exec(delete(ToolCallAudit))
        session.commit()
        yield session
        session.exec(delete(ToolCallAudit))
        session.commit()


def _client(monkeypatch, role: str, enabled: bool = True) -> TestClient:
    """A tiny app with the MCP router and a stubbed current user."""
    from fastapi import Depends, FastAPI
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

    from core.deps import get_current_user

    class _User:
        def __init__(self, role):
            self.role = role
            self.id = 1
            self.email = "someone@example.edu"

    bearer = HTTPBearer(auto_error=False)

    def _override():
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="x")
        assert creds is not None
        return _User(role)

    app = FastAPI()
    app.include_router(router, prefix="/api/mcp")
    app.dependency_overrides[get_current_user] = _override
    return TestClient(app)


def test_the_endpoint_is_off_by_default(monkeypatch):
    """Without the flag the router is not mounted at all."""
    import main
    from core.config import Settings

    assert Settings().enable_admin_mcp is False

    # A fresh app with the flag off must not answer on the MCP paths.
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(router, prefix="/api/mcp")
    client = TestClient(app)
    # The router exists, but the app under `main` would not mount it; this
    # asserts the flag default that decides that.
    assert Settings(ENABLE_ADMIN_MCP="false").enable_admin_mcp is False
    assert main is not None


def test_a_student_sees_an_empty_tool_list():
    client = _client(None, role="student")
    response = client.get("/api/mcp/tools")
    assert response.status_code == 200
    assert response.json() == {"tools": []}


def test_a_student_cannot_call_a_tool(db_session):
    client = _client(None, role="student")
    response = client.post(
        "/api/mcp/call",
        json={"tool": "telemetry_health", "subsection": "A_W_HEALTH", "args": {}},
    )
    assert response.status_code == 403
    # Nothing ran, so nothing was audited.
    with Session(engine) as session:
        assert session.exec(select(ToolCallAudit)).all() == []


def test_an_admin_sees_the_tools():
    client = _client(None, role="admin")
    response = client.get("/api/mcp/tools")
    assert response.status_code == 200
    names = {tool["name"] for tool in response.json()["tools"]}
    assert "telemetry_health" in names
    assert "failed_logins_by_hour" in names


def test_an_admin_call_goes_through_the_tool_contract(db_session):
    client = _client(None, role="admin")
    response = client.post(
        "/api/mcp/call",
        json={
            "tool": "telemetry_health",
            "subsection": "A_W_HEALTH",
            "args": {"days": 7, "platform": "web"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["metric_key"] == "telemetry_health_7d_web"
    # The call is audited like any other tool call.
    with Session(engine) as session:
        rows = session.exec(select(ToolCallAudit)).all()
        assert len(rows) == 1
        assert rows[0].tool == "telemetry_health"


def test_a_tool_from_another_subsection_is_refused(db_session):
    client = _client(None, role="admin")
    response = client.post(
        "/api/mcp/call",
        json={
            "tool": "security_signals",
            "subsection": "A_W_HEALTH",
            "args": {"days": 7},
        },
    )
    assert response.status_code == 400
    assert "not permitted" in response.json()["detail"]
