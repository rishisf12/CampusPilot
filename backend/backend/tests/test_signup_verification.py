"""
Tests for verifying the email *before* an account is created.

The reordering matters, so these pin the new order down:

    /auth/signup/start  ->  /auth/signup/verify  ->  /auth/signup

and check the properties that make it safe: nothing is created until the address
is proven, the first step cannot be used to discover who has an account, and the
code cannot be guessed.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, delete, select

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.database as database  # noqa: E402
from main import app  # noqa: E402
from models import PendingSignup, User, UserProfile  # noqa: E402
from features.auth import signup as svc  # noqa: E402

EMAIL = "newstudent@iiitdmj.ac.in"
USERNAME = "newstudent"
PASSWORD = "Test@12345"

DETAILS = {
    "first_name": "New",
    "last_name": "Student",
    "gender": "Other",
    "programme": "BTech",
    "semester": 5,
    "branch": "CSE A",
    "username": USERNAME,
    "roll_number": "23BCS950",
    "email": EMAIL,
    "password": PASSWORD,
}


#: Usernames this module creates directly in the database, as well as the one the
#: API creates on success. Cleanup must cover all of them, or a leaked row collides
#: with the next test's insert on the UNIQUE username constraint.
TEST_USERNAMES = ("already_here", "newstudent", "newstudent2")


def _purge(db: Session) -> None:
    """Scoped to this module: the scratch database is shared."""
    db.exec(delete(PendingSignup))
    doomed = [
        user
        for user in db.exec(select(User)).all()
        if user.username in TEST_USERNAMES or user.username.startswith("newstudent")
    ]
    for user in doomed:
        # Profiles go first: user_profile.user_id is UNIQUE, and an orphaned
        # profile would collide with the next test's new user, which reuses the id.
        db.exec(delete(UserProfile).where(UserProfile.user_id == user.id))
        db.delete(user)
    db.commit()


def accounts_on(db: Session, email: str) -> list:
    """Accounts on this address - not every account in the shared database."""
    return list(db.exec(select(User).where(User.email == email)).all())


@pytest.fixture()
def db():
    engine = create_engine(database.engine.url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _purge(session)
        yield session
        _purge(session)


@pytest.fixture()
def client(db):
    with TestClient(app) as test_client:
        yield test_client


def _naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def prove(db, email=EMAIL):
    """Drive start+verify in the service, returning the code used."""
    code, _ = svc.start(db, email)
    svc.verify(db, email, code)
    return code


class TestStartStep:
    def test_creates_no_account(self, client, db):
        response = client.post("/auth/signup/start", json={"email": EMAIL})
        assert response.status_code == 200
        # The whole point: nothing exists yet.
        assert db.exec(select(User).where(User.email == EMAIL)).first() is None
        assert db.exec(select(PendingSignup)).all()

    def test_sends_no_account_detail(self, client, db):
        body = client.post("/auth/signup/start", json={"email": EMAIL}).json()
        assert "registered" not in body["message"].lower()
        assert "code is on its way" in body["message"]

    def test_an_invalid_address_is_rejected(self, client, db):
        # 422, not 400: the request body itself is malformed, so it is rejected by
        # validation before the endpoint runs at all. That is the correct code for a
        # bad body, and it reveals nothing about whether the address exists.
        response = client.post("/auth/signup/start", json={"email": "not-an-email"})
        assert response.status_code == 422
        assert db.exec(select(PendingSignup)).all() == []

    def test_the_service_also_refuses_a_malformed_address(self, db):
        """Defence in depth: the shape check does not rely on the body model."""
        with pytest.raises(svc.SignupVerificationError):
            svc.start(db, "not-an-email")

    def test_a_duplicate_address_is_not_revealed(self, client, db):
        """Asking about a registered address must look like asking about any other."""
        db.add(
            User(
                email=EMAIL,
                password_hash="x",
                username="already_here",
                roll_number="23BCS949",
                is_email_verified=True,
            )
        )
        db.commit()
        taken = client.post("/auth/signup/start", json={"email": EMAIL}).json()
        _purge(db)
        free = client.post("/auth/signup/start", json={"email": "brandnew@iiitdmj.ac.in"}).json()
        assert taken == free

    def test_resending_too_soon_looks_the_same_as_sending(self, client, db):
        first = client.post("/auth/signup/start", json={"email": EMAIL})
        second = client.post("/auth/signup/start", json={"email": EMAIL})
        assert first.json() == second.json()
        assert second.status_code == 200

    def test_the_code_is_not_stored_in_the_clear(self, client, db):
        client.post("/auth/signup/start", json={"email": EMAIL})
        row = db.exec(select(PendingSignup)).first()
        assert len(row.code_hash) == 64
        assert not row.code_hash.isdigit()

    def test_the_email_is_stored_lower_cased(self, client, db):
        client.post("/auth/signup/start", json={"email": "MiXeD@IIITDMJ.ac.in"})
        row = db.exec(select(PendingSignup)).first()
        assert row.email == "mixed@iiitdmj.ac.in"


class TestVerifyStep:
    def test_a_wrong_code_is_refused(self, client, db):
        client.post("/auth/signup/start", json={"email": EMAIL})
        response = client.post("/auth/signup/verify", json={"email": EMAIL, "code": "000000"})
        assert response.status_code == 400
        assert not svc.is_verified(db, EMAIL)

    def test_the_right_code_verifies(self, client, db):
        code, _ = svc.start(db, EMAIL)
        response = client.post("/auth/signup/verify", json={"email": EMAIL, "code": code})
        assert response.status_code == 200
        assert svc.is_verified(db, EMAIL)

    def test_a_code_cannot_be_replayed(self, client, db):
        code, _ = svc.start(db, EMAIL)
        client.post("/auth/signup/verify", json={"email": EMAIL, "code": code})
        again = client.post("/auth/signup/verify", json={"email": EMAIL, "code": code})
        assert again.status_code == 400

    def test_an_expired_code_is_refused(self, client, db):
        code, _ = svc.start(db, EMAIL)
        row = db.exec(select(PendingSignup)).first()
        row.created_at = _naive_now() - svc.CODE_TTL - timedelta(minutes=1)
        db.add(row)
        db.commit()
        response = client.post("/auth/signup/verify", json={"email": EMAIL, "code": code})
        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower()

    def test_guessing_is_cut_off(self, client, db):
        code, _ = svc.start(db, EMAIL)
        for _ in range(svc.MAX_ATTEMPTS):
            response = client.post("/auth/signup/verify", json={"email": EMAIL, "code": "000000"})
            assert response.status_code == 400
        # The row is gone, not merely blocked.
        assert db.exec(select(PendingSignup)).all() == []

    def test_asking_for_a_new_code_resets_the_budget_too_far(self, client, db):
        """The right code must not work once the budget is spent."""
        code, _ = svc.start(db, EMAIL)
        for _ in range(svc.MAX_ATTEMPTS):
            client.post("/auth/signup/verify", json={"email": EMAIL, "code": "000000"})
        with pytest.raises(svc.SignupVerificationError):
            svc.verify(db, EMAIL, code)

    def test_an_unverified_address_is_not_verified(self, client, db):
        assert not svc.is_verified(db, "never@iiitdmj.ac.in")


class TestCreateStep:
    def test_refused_without_verification(self, client, db):
        """The gate: no code, no account."""
        response = client.post("/auth/signup", json=DETAILS)
        assert response.status_code == 400
        assert "verify" in response.json()["detail"].lower()
        assert db.exec(select(User).where(User.email == EMAIL)).first() is None

    def test_refused_when_the_address_was_never_started(self, client, db):
        response = client.post("/auth/signup", json=DETAILS)
        assert response.status_code == 400
        assert accounts_on(db, EMAIL) == []

    def test_creates_the_account_once_verified(self, client, db):
        prove(db)
        response = client.post("/auth/signup", json=DETAILS)
        assert response.status_code == 200
        user = db.exec(select(User).where(User.email == EMAIL)).first()
        assert user is not None
        assert user.username == USERNAME

    def test_the_account_starts_verified(self, client, db):
        """No second code: the mailbox was already proven."""
        prove(db)
        client.post("/auth/signup", json=DETAILS)
        user = db.exec(select(User).where(User.email == EMAIL)).first()
        db.refresh(user)
        assert user.is_email_verified is True

    def test_it_can_sign_in_straight_away(self, client, db):
        prove(db)
        client.post("/auth/signup", json=DETAILS)
        assert client.post(
            "/auth/login", data={"username": USERNAME, "password": PASSWORD}
        ).status_code == 200

    def test_a_profile_is_created(self, client, db):
        prove(db)
        client.post("/auth/signup", json=DETAILS)
        user = db.exec(select(User).where(User.email == EMAIL)).first()
        profile = db.exec(select(UserProfile).where(UserProfile.user_id == user.id)).first()
        assert profile is not None
        assert profile.branch == "CSE A"
        assert profile.semester == 5

    def test_the_pending_record_is_cleared(self, client, db):
        prove(db)
        client.post("/auth/signup", json=DETAILS)
        assert db.exec(select(PendingSignup)).all() == []

    def test_proof_expires(self, client, db):
        """A verification from an hour ago must not still open the door."""
        prove(db)
        row = db.exec(select(PendingSignup)).first()
        row.verified_at = _naive_now() - svc.VERIFIED_TTL - timedelta(minutes=1)
        db.add(row)
        db.commit()
        response = client.post("/auth/signup", json=DETAILS)
        assert response.status_code == 400
        assert accounts_on(db, EMAIL) == []

    def test_a_proof_is_for_one_address_only(self, client, db):
        """Proving yours must not let you claim someone else's address."""
        prove(db, EMAIL)
        response = client.post("/auth/signup", json={**DETAILS, "email": "someoneelse@iiitdmj.ac.in"})
        assert response.status_code == 400
        assert accounts_on(db, EMAIL) == []

    def test_duplicate_email_is_reported_after_proof(self, client, db):
        """Safe to report now: the requester owns the mailbox."""
        db.add(
            User(
                email=EMAIL,
                password_hash="x",
                username="already_here",
                roll_number="23BCS949",
                is_email_verified=True,
            )
        )
        db.commit()
        prove(db)
        response = client.post("/auth/signup", json=DETAILS)
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]

    def test_duplicate_username_is_still_caught(self, client, db):
        db.add(
            User(
                email="taken@iiitdmj.ac.in",
                password_hash="x",
                username=USERNAME,
                roll_number="23BCS948",
                is_email_verified=True,
            )
        )
        db.commit()
        prove(db)
        response = client.post("/auth/signup", json=DETAILS)
        assert response.status_code == 400
        assert "username" in response.json()["detail"].lower()


class TestResendForThisFlow:
    def test_reveals_nothing_about_resending(self, client, db):
        first = client.post("/auth/signup/start", json={"email": EMAIL}).json()
        second = client.post("/auth/signup/start", json={"email": EMAIL}).json()
        assert first == second

    def test_the_cooldown_is_measured_per_address(self, client, db):
        client.post("/auth/signup/start", json={"email": EMAIL})
        svc.start(db, "other@iiitdmj.ac.in")  # must not raise

    def test_retry_seconds_are_reported_to_the_service(self, db):
        svc.start(db, EMAIL)
        assert svc.seconds_until_retry(db, EMAIL) > 0
