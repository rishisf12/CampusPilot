"""
Shared pytest configuration.

PostgreSQL is the only supported database (SQLite support was removed
in 434c6e3). A test run needs a real PostgreSQL to talk to.

The app reads its database URL from the environment at import time, so
TEST_DATABASE_URL must be set before any test module imports
``database``/``config``:

    createdb -U campuspilot campuspilot_test
    set TEST_DATABASE_URL=postgresql+psycopg://campuspilot:campuspilot@localhost:5432/campuspilot_test
    python -m pytest

The database is destroyed and rebuilt from the Alembic history on every
run, so it must never be a database you care about.
"""
import contextlib
import os
from urllib.parse import urlparse

import pytest

# --------------------------------------------------------------------------
# Choose the database BEFORE anything imports core.config.
# Importing those modules builds the engine, and a wrong URL there
# costs minutes of retrying instead of a one-line error here.
# --------------------------------------------------------------------------
TEST_POSTGRES_URL = os.environ.get("TEST_DATABASE_URL", "").strip()


def _require_test_database(url: str) -> None:
    """Refuse to run unless we were handed a dedicated test database.

    Two failures are caught here, and both have already happened:

    * No ``TEST_DATABASE_URL`` at all. The old default was a scratch
      SQLite file; without it the run would silently fall through to
      the development database.
    * A ``TEST_DATABASE_URL`` pointing at the development database,
      which is exactly how the dev data got wiped once.
    """
    if not url:
        pytest.exit(
            "TEST_DATABASE_URL is required - PostgreSQL is the only "
            "supported database (SQLite support was removed in 434c6e3).\n"
            "    set TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/campuspilot_test",
            returncode=1,
        )

    db_name = urlparse(url).path.lstrip("/")
    if "test" not in db_name.lower():
        pytest.exit(
            f"Refusing to run tests against '{db_name}': the _schema fixture "
            "runs 'alembic downgrade base', which drops every table. "
            "Point TEST_DATABASE_URL at a dedicated *_test database instead.",
            returncode=1,
        )


_require_test_database(TEST_POSTGRES_URL)

# The app reads DATABASE_URL at import time, so it has to be set
# before core.config is imported by any test module.
os.environ["DATABASE_URL"] = TEST_POSTGRES_URL

# Keep email sending out of the tests; no test should touch SMTP.
os.environ.setdefault("SMTP_USER", "")
os.environ.setdefault("SMTP_PASSWORD", "")

# Markers. Registered here so `--strict-markers` can stay on.
os.environ.setdefault("PYTEST_ADDOPTS", "")


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "postgres: kept for compatibility; everything is PostgreSQL now"
    )


_RATE_LIMITER_NAMES = (
    "COLLECT_BATCH_LIMIT",
    "CRASH_LIMIT",
    "AUTH_LIMIT",
    "BRUTE_FORCE_LIMIT",
    "OTP_RESEND_LIMIT",
)


def _reset_rate_limiters() -> None:
    from features.monitoring.infrastructure.ratelimit import (
        AUTH_LIMIT,
        BRUTE_FORCE_LIMIT,
        COLLECT_BATCH_LIMIT,
        CRASH_LIMIT,
        OTP_RESEND_LIMIT,
    )

    for limiter in (
        COLLECT_BATCH_LIMIT,
        CRASH_LIMIT,
        AUTH_LIMIT,
        BRUTE_FORCE_LIMIT,
        OTP_RESEND_LIMIT,
    ):
        limiter.reset()


@pytest.fixture(scope="session")
def using_postgres() -> bool:
    """Always True - PostgreSQL is the only dialect. Kept for compatibility."""
    return True


@pytest.fixture
def require_postgres(using_postgres):
    """Never skips - everything runs on PostgreSQL. Kept for compatibility."""
    return None


@pytest.fixture(scope="session", autouse=True)
def _schema():
    """Rebuild the schema from the app's Alembic history, once per session.

    Production runs Alembic, so a test suite that built its schema any
    other way would happily pass against a schema that could never be
    migrated to. The downgrade first is what makes an interrupted
    previous run safe to re-run.
    """
    from alembic import command

    from core.database import alembic_config

    cfg = alembic_config()
    # Base first: a previous interrupted run may have left tables behind.
    with contextlib.suppress(Exception):
        command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limiters_fixture():
    """Reset in-memory rate limiters before and after each test."""
    _reset_rate_limiters()
    yield
    _reset_rate_limiters()