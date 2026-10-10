"""End-to-end tests for /teams and /hackathons, CampusPilot auth style.

Users are created directly with distinct usernames (the shared scratch database
lives for the whole session), and tokens are minted with create_access_token -
the same pattern test_endpoints.py uses.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

# The database URL is set by tests/conftest.py before any import of the app.
from core.database import create_db_and_tables, engine
from main import app
from models import User, UserProfile
from features.auth.routes import create_access_token


def make_user(username, branch="CSE A", skills=None):
    with Session(engine) as session:
        user = User(
            email=f"{username}@iiitdmj.ac.in", password_hash="x",
            full_name=username.title(), username=username,
            roll_number=f"99XXX{username[:3].upper()}",
            is_email_verified=True, role="student",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        session.add(UserProfile(
            user_id=user.id, first_name=username.title(),
            programme="BTech", semester=5, branch=branch,
            skills=skills or [],
        ))
        session.commit()
        return user.id


@pytest.fixture(scope="module")
def tokens():
    create_db_and_tables()
    owner = make_user("tm_owner", branch="CSE A", skills=["react", "python"])
    mate = make_user("tm_mate", branch="CSE A", skills=["nodejs", "docker"])
    stranger = make_user("tm_stranger", branch="ME", skills=["react", "python"])
    return {
        "owner": create_access_token(owner, "tm_owner"),
        "mate": create_access_token(mate, "tm_mate"),
        "stranger": create_access_token(stranger, "tm_stranger"),
    }


@pytest.fixture(scope="module")
def client(tokens):
    with TestClient(app) as test_client:
        yield test_client, tokens


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def create_team(test_client, token, name="Team Rocket", **kwargs):
    body = {
        "name": name,
        "description": kwargs.pop("description", "A team"),
        "tech_stack": kwargs.pop("tech_stack", ["react", "python"]),
        "max_members": kwargs.pop("max_members", 4),
    }
    body.update(kwargs)
    return test_client.post("/teams", json=body, headers=auth(token))


class TestTeamsCrud:
    def test_create_returns_team_with_owner_member(self, client):
        test_client, tokens = client
        res = create_team(test_client, tokens["owner"], name="Team Alpha")
        assert res.status_code == 201, res.text[:300]
        body = res.json()
        assert body["members_count"] == 1
        assert body["spots_left"] == 3

    def test_duplicate_name_is_rejected(self, client):
        test_client, tokens = client
        res = create_team(test_client, tokens["mate"], name="Team Alpha")
        assert res.status_code == 400

    def test_list_and_detail(self, client):
        test_client, tokens = client
        listed = test_client.get("/teams", headers=auth(tokens["mate"])).json()
        assert listed["pagination"]["total"] >= 1
        team_id = listed["data"][0]["id"]
        detail = test_client.get(f"/teams/{team_id}", headers=auth(tokens["mate"])).json()
        assert len(detail["members"]) >= 1

    def test_update_is_owner_only(self, client):
        test_client, tokens = client
        team_id = test_client.get("/teams", headers=auth(tokens["owner"])).json()["data"][0]["id"]
        denied = test_client.put(
            f"/teams/{team_id}", json={"description": "hijacked"}, headers=auth(tokens["mate"])
        )
        assert denied.status_code == 403
        ok = test_client.put(
            f"/teams/{team_id}", json={"description": "edited"}, headers=auth(tokens["owner"])
        )
        assert ok.status_code == 200 and ok.json()["description"] == "edited"

    def test_delete_is_owner_only(self, client):
        test_client, tokens = client
        doomed = create_team(test_client, tokens["mate"], name="Team Doomed").json()["id"]
        assert test_client.delete(
            f"/teams/{doomed}", headers=auth(tokens["stranger"])
        ).status_code == 403
        assert test_client.delete(
            f"/teams/{doomed}", headers=auth(tokens["mate"])
        ).status_code == 200


class TestJoinAndRequests:
    def test_direct_join_and_leave(self, client):
        test_client, tokens = client
        team_id = create_team(test_client, tokens["owner"], name="Team Open").json()["id"]
        joined = test_client.post(f"/teams/{team_id}/join", headers=auth(tokens["mate"]))
        assert joined.status_code == 200
        assert joined.json()["status"] == "joined"

        again = test_client.post(f"/teams/{team_id}/join", headers=auth(tokens["mate"]))
        assert again.status_code == 409

        left = test_client.post(f"/teams/{team_id}/leave", headers=auth(tokens["mate"]))
        assert left.status_code == 200

    def test_owner_cannot_join_or_leave_own_team(self, client):
        test_client, tokens = client
        team_id = create_team(test_client, tokens["owner"], name="Team Mine").json()["id"]
        assert test_client.post(
            f"/teams/{team_id}/join", headers=auth(tokens["owner"])
        ).status_code == 400
        assert test_client.post(
            f"/teams/{team_id}/leave", headers=auth(tokens["owner"])
        ).status_code == 400

    def test_approval_flow(self, client):
        test_client, tokens = client
        team_id = create_team(
            test_client, tokens["owner"], name="Team Gated", request_to_join=True
        ).json()["id"]
        pending = test_client.post(f"/teams/{team_id}/join", headers=auth(tokens["mate"]))
        assert pending.json()["status"] == "pending"

        incoming = test_client.get("/teams/requests", headers=auth(tokens["owner"])).json()
        req = next(r for r in incoming["requests"] if r["team_name"] == "Team Gated")

        # A non-owner cannot decide.
        assert test_client.put(
            f"/teams/requests/{req['id']}", json={"status": "accepted"},
            headers=auth(tokens["stranger"]),
        ).status_code == 403

        decided = test_client.put(
            f"/teams/requests/{req['id']}", json={"status": "accepted"},
            headers=auth(tokens["owner"]),
        )
        assert decided.json()["status"] == "accepted"

        members = test_client.get(
            f"/teams/{team_id}/members", headers=auth(tokens["owner"])
        ).json()["members"]
        assert {m["user_id"] for m in members} >= {1, 2} or len(members) == 2

    def test_mine_lists_owned_and_joined(self, client):
        test_client, tokens = client
        body = test_client.get("/teams/mine", headers=auth(tokens["owner"])).json()
        assert isinstance(body["teams"], list) and len(body["teams"]) >= 1
        assert all("role" in t for t in body["teams"])


class TestMatching:
    def test_gap_filler_outranks_duplicator(self, client):
        """The behaviour the whole section exists for: `tm_mate` (nodejs,
        docker) closes Team Alpha's gap better than `tm_stranger` who merely
        duplicates its react/python stack.

        The team is created here rather than borrowed from an earlier test in this
        module. That coupling is what made this fail on PostgreSQL while passing
        on SQLite: neither dialect guarantees another test left a team behind,
        SQLite just happened to do it reliably. Each test owning its fixtures is
        the fix; changing the assertion would have hidden a real ordering
        dependency.
        """
        test_client, tokens = client
        alpha = create_team(
            test_client, tokens["owner"], name="Team Alpha Match"
        ).json()["id"]

        updated = test_client.put(
            f"/teams/{alpha}",
            json={"wanted": ["nodejs", "docker"]},
            headers=auth(tokens["owner"]),
        )
        assert updated.status_code == 200, updated.text[:300]

        mate_ranked = test_client.get("/teams/match", headers=auth(tokens["mate"])).json()
        stranger_ranked = test_client.get(
            "/teams/match", headers=auth(tokens["stranger"])
        ).json()
        assert mate_ranked["matches"], "no matches returned to score"
        assert stranger_ranked["matches"], "no matches returned to score"

        # Compare the score for *this* team, not the global maximum, so the
        # assertion cannot pass or fail because of an unrelated team's score.
        def score_for(body, team_id):
            return next(m["score"] for m in body["matches"] if m["id"] == team_id)

        assert score_for(mate_ranked, alpha) > score_for(stranger_ranked, alpha)


class TestHackathons:
    def test_create_and_list_event(self, client):
        test_client, tokens = client
        created = test_client.post(
            "/hackathons",
            json={"title": "SIH 2026", "description": "National hackathon"},
            headers=auth(tokens["owner"]),
        )
        assert created.status_code == 201, created.text[:300]
        listed = test_client.get("/hackathons", headers=auth(tokens["mate"])).json()
        assert any(h["title"] == "SIH 2026" for h in listed["hackathons"])
        assert listed["retention_days"] == 30

    def test_team_linked_to_event_and_discover_filter(self, client):
        test_client, tokens = client
        event_id = next(
            h["id"] for h in test_client.get(
                "/hackathons", headers=auth(tokens["mate"])
            ).json()["hackathons"] if h["title"] == "SIH 2026"
        )
        team = create_team(
            test_client, tokens["mate"], name="Team SIH", hackathon_id=event_id
        )
        assert team.status_code == 201
        filtered = test_client.get(
            f"/teams/match?hackathon_id={event_id}", headers=auth(tokens["owner"])
        ).json()
        assert all(m["hackathon_id"] == event_id for m in filtered["matches"])

    def test_feed_sync_without_credentials_explains_itself(self, client):
        test_client, tokens = client
        res = test_client.post("/hackathons/feed/sync", headers=auth(tokens["owner"]))
        assert res.status_code == 200
        assert res.json()["ok"] is False

    def test_missing_media_is_404(self, client):
        test_client, tokens = client
        assert test_client.get(
            "/hackathons/media/nope.pdf", headers=auth(tokens["owner"])
        ).status_code == 404
