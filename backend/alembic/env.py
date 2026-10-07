"""Alembic environment, wired to SQLModel rather than to raw SQLAlchemy.

Three things make this non-standard:

1. **sys.path is fixed here, not left to the ini.** Alembic's ``prepend_sys_path``
   option exists for this, but it resolves relative to the *current* directory,
   and this command gets invoked from ``backend/``, from ``backend/backend/``,
   and from the Dockerfile where ``WORKDIR`` is ``/app``. Doing it in Python means
   it works from all of them.

2. **Metadata comes from SQLModel, not Base.metadata.** The app declares tables
   with ``SQLModel, table=True``, so importing every model module is what
   populates ``SQLModel.metadata``. Miss one module and Alembic will happily
   generate a migration that DROPS its table. The import below is therefore
   load-bearing, not decorative.

3. **The engine is the app's own engine.** ``env.py`` normally calls
   ``engine_from_config``. Rebuilding would ignore ``DATABASE_URL`` and every
   pool setting in ``core/config.py``, so migrations would run against a
   different database than the app - the kind of mistake that only shows up in
   production.
"""
from logging.config import fileConfig

import sys
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# --- make the app importable from any working directory -------------------
# This file lives at backend/alembic/env.py, so:
#   parents[0] = backend/alembic
#   parents[1] = backend            <- the repo's backend/ directory
# The importable package dir is backend/backend, a *sibling* of backend/alembic,
# not a parent - so it has to be joined on rather than indexed into parents.
_APP_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

# Import the app's models BEFORE metadata is resolved, so SQLModel.metadata is
# fully populated. models.py imports nothing from features/, so there is no
# circular-import risk from doing this at module scope.
from sqlmodel import SQLModel  # noqa: E402

import models  # noqa: E402,F401  - imported for the side effect of registering tables

from core.config import settings  # noqa: E402

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def _url() -> str:
    """The database Alembic should target.

    Falls back to ``DATABASE_URL`` when alembic.ini leaves ``sqlalchemy.url``
    blank - which is how it ships, because the URL carries a password and does
    not belong in a committed file.
    """
    return config.get_main_option("sqlalchemy.url") or settings.database_url


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it. For review, not for deploys."""
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        # SQLite has no ALTER COLUMN, so Alembic has to copy the table to change
        # it. Harmless on Postgres, so set always rather than branching.
        render_as_batch=settings.is_sqlite,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection.

    Uses the app's own engine so ``pool_pre_ping``, ``pool_recycle`` and the
    connect timeout all apply - a migration that cannot reach the database
    should fail after DB_CONNECT_TIMEOUT, not hang a deploy.
    """
    if config.get_main_option("sqlalchemy.url"):
        # An explicit URL in the ini wins; only then build our own engine.
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
    else:
        from core.database import engine as app_engine

        connectable = app_engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=settings.is_sqlite,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()