"""Core path regression tests.

`core/config.py` sits one level deeper than the old flat `config.py`, so every
`parents[n]` computation shifted. A wrong index does not fail at import - it
fails at startup with "unable to open database file", or silently writes
uploads to a stray folder. Pin the resolved locations here.
"""
from pathlib import Path

from core.config import settings


def repo_root() -> Path:
    # core/config.py -> core -> backend/backend -> backend -> CampusPilot
    return Path(__file__).resolve().parents[3]


def test_database_default_is_postgres():
    """Pin the *default* URL (the test env overrides it).

    Changed deliberately: SQLite serialises all writers for the whole database,
    so a student submitting feedback while the IMAP poller ingests a message can
    hit "database is locked". PostgreSQL also gives the monitoring stack real
    introspection - pg_stat_statements, per-table statistics, EXPLAIN ANALYZE.
    """
    import os

    from core.config import Settings

    override = os.environ.pop("DATABASE_URL", None)
    try:
        fresh = Settings()
    finally:
        if override is not None:
            os.environ["DATABASE_URL"] = override

    url = fresh.database_url
    assert url.startswith("postgresql+psycopg://"), (
        f"default database_url must be PostgreSQL, got {url!r}"
    )
    # The driver name must be psycopg 3, not a bare "postgresql://" which would
    # resolve to psycopg2 - a package that is not installed.
    assert "+psycopg" in url


def test_env_file_is_repo_root_dotenv():
    env_file = Path(__file__).resolve().parents[3] / ".env"
    assert env_file == repo_root() / ".env"


def test_feed_media_defaults_under_backend_uploads():
    media = Path(settings.feed_media_dir)
    assert media.parent.name == "uploads"
    assert media.parent.parent.name == "backend"