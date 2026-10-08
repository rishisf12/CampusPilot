"""Database engine, session factory, and schema creation.

PostgreSQL is the only supported database. Three things in here are specific to
Postgres and are the whole reason this file exists rather than a one-line URL
swap:

1. **Engine options are PostgreSQL-specific.** ``pool_size``, ``pool_pre_ping``,
   ``pool_recycle``, and connect timeout are first-class Postgres features.
   They are hard errors on SQLite's single-file driver.

2. **Schema migration is owned by Alembic.** The old schema migration could not
   work on Postgres. ``_migrate_columns`` issued ``ALTER TABLE ... ADD COLUMN``
   with the type rendered by ``column.type.compile(dialect)``. That is fine on
   SQLite, but on Postgres a server-side default has to be spelled ``now()`` not
   ``CURRENT_TIMESTAMP``, a JSON column wants ``JSONB``, and an enum column is a
   *type*, not a column - so the naive version would half-apply and then fail.
   Alembic now owns the schema.

3. **Postgres connections go stale.** Idle connections are dropped by the
   server or by any NAT between here and there, and the symptom is an
   OperationalError surfacing on an unrelated request. ``pool_pre_ping`` turns
   that into a transparent reconnect.
"""
import logging
from contextlib import contextmanager

from sqlmodel import Session, SQLModel, create_engine

from core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def engine_kwargs() -> dict:
    """Options for the PostgreSQL dialect.

    Kept in one place, and public, so that anything rebuilding an engine against
    the same URL gets the right options without re-deriving them. The test suite
    clones the engine to obtain an isolated session.
    """
    return {
        # Ping before handing out a pooled connection; transparently replaces one
        # the server or a firewall has closed while it sat idle.
        "pool_pre_ping": True,
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_timeout": settings.db_pool_timeout,
        # Recycle before anything else would, rather than discovering the drop as
        # a failed request at 3am.
        "pool_recycle": settings.db_pool_recycle,
        "connect_args": {
            "connect_timeout": settings.db_connect_timeout,
            "application_name": "campuspilot-api",
            # Applied only when it can help. "prefer" upgrades to TLS when the
            # server offers it; compose talks plaintext on the bridge network.
            **({"sslmode": settings.db_sslmode} if settings.db_sslmode != "disable" else {}),
        },
    }


#: Back-compat alias for the private name this function used to have.
_engine_kwargs = engine_kwargs


engine = create_engine(
    settings.database_url,
    echo=False,
    future=True,
    **engine_kwargs(),
)


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
    """Bring the database up to the Alembic head.

    Called from the application lifespan. Safe to run on every boot: Alembic is
    a no-op when the ``alembic_version`` table already says "head".

    On a brand-new database this creates everything from the migration history.
    That is deliberate - ``create_all`` would build the *current* models and
    leave no revision stamp, which silently diverges from the migration files the
    moment the first real migration is written.
    """
    from alembic import command

    logger.info("PostgreSQL detected: running migrations to head")
    cfg = alembic_config()
    command.upgrade(cfg, "head")
    logger.info("Schema is at head")


def create_db_and_tables() -> None:
    """Back-compat alias. Kept because ``main.py`` and several tools import it."""
    upgrade_schema()


# --------------------------------------------------------------------------
# Sessions
# --------------------------------------------------------------------------

def get_session() -> Session:
    """FastAPI dependency: yields a session and ensures close."""
    with Session(engine) as session:
        yield session


from contextlib import contextmanager


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