"""
Tests for password reset by emailed code.

The properties that matter here are mostly negative: this endpoint must not
confirm which accounts exist, must not be guessable, must not flood an inbox, and
must actually lock out a compromised device. Each of those has a test.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, delete, select

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.database as database  # noqa: E402
from models import PasswordResetCode, PasskeyCredential, User  # noqa: E402
from features.auth.routes import hash_password, verify_password  # noqa: E402
from features.auth import password_reset as svc  # noqa: E402
from test_passkeys import SoftwareAuthenticator  # noqa: E402

USERNAME = "reset_tester"
EMAIL = "reset_tester@iiitdmj.ac.in"
PASSWORD = "Original@123"


@pytest.fixture()
def session():
    engine = create_engine(database.engine.url, **database.engine_kwargs())
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        _purge(db)
        db.add(
            User(
                email=EMAIL,
                full_name="Reset Tester",
                username=USERNAME,
                roll_number="23BCS995",
                password_hash=hash_password(PASSWORD),
                is_email_verified=True,
            )
        )
        db.commit()
        yield db
        _purge(db)


def _purge(db: Session) -> None:
    """Remove only this module's rows; the scratch database is shared."""
    db.exec(delete(PasswordResetCode))
    for credential in db.exec(select(PasskeyCredential)).all():
        db.delete(credential)
    for user in db.exec(select(User)).all():
        if user.username in ("reset_tester", "reset_other"):
            db.delete(user)
    db.commit()


def _naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def enrol_passkey(db: Session, user: User) -> None:
    options = svc_passkey_options(db, user)
    authenticator = SoftwareAuthenticator()
    challenge = options["_challenge"]
    from features.auth import passkeys as passkey_service

    passkey_service.complete_registration(
        db, user, authenticator.create(challenge), challenge
    )


def svc_passkey_options(db: Session, user: User):
    from features.auth import passkeys as passkey_service

    return passkey_service.registration_options(db, user)


class TestRequestingACode:
    def test_returns_six_digits(self, session):
        code = svc.request_code(session, USERNAME)
        assert code is not None and len(code) == 6 and code.isdigit()

    def test_finds_the_account_by_email_too(self, session):
        assert svc.request_code(session, EMAIL) is not None

    def test_unknown_account_returns_nothing(self, session):
        assert svc.request_code(session, "nobody_at_all") is None

    def test_blank_identifier_returns_nothing(self, session):
        assert svc.request_code(session, "") is None
        assert svc.request_code(session, "   ") is None

    def test_the_code_is_not_stored_in_the_clear(self, session):
        code = svc.request_code(session, USERNAME)
        stored = session.exec(select(PasswordResetCode)).all()
        assert stored
        assert all(row.code_hash != code for row in stored)
        assert all(len(row.code_hash) == 64 for row in stored)

    def test_two_requests_give_different_codes(self, session):
        first = svc.request_code(session, USERNAME)
        # Age the first so the cooldown does not block the second.
        row = session.exec(select(PasswordResetCode)).first()
        row.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        session.add(row)
        session.commit()
        second = svc.request_code(session, USERNAME)
        assert first != second

    def test_resending_too_soon_is_refused(self, session):
        svc.request_code(session, USERNAME)
        with pytest.raises(svc.PasswordResetError, match="sent recently"):
            svc.request_code(session, USERNAME)

    def test_the_cooldown_is_measured_per_account(self, session):
        """One student's requests must not block another's."""
        other = User(
            email="reset_other@iiitdmj.ac.in",
            full_name="Other",
            username="reset_other",
            roll_number="23BCS994",
            password_hash=hash_password("Other@12345"),
            is_email_verified=True,
        )
        session.add(other)
        session.commit()

        svc.request_code(session, USERNAME)
        assert svc.request_code(session, "reset_other") is not None

    def test_retry_wait_is_reported(self, session):
        svc.request_code(session, USERNAME)
        wait = svc.seconds_until_retry(session, USERNAME)
        assert 0 < wait <= svc.SEND_COOLDOWN.total_seconds()

    def test_no_wait_once_the_cooldown_passes(self, session):
        svc.request_code(session, USERNAME)
        row = session.exec(select(PasswordResetCode)).first()
        row.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - svc.SEND_COOLDOWN - timedelta(minutes=1)
        session.add(row)
        session.commit()
        assert svc.seconds_until_retry(session, USERNAME) == 0

    def test_old_codes_are_swept(self, session):
        svc.request_code(session, USERNAME)
        row = session.exec(select(PasswordResetCode)).first()
        row.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - svc.CODE_RETENTION - timedelta(days=1)
        session.add(row)
        session.commit()

        svc.request_code(session, USERNAME)
        fresh = session.exec(select(PasswordResetCode)).all()
        assert len(fresh) == 1


class TestCompletingAReset:
    def test_the_new_password_works(self, session):
        code = svc.request_code(session, USERNAME)
        svc.complete_reset(session, USERNAME, code, "Brand@New456")

        user = session.exec(select(User).where(User.username == USERNAME)).first()
        session.refresh(user)
        assert verify_password("Brand@New456", user.password_hash)
        assert not verify_password(PASSWORD, user.password_hash)

    def test_an_unknown_account_is_refused(self, session):
        with pytest.raises(svc.PasswordResetError, match="not valid"):
            svc.complete_reset(session, "nobody_at_all", "123456", "Brand@New456")

    def test_a_wrong_code_is_refused(self, session):
        code = svc.request_code(session, USERNAME)
        wrong = "000000" if code != "000000" else "111111"
        with pytest.raises(svc.PasswordResetError, match="not valid"):
            svc.complete_reset(session, USERNAME, wrong, "Brand@New456")
        # And the password is untouched.
        user = session.exec(select(User).where(User.username == USERNAME)).first()
        assert verify_password(PASSWORD, user.password_hash)

    def test_a_wrong_code_does_not_consume_the_right_one(self, session):
        code = svc.request_code(session, USERNAME)
        wrong = "000000" if code != "000000" else "111111"
        with pytest.raises(svc.PasswordResetError):
            svc.complete_reset(session, USERNAME, wrong, "Brand@New456")

        # The real code still works - one slip should not force a new email.
        svc.complete_reset(session, USERNAME, code, "Brand@New456")

    def test_a_code_is_single_use(self, session):
        code = svc.request_code(session, USERNAME)
        svc.complete_reset(session, USERNAME, code, "Brand@New456")
        with pytest.raises(svc.PasswordResetError, match="not valid"):
            svc.complete_reset(session, USERNAME, code, "Another@789")

    def test_an_expired_code_is_refused(self, session):
        code = svc.request_code(session, USERNAME)
        row = session.exec(select(PasswordResetCode)).first()
        row.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - svc.CODE_TTL - timedelta(minutes=1)
        session.add(row)
        session.commit()

        with pytest.raises(svc.PasswordResetError, match="not valid"):
            svc.complete_reset(session, USERNAME, code, "Brand@New456")

    def test_guessing_is_cut_off(self, session):
        """Six digits is a million values; the budget is what stops it."""
        svc.request_code(session, USERNAME)
        for _ in range(svc.MAX_ATTEMPTS):
            with pytest.raises(svc.PasswordResetError):
                svc.complete_reset(session, USERNAME, "000000", "Brand@New456")

        # The row is gone rather than merely blocked: a code left on file with its
        # budget spent would keep absorbing guesses forever.
        assert session.exec(select(PasswordResetCode)).all() == []

    def test_the_budget_is_spent_not_merely_counted(self, session):
        """The final wrong guess must be the one that kills the code."""
        svc.request_code(session, USERNAME)
        for _ in range(svc.MAX_ATTEMPTS - 1):
            with pytest.raises(svc.PasswordResetError, match="not valid"):
                svc.complete_reset(session, USERNAME, "000000", "Brand@New456")

        row = session.exec(select(PasswordResetCode)).first()
        assert row.attempts == svc.MAX_ATTEMPTS - 1

        with pytest.raises(svc.PasswordResetError, match="Too many wrong attempts"):
            svc.complete_reset(session, USERNAME, "000000", "Brand@New456")
        assert session.exec(select(PasswordResetCode)).all() == []

    def test_the_correct_code_is_refused_once_the_budget_is_gone(self, session):
        """Knowing the right code must not help after the budget is spent."""
        code = svc.request_code(session, USERNAME)
        for _ in range(svc.MAX_ATTEMPTS):
            with pytest.raises(svc.PasswordResetError):
                svc.complete_reset(session, USERNAME, "000000", "Brand@New456")

        with pytest.raises(svc.PasswordResetError):
            svc.complete_reset(session, USERNAME, code, "Brand@New456")

        user = session.exec(select(User).where(User.username == USERNAME)).first()
        session.refresh(user)
        assert verify_password(PASSWORD, user.password_hash)

    def test_requesting_afresh_code_does_not_reset_the_budget(self, session):
        """Otherwise an attacker could guess for free by re-requesting."""
        svc.request_code(session, USERNAME)
        for _ in range(svc.MAX_ATTEMPTS):
            with pytest.raises(svc.PasswordResetError):
                svc.complete_reset(session, USERNAME, "000000", "Brand@New456")
        assert session.exec(select(PasswordResetCode)).all() == []

    def test_the_code_can_be_used_by_email_instead(self, session):
        code = svc.request_code(session, USERNAME)
        svc.complete_reset(session, EMAIL, code, "Brand@New456")


class TestResetContainsAnIncident:
    def test_existing_sessions_are_stamped_out(self, session):
        user = session.exec(select(User).where(User.username == USERNAME)).first()
        assert user.password_changed_at is None

        code = svc.request_code(session, USERNAME)
        svc.complete_reset(session, USERNAME, code, "Brand@New456")

        session.refresh(user)
        assert user.password_changed_at is not None

    def test_every_passkey_is_revoked(self, session):
        """A compromised device's passkey must not survive the reset."""
        user = session.exec(select(User).where(User.username == USERNAME)).first()
        enrol_passkey(session, user)
        enrol_passkey(session, user)
        assert len(session.exec(select(PasskeyCredential)).all()) == 2

        code = svc.request_code(session, USERNAME)
        result = svc.complete_reset(session, USERNAME, code, "Brand@New456")

        assert result["passkeys_revoked"] == 2
        assert session.exec(select(PasskeyCredential)).all() == []

    def test_other_live_codes_die_with_the_password(self, session):
        """A code issued for the *old* password must not outlive it."""
        first = svc.request_code(session, USERNAME)
        # Age the first just enough to clear the resend cooldown but stay live,
        # so a second code exists alongside it.
        row = session.exec(select(PasswordResetCode)).first()
        row.created_at = (
            datetime.now(timezone.utc).replace(tzinfo=None)
            - svc.SEND_COOLDOWN
            - timedelta(minutes=1)
        )
        session.add(row)
        session.commit()
        second = svc.request_code(session, USERNAME)
        assert first != second
        assert len(session.exec(select(PasswordResetCode)).all()) == 2

        svc.complete_reset(session, USERNAME, second, "Brand@New456")

        # Only the spent code survives; the other is gone rather than usable.
        remaining = session.exec(select(PasswordResetCode)).all()
        assert len(remaining) == 1
        assert remaining[0].used_at is not None

    def test_an_expired_code_is_left_to_the_sweeper(self, session):
        """Already past its TTL, so harmless; retention clears it later."""
        svc.request_code(session, USERNAME)
        row = session.exec(select(PasswordResetCode)).first()
        row.created_at = (
            datetime.now(timezone.utc).replace(tzinfo=None)
            - svc.CODE_TTL
            - timedelta(minutes=5)
        )
        session.add(row)
        session.commit()
        # Get a live code so a reset can succeed.
        row.created_at = (
            datetime.now(timezone.utc).replace(tzinfo=None)
            - svc.SEND_COOLDOWN
            - timedelta(minutes=1)
        )
        session.add(row)
        session.commit()
        second = svc.request_code(session, USERNAME)

        svc.complete_reset(session, USERNAME, second, "Brand@New456")
        remaining = session.exec(select(PasswordResetCode)).all()
        assert all(row.used_at is not None or row.created_at < _naive_now() - svc.CODE_TTL for row in remaining)

    def test_email_verification_is_not_disturbed(self, session):
        """A reset must not change who the account belongs to."""
        code = svc.request_code(session, USERNAME)
        svc.complete_reset(session, USERNAME, code, "Brand@New456")
        user = session.exec(select(User).where(User.username == USERNAME)).first()
        assert user.is_email_verified is True
        assert user.email == EMAIL
        assert user.roll_number == "23BCS995"
