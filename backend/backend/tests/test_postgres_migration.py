"""
Tests for the PostgreSQL migration itself.

Not application tests - these assert the *properties* the new database setup has
to have, so that a future change which quietly breaks them is caught rather than
discovered in production.

The two tests that matter most came out of real failures during the migration:

1. ``test_alembic_round_trip`` - autogenerate's downgrade dropped the tables but
   left the ``attendancestatus`` enum type behind, so the next upgrade died with
   DuplicateObject. That made the migration unusable in both directions.

2. ``test_not_null_is_enforced`` - the old SQLite schema-repair pass emitted
   ``ADD COLUMN "role" VARCHAR``, dropping NOT NULL, so rows predating the column
   carry NULL. SQLite accepted it forever. Postgres does not.
"""
import sqlite3
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlmodel import Session, select

from models import AttendanceStatus, AttendanceRecord, Course, User


# ---------------------------------------------------------------------------
# Dialect guards
# ---------------------------------------------------------------------------

def test_sqlmodel_enum_labels_match_postgres_type(using_postgres):
    """The stored value must be a label the Postgres enum type actually accepts.

    SQLAlchemy persists the enum member *name* ("PRESENT"), not its *value*
    ("Present"). If that ever changed, every attendance insert would fail on
    Postgres with a label-missing error while continuing to work on SQLite -
    exactly the kind of divergence these tests exist to catch.
    """
    if not using_postgres:
        pytest.skip("needs PostgreSQL")

    from core.database import engine

    with engine.connect() as conn:
        labels = conn.execute(
            sa.text(
                "SELECT string_agg(e.enumlabel, ',' ORDER BY e.enumsortorder) "
                "FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid "
                "WHERE t.typname = 'attendancestatus' GROUP BY t.typname"
            )
        ).scalar()
    stored = {m.name for m in AttendanceStatus}
    assert set(labels.split(",")) == stored


def test_attendance_round_trip(require_postgres):
    """Write one of each status and read them back through the ORM."""
    from core.database import engine

    with Session(engine) as s:
        course = Course(code="PGENUM", name="Enum probe", semester=1, branch="CSE A")
        s.add(course)
        s.commit()
        s.refresh(course)
        for status in AttendanceStatus:
            s.add(
                AttendanceRecord(
                    course_id=course.id, date="2026-01-05", status=status
                )
            )
        s.commit()

        found = s.exec(select(AttendanceRecord).where(
            AttendanceRecord.course_id == course.id
        )).all()
        assert {r.status for r in found} == set(AttendanceStatus)

        # Delete children before the parent. SQLAlchemy's default cascade would
        # otherwise try to NULL the child's `course_id` first - which SQLite
        # accepts silently (FK enforcement is off by default) and PostgreSQL
        # rejects with a NotNullViolation. Worth the explicit order: it is the
        # same trap any future cleanup code has to avoid.
        for record in found:
            s.delete(record)
        s.delete(course)
        s.commit()


# ---------------------------------------------------------------------------
# Constraint enforcement - the SQLite/Postgres divergence
# ---------------------------------------------------------------------------

def test_not_null_is_enforced(require_postgres):
    """A NOT NULL column must reject NULL on Postgres.

    The SQLite database in the repo carries a user row with ``role = NULL``,
    written before the column existed and repaired by the data migration. On
    Postgres the insert must be refused, or the constraint is not doing its job.
    """
    from core.database import engine

    with engine.begin() as conn:
        with pytest.raises(sa.exc.IntegrityError):
            conn.execute(
                sa.text(
                    'INSERT INTO "user" (email, password_hash, username, role) '
                    "VALUES ('nn@x.io', 'x', 'nn_probe', NULL)"
                )
            )


def test_unique_constraints_are_enforced(require_postgres):
    """Unique indexes exist on user.email and user.username.

    Worth asserting explicitly: on SQLite a UNIQUE index built on an existing
    table can fail to be created without an error, leaving duplicates possible.
    """
    from core.database import engine

    with Session(engine) as s:
        existing = s.exec(select(User)).first()
        assert existing is not None, "data migration should have populated users"
        with pytest.raises(sa.exc.IntegrityError):
            s.add(
                User(
                    email=existing.email,
                    password_hash="x",
                    username="dup_probe",
                    role="student",
                )
            )
            s.commit()
        s.rollback()


def test_json_columns_round_trip(require_postgres):
    """JSON stored on SQLite as TEXT must land as real JSON in Postgres.

    A naive copy passes the string through, and Postgres stores a doubly-encoded
    JSON document that looks fine in psql but is a *string* to the application.
    """
    from core.database import engine
    from models import UserProfile

    with Session(engine) as s:
        user = s.exec(select(User)).first()
        s.add(
            UserProfile(
                user_id=user.id,
                skills=["react", "python"],
                elective_codes=["CS301", "CS302"],
            )
        )
        s.commit()

        p = s.exec(select(UserProfile).where(UserProfile.user_id == user.id)).first()
        assert isinstance(p.skills, list), f"skills decoded as {type(p.skills)}"
        assert p.skills == ["react", "python"]
        assert p.elective_codes == ["CS301", "CS302"]

        s.delete(p)
        s.commit()


def test_case_sensitive_like_on_postgres(require_postgres):
    """Postgres LIKE is case-sensitive; SQLite's is not for ASCII.

    Any search feature written against SQLite and moved here will silently change
    behaviour. This test documents the difference so nobody "fixes" it later by
    loosening a query.
    """
    from core.database import engine

    with engine.connect() as conn:
        hit = conn.execute(
            sa.text("SELECT 'CampusNav' LIKE 'campusnav'")
        ).scalar()
    assert hit is False


# ---------------------------------------------------------------------------
# Alembic
# ---------------------------------------------------------------------------

def test_alembic_round_trip(require_postgres):
    """downgrade base -> upgrade head must work, repeatedly.

    Autogenerate's downgrade drops the tables but not the enum type, so the
    second upgrade fails with DuplicateObject. Verified over several cycles
    because a single cycle can pass by accident if a stale type happens to be
    reused.
    """
    from alembic import command

    from core.database import alembic_config, engine

    cfg = alembic_config()
    for _ in range(2):
        command.downgrade(cfg, "base")
        with engine.connect() as conn:
            leftover = conn.execute(
                sa.text(
                    "SELECT count(*) FROM pg_type WHERE typname = 'attendancestatus'"
                )
            ).scalar()
            assert leftover == 0, "enum type survived downgrade base"
        command.upgrade(cfg, "head")


def test_alembic_metadata_matches_models(require_postgres):
    """No pending autogenerate diff.

    If this fails, someone edited models.py without writing a migration, and
    production and the model definitions have drifted.
    """
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from core.database import engine
    import models  # noqa: F401  - registers tables on SQLModel.metadata
    from sqlmodel import SQLModel

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        diff = compare_metadata(ctx, SQLModel.metadata)
    # Filter out the alembic_version bookkeeping table.
    real = [d for d in diff if not any("alembic_version" in str(t) for t in getattr(d, "compare", ()))]
    assert not real, f"models and migrations have drifted: {real}"


# ---------------------------------------------------------------------------
# The data migration script
# ---------------------------------------------------------------------------

def test_data_migration_detects_null_in_not_null_column(tmp_path):
    """The repair path must trigger on a legacy file, and be reported.

    Reproduces the historical ``user.role IS NULL`` situation in a scratch SQLite
    file so the fix is covered by a test rather than by having noticed it once.
    ``role`` is created separately, without NOT NULL, exactly as the old
    schema-repair pass produced.
    """
    import sys as _sys

    db = tmp_path / "legacy.db"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE user (id INTEGER PRIMARY KEY, email TEXT NOT NULL, "
        "password_hash TEXT NOT NULL, username TEXT NOT NULL UNIQUE)"
    )
    con.execute(
        "INSERT INTO user (id, email, password_hash, username) "
        "VALUES (1, 'legacy@x.io', 'h', 'legacy')"
    )
    con.commit()
    con.close()

    # The damage: column added after the row existed, constraint not carried over.
    con = sqlite3.connect(db)
    con.execute("ALTER TABLE user ADD COLUMN role VARCHAR")
    cols = {r[1]: r for r in con.execute("PRAGMA table_info(user)")}
    con.close()
    assert cols["role"][3] == 0, "fixture should have a NULLable role column"

    # Exercise the real function from the migration script.
    _sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
    try:
        import migrate_sqlite_to_postgres as mig
    finally:
        _sys.path.pop(0)

    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM user").fetchone()
    con.close()

    from models import User as UserTable

    values, repairs = mig._row_values(row, UserTable.__table__)

    # Two repairs, not one, and both are correct:
    #   role              - column added later without NOT NULL, so it is NULL
    #   is_email_verified - absent from the legacy file entirely, so it reads as
    #                       NULL and falls back to its model default of False
    # The point of the assertion is that `role` is repaired from the *model
    # default* rather than guessed at or left NULL for Postgres to reject.
    assert repairs == 2, f"expected 2 NOT NULL repairs, got {repairs}"
    assert values["role"] == "student"
    assert values["is_email_verified"] is False