"""Database engine, session factory, and schema creation.

Supports both PostgreSQL (production) and SQLite (local development).
"""
import logging
from contextlib import contextmanager
from urllib.parse import urlparse

from sqlmodel import Session, create_engine
from sqlalchemy import text, event
from sqlalchemy.pool import StaticPool

from core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def is_sqlite(url: str) -> bool:
    """Check if the database URL is for SQLite."""
    parsed = urlparse(url)
    return parsed.scheme in ("sqlite", "sqlite+pysqlite")


def engine_kwargs() -> dict:
    """Options for the database dialect - works for both SQLite and PostgreSQL."""
    url = settings.database_url
    
    if is_sqlite(url):
        # SQLite-specific configuration
        return {
            "poolclass": StaticPool,
            "connect_args": {
                "check_same_thread": False,
                "timeout": 30,
            },
        }
    else:
        # PostgreSQL-specific configuration
        return {
            "pool_pre_ping": True,
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_timeout": settings.db_pool_timeout,
            "pool_recycle": settings.db_pool_recycle,
            "connect_args": {
                "connect_timeout": settings.db_connect_timeout,
                "application_name": "campuspilot-api",
                **({"sslmode": settings.db_sslmode} if settings.db_sslmode != "disable" else {}),
            },
        }


def create_engine_with_retry(url: str, max_retries: int = 30, base_delay: float = 1.0):
    """Create an engine, retrying transient connection failures."""
    import time

    for attempt in range(1, max_retries + 1):
        try:
            engine = create_engine(
                url,
                echo=False,
                future=True,
                **engine_kwargs(),
            )
            # Force the connection now
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:
            if attempt == max_retries:
                logger.exception("Failed to connect to database after %d attempts", max_retries)
                raise
            delay = min(base_delay * (2 ** (attempt - 1)), 30.0)
            logger.warning(
                "Database connection attempt %d/%d failed: %s. Retrying in %.1fs...",
                attempt,
                max_retries,
                exc,
                delay,
            )
            time.sleep(delay)
            continue

        logger.info("Database connection established on attempt %d", attempt)
        return engine

    raise RuntimeError("Failed to create database engine after max retries")


engine = create_engine_with_retry(settings.database_url)


# Enable foreign keys for SQLite
if is_sqlite(settings.database_url):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# --------------------------------------------------------------------------
# Alembic
# --------------------------------------------------------------------------

def alembic_config():
    """Build an Alembic config bound to *this* engine.

    Import is local so that a process which never migrates (every request
    handler) does not pay Alembic's import cost, and so the test suite - which
    creates its schema with ``create_all`` - never has Alembic touch it.

    **Why the script location is searched for rather than computed.** The two
    places this code runs lay the tree out differently:

    * A repository checkout has ``backend/alembic.ini`` and ``backend/alembic``
      as siblings of the ``backend/backend`` package directory, so they are two
      levels above this file.
    * The container image installs the package at ``/app/backend`` and the
      migrations at ``/app/backend/alembic``, because ``PYTHONPATH`` must
      contain the package directory for the application's flat imports
      (``from core.database import ...``) to resolve at all.

    Computing a single depth picks the right one and silently picks the wrong
    one in the other environment - and the failure, ``Path doesn't exist:
    '/app/alembic'``, looks like a missing migrations directory rather than a
    path bug. Checking both costs two `exists()` calls at startup.
    """
    from alembic.config import Config
    from pathlib import Path

    here = Path(__file__).resolve()
    candidates = [
        here.parents[2],   # repository checkout: backend/
        here.parents[1],   # container image: /app/backend/
    ]

    script_dir = None
    ini_path = None
    for base in candidates:
        if script_dir is None and (base / "alembic").is_dir():
            script_dir = base / "alembic"
            if (base / "alembic.ini").is_file():
                ini_path = base / "alembic.ini"

    if script_dir is None:
        raise RuntimeError(
            "Could not locate the Alembic migrations. Looked in: "
            + ", ".join(str(b / "alembic") for b in candidates)
        )

    cfg = Config(str(ini_path)) if ini_path else Config()
    cfg.set_main_option("script_location", str(script_dir))
    cfg.attributes["configure_logger"] = False
    return cfg


def upgrade_schema() -> None:
    """Bring the database up to the Alembic head (PostgreSQL only)."""
    if is_sqlite(settings.database_url):
        logger.info("SQLite detected: skipping Alembic migrations (using existing schema)")
        return
    
    import time
    from alembic import command

    max_retries = 10
    base_delay = 1.0
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("PostgreSQL detected: running migrations to head (attempt %d/%d)", attempt, max_retries)
            cfg = alembic_config()
            command.upgrade(cfg, "head")
            logger.info("Schema is at head")
            return
        except Exception as e:
            if attempt == max_retries:
                logger.exception("Failed to run migrations after %d attempts", max_retries)
                raise
            delay = base_delay * (2 ** (attempt - 1))  # exponential backoff
            logger.warning("Migration attempt %d/%d failed: %s. Retrying in %.1fs...", attempt, max_retries, e, delay)
            time.sleep(delay)


def create_db_and_tables() -> None:
    """Back-compat alias. Creates tables for SQLite, runs migrations for PostgreSQL."""
    if is_sqlite(settings.database_url):
        logger.info("SQLite detected: creating tables from models")
        from sqlmodel import SQLModel
        SQLModel.metadata.create_all(engine)
    else:
        upgrade_schema()


# --------------------------------------------------------------------------
# Sessions
# --------------------------------------------------------------------------

def get_session() -> Session:
    """FastAPI dependency: yields a session and ensures close."""
    with Session(engine) as session:
        yield session


@contextmanager
def session_scope():
    """Context manager for scripts / non-FastAPI code."""
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()