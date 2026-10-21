"""Align the seating index with the exam timetable.

The two documents are uploaded separately, so they can disagree: a typo in
one, a header the parser read differently in the other. When they do, the
timetable screen and the roll lookup answer the same question differently -
and the student cannot tell which one to believe.

The timetable is the published document, so it decides the slot, and the
seating rows are moved onto it. The repair is deliberately conservative: a
course the timetable places in a single slot moves there; a course it places
in several is left alone, because choosing between two real exams would be a
guess.

Revision: 024
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "024_reconcile_seating"
down_revision: Union[str, None] = "023_admin_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgres() -> bool:
    return op.get_context().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        return

    from features.exam.reconcile import align_row, slots_by_course

    bind = op.get_bind()
    schedule_rows = bind.execute(
        sa.text(
            "SELECT course_code, schedule_date, start_time, end_time "
            "FROM academic.mid_sem_schedule "
            "WHERE schedule_date IS NOT NULL"
        )
    ).mappings().all()
    slots = slots_by_course([dict(row) for row in schedule_rows])
    if not slots:
        return

    seating_rows = bind.execute(
        sa.text(
            "SELECT id, course_code, seating_date, start_time, end_time "
            "FROM academic.exam_seating"
        )
    ).mappings().all()

    updates = []
    for row in seating_rows:
        aligned = {
            "course_code": row["course_code"],
            "seating_date": row["seating_date"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
        }
        if not align_row(aligned, slots):
            continue
        updates.append(
            {
                "id": row["id"],
                "date": aligned["seating_date"],
                "start": aligned["start_time"],
                "end": aligned["end_time"],
            }
        )

    if not updates:
        return

    bind.execute(
        sa.text(
            "UPDATE academic.exam_seating "
            "SET seating_date = :date, start_time = :start, end_time = :end "
            "WHERE id = :id"
        ),
        updates,
    )


def downgrade() -> None:
    if not _is_postgres():
        return
    # Not reversible on purpose: the slot a row was moved away from is not
    # recorded, and putting a row back on a slot the timetable contradicts
    # would restore the very disagreement this migration removes.
    pass
