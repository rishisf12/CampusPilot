"""Database engine, session factory, and table creation."""
import logging
from contextlib import contextmanager
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import inspect, text
from core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = create_engine(settings.database_url, echo=False)


def _migrate_columns() -> None:
    """
    Add columns that exist on the models but are missing from an older SQLite file.

    SQLModel's ``create_all`` only creates missing *tables*, never missing columns,
    so pre-existing databases need an explicit ``ALTER TABLE`` pass.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table in SQLModel.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # freshly created by create_all, already has every column

        existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing_columns:
                continue
            ddl = column.type.compile(engine.dialect)
            logger.info("Migrating: ADD COLUMN %s.%s %s" % (table.name, column.name, ddl))
            with engine.begin() as conn:
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN "{column.name}" {ddl}'))


def _rename_legacy_columns() -> None:
    """Rename pre-migration ``exam_seating.exam_date`` to ``seating_date``."""
    inspector = inspect(engine)
    if "exam_seating" not in set(inspector.get_table_names()):
        return
    columns = {col["name"] for col in inspector.get_columns("exam_seating")}
    if "exam_date" in columns and "seating_date" not in columns:
        logger.info("Migrating: RENAME exam_seating.exam_date -> seating_date")
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE exam_seating RENAME COLUMN exam_date TO seating_date"))


def create_db_and_tables() -> None:
    """Create all tables defined in SQLModel metadata and migrate older schemas."""
    logger.info("Creating database tables...")
    SQLModel.metadata.create_all(engine)
    _rename_legacy_columns()
    _migrate_columns()
    logger.info("Tables created.")


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