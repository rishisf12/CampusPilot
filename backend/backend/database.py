"""Database engine, session factory, and table creation."""
import logging
from contextlib import contextmanager
from sqlmodel import SQLModel, Session, create_engine
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = create_engine(settings.database_url, echo=False)


def create_db_and_tables() -> None:
    """Create all tables defined in SQLModel metadata."""
    logger.info("Creating database tables...")
    SQLModel.metadata.create_all(engine)
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