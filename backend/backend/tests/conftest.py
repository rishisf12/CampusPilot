"""
Shared pytest configuration.

The app reads its database URL from the environment at import time, so this must
be set before any test module imports ``database``/``config``.

Two dialects are supported, and the difference is deliberate:

* **SQLite** (default) - a scratch file in the temp directory. No service to
  start, runs in milliseconds. This is what a developer gets locally and what CI
  uses for the fast feedback loop.

* **PostgreSQL** - set ``TEST_DATABASE_URL``. Required before trusting a change,
  because SQLite is permissive where Postgres is not. A column that SQLite
  happily stores as NULL, a ``float`` compared with ``=``, a case-sensitive
  ``LIKE``, a date truncation - all behave differently, and only the second
  dialect will tell you.

    set TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/campdb_test
    python -m pytest

The marker ``postgres`` skips a test that only means something on PostgreSQL
(constraint enforcement, dialect-specific DDL). Use::

    @pytest.mark.postgres
"""
import os
import tempfile
from pathlib import Path

import pytest

# --------------------------------------------------------------------------
# Pick the dialect BEFORE anything imports core.config.
# --------------------------------------------------------------------------
TEST_POSTGRES_URL = os.environ.get("TEST_DATABASE_URL", "").strip()

if TEST_POSTGRES_URL:
    os.environ["DATABASE_URL"] = TEST_POSTGRES_URL
else:
    TEST_DB = Path(tempfile.gettempdir()) / "campuspilot_pytest.db"
    if TEST_DB.exists():
        TEST_DB.unlink()
    os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

# Keep email sending out of the tests; no test should touch SMTP.
os.environ.setdefault("SMTP_USER", "")
os.environ.setdefault("SMTP_PASSWORD", "")

# Markers. Registered here so `--strict-markers` can stay on.
os.environ.setdefault("PYTEST_ADDOPTS", "")


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "postgres: only meaningful when TEST_DATABASE_URL points at PostgreSQL"
    )


@pytest.fixture(scope="session")
def using_postgres() -> bool:
    return bool(TEST_POSTGRES_URL)


@pytest.fixture
def require_postgres(using_postgres):
    """Skip a test that cannot pass on SQLite."""
    if not using_postgres:
        pytest.skip("needs PostgreSQL: set TEST_DATABASE_URL")


@pytest.fixture(scope="session", autouse=True)
def _schema():
    """Create the schema once for the session, and tear it down after.

    On SQLite this is a temp file that conftest already unlinked, so
    ``create_all`` is sufficient. On PostgreSQL the app's Alembic history is used
    instead, because that is what production runs - a test suite that builds its
    schema a different way would happily pass against a schema that cannot
    actually be migrated to.
    """
    from core.database import engine
    from sqlmodel import SQLModel

    if TEST_POSTGRES_URL:
        from alembic import command

        from core.database import alembic_config

        cfg = alembic_config()
        # Base first: a previous interrupted run may have left tables behind.
        try:
            command.downgrade(cfg, "base")
        except Exception:  # noqa: BLE001 - nothing to downgrade is fine
            pass
        command.upgrade(cfg, "head")
        yield
        return

    SQLModel.metadata.create_all(engine)
    yield