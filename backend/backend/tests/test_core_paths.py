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


def test_database_lives_in_repo_database_dir():
    """Pin the *default* URL construction (the test env overrides it)."""
    import os

    from core.config import Settings

    override = os.environ.pop("DATABASE_URL", None)
    try:
        url = Settings().database_url
    finally:
        if override is not None:
            os.environ["DATABASE_URL"] = override
    assert url == f"sqlite:///{repo_root() / 'database' / 'classpilot.db'}"


def test_env_file_is_repo_root_dotenv():
    env_file = Path(__file__).resolve().parents[3] / ".env"
    assert env_file == repo_root() / ".env"


def test_feed_media_defaults_under_backend_uploads():
    media = Path(settings.feed_media_dir)
    assert media.parent.name == "uploads"
    assert media.parent.parent.name == "backend"
