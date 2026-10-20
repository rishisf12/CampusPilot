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
            "wipes and rebuilds the schema, which drops every table. "
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
    migrated to. The wipe first is what makes an interrupted previous
    run safe to re-run.

    Why a wipe instead of ``alembic downgrade base``. The downgrade chain
    through the older migrations is not actually reversible - enum types
    shared with create_all's schema-tagged mirror tables, FK ordering in
    the phase3 baseline, and the unqualified monitoring tables all fail
    partway down. Because the failure used to be swallowed here, each run
    silently inherited the previous run's rows and the suite sprayed
    duplicate-user IntegrityErrors that looked like test bugs. Dropping
    the schemas is the same ``destroyed and rebuilt`` contract, reliably.
    """
    from alembic import command
    from sqlalchemy import text

    from core.database import alembic_config, engine

    cfg = alembic_config()
    with engine.begin() as conn:
        # The version marker is unqualified, so it may sit in any schema
        # the search path offers; find rather than assume.
        for (schema,) in conn.execute(
            text("SELECT table_schema FROM information_schema.tables WHERE table_name = 'alembic_version'")
        ).all():
            conn.execute(text(f'DROP TABLE IF EXISTS "{schema}".alembic_version'))
        # Unqualified baseline tables land in `core` (the search path's
        # first hit); create_all's schema-tagged mirrors land in the rest.
        # Dropping the schemas first takes every mirrored enum dependency
        # with them.
        for schema in ("core", "academic", "social", "telemetry"):
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        # Native enum types from create_all land in the connection's default
        # schema (`public`), so clear those or the next upgrade's unqualified
        # CREATE TYPE picks the wrong namespace. Mirror-table dependents are
        # already gone above; CASCADE covers any stray column that is not.
        for (type_name,) in conn.execute(
            text(
                "SELECT t.typname FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace "
                "WHERE n.nspname = 'public' AND t.typtype = 'e'"
            )
        ).all():
            conn.execute(text(f'DROP TYPE IF EXISTS public."{type_name}" CASCADE'))
    command.upgrade(cfg, "heads")
    # Migrations share the app engine; dispose of pooled connections so no
    # session-scoped state a migration left behind (search_path, timezone...)
    # leaks into the fixture's sessions. A fresh pool costs milliseconds here
    # and buys a clean slate for the whole suite.
    engine.dispose()
    # Catch-up for tables that exist via create_all in prod but never via
    # Alembic (social.feedback, academic.timetable_slot, ...). Prod gets
    # them from create_all on fresh installs; tests get them here so the
    # suite runs against the same shape prod serves. Long-term fix is a
    # squashed baseline migration; until then this keeps the two in sync.
    import models  # noqa: F401
    import features.monitoring.domain.models  # noqa: F401
    from sqlmodel import SQLModel
    from core.database import engine as _engine
    SQLModel.metadata.create_all(_engine, checkfirst=True)
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limiters_fixture():
    """Reset in-memory rate limiters before and after each test."""
    _reset_rate_limiters()
    yield
    _reset_rate_limiters()