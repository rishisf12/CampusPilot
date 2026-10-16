"""Relabel `attendancestatus` to the enum *values*, not the enum *names*.

    attendance was unreadable AND unwritable on PostgreSQL.

The Python enum and the database had drifted apart in a way that broke both
directions of the round trip:

    models.AttendanceStatus.PRESENT has value "Present"
    models.py stores it with values_callable=[e.value ...], so the ORM sends
      the string "Present"

but the initial migration created the Postgres type from the enum *names*:

    sa.Enum('PRESENT', 'ABSENT', 'CANCELLED', name='attendancestatus')

so the database only accepted "PRESENT". That produced two failures:

    write - psycopg.errors.InvalidTextRepresentation
            invalid input value for enum attendancestatus: "Cancelled"
    read  - LookupError: 'PRESENT' is not among the defined enum values.
            Possible values: Present, Absent, Cancelled

Every existing record was therefore unreadable, not just unwritable - the
summary endpoints silently reported 100% for courses that had absences.

The value form is the correct target: it is what the API accepts
(AttendanceMark.status), what the frontend sends
('Present' | 'Absent' | 'Cancelled'), and what models.py is configured to write.
So the database moves to the values, not the other way round.

Postgres cannot alter an enum type's labels in place, so the type is rebuilt:
create a replacement with the right labels, cast the column across, drop the old
type, rename. The CASE below maps the old labels onto the new ones and passes
anything already in the value form through untouched, so re-running is safe.

Only PostgreSQL needs this. On SQLite the model declares native_enum=False, so
the column is a VARCHAR with a CHECK constraint built from the same values and
was never affected.

Verified by: test_postgres_migration.py::test_attendance_status_labels and
    ::test_attendance_round_trip
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

# Keep this id <= 32 characters: alembic_version.version_num is varchar(32)
# and a longer id fails at the very last step with StringDataRightTruncation,
# after the migration has already run its DDL.
revision: str = '012_attendance_enum_values'
down_revision: Union[str, None] = '011_user_settings'
branch_labels = None
depends_on = None

TYPE_NAME = 'attendancestatus'
OLD_TYPE = 'attendancestatus_old'
TABLE = 'academic.attendance_record'
COLUMN = 'status'

# What the ORM writes, and what the API and frontend speak.
WANTED = ('Present', 'Absent', 'Cancelled')


def _labels(bind) -> list:
    return list(
        bind.execute(
            sa.text(
                "SELECT e.enumlabel FROM pg_type t "
                "JOIN pg_namespace n ON n.oid = t.typnamespace "
                "JOIN pg_enum e ON e.enumtypid = t.oid "
                "WHERE t.typname = :name AND n.nspname = 'public' "
                "ORDER BY e.enumsortorder"
            ),
            {"name": TYPE_NAME},
        ).scalars()
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return

    current = _labels(bind)
    if not current:
        # No native type: the column is a plain VARCHAR (or the table is not
        # there yet). Either way there is nothing to relabel.
        return
    if tuple(current) == WANTED:
        # Already correct - a fresh install of the corrected initial migration,
        # or this migration applied twice. Leave it alone.
        return

    op.execute(f'ALTER TABLE {TABLE} ALTER COLUMN {COLUMN} DROP DEFAULT')
    op.execute(
        'CREATE TYPE public.' + OLD_TYPE + ' AS ENUM ('
        + ', '.join(f"'{v}'" for v in WANTED)
        + ')'
    )

    # Map the old name labels onto the value labels. Rows already stored in the
    # value form pass through, and anything unrecognised raises here rather than
    # being silently coerced to NULL.
    op.execute(
        f"""
        ALTER TABLE {TABLE}
        ALTER COLUMN {COLUMN} TYPE public.{OLD_TYPE}
        USING (
            CASE {COLUMN}::text
                WHEN 'PRESENT'   THEN 'Present'
                WHEN 'ABSENT'    THEN 'Absent'
                WHEN 'CANCELLED' THEN 'Cancelled'
                WHEN 'Present'   THEN 'Present'
                WHEN 'Absent'    THEN 'Absent'
                WHEN 'Cancelled' THEN 'Cancelled'
                ELSE NULL
            END
        )::public.{OLD_TYPE}
        """
    )

    op.execute(f'DROP TYPE public.{TYPE_NAME}')
    op.execute(f'ALTER TYPE public.{OLD_TYPE} RENAME TO {TYPE_NAME}')


def downgrade() -> None:
    """Deliberately a no-op on a correctly-labelled database.

    The obvious inverse of this migration is to relabel the values back to the
    uppercase names. That would be a downgrade that knowingly reintroduces the
    bug: the initial migration has been corrected to create the value labels,
    so a database at revision 011 is expected to hold them, and writing the
    names back would put it into the broken state this migration exists to fix.

    So the downgrade returns early whenever the labels are already correct and
    leaves them alone. The name-restore below only runs when the type holds
    labels that are neither form - a torn-down database - where leaving them
    unrecognised would make the next upgrade fail on the CASE.
    """
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return

    current = _labels(bind)
    if not current or tuple(current) == WANTED:
        return

    # Values -> names. Rows are already in the value form at this point.
    op.execute(
        "CREATE TYPE public." + OLD_TYPE + " AS ENUM ('PRESENT', 'ABSENT', 'CANCELLED')"
    )
    op.execute(
        f"""
        ALTER TABLE {TABLE}
        ALTER COLUMN {COLUMN} TYPE public.{OLD_TYPE}
        USING (
            CASE {COLUMN}::text
                WHEN 'Present'   THEN 'PRESENT'
                WHEN 'Absent'    THEN 'ABSENT'
                WHEN 'Cancelled' THEN 'CANCELLED'
                ELSE NULL
            END
        )::public.{OLD_TYPE}
        """
    )
    op.execute(f'DROP TYPE public.{TYPE_NAME}')
    op.execute(f'ALTER TYPE public.{OLD_TYPE} RENAME TO {TYPE_NAME}')
