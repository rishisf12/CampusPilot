"""phase1_add_attendance_user_id

Revision ID: 8e1fa85035dc
Revises: 0c60d501467d
Create Date: 2026-10-10 06:05:44.401164
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = '8e1fa85035dc'
down_revision: Union[str, None] = '0c60d501467d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1.1 attendance_record: add user_id
    # attendance_record currently has 0 rows, so no backfill needed
    op.add_column('attendance_record', sa.Column('user_id', sa.Integer(), nullable=True))

    # Since table is empty, we can make it NOT NULL immediately
    op.alter_column('attendance_record', 'user_id', nullable=False)

    # Add foreign key to user.id with CASCADE delete
    op.create_foreign_key(
        'fk_attendance_record_user_id_user',
        'attendance_record', 'user',
        ['user_id'], ['id'],
        ondelete='CASCADE'
    )

    # Unique index on (user_id, course_id, date) - prevents duplicate attendance for same user/course/date
    op.create_index(
        'uq_attendance_user_course_date',
        'attendance_record',
        ['user_id', 'course_id', 'date'],
        unique=True
    )

    # Index on user_id for query performance
    op.create_index(
        'ix_attendance_record_user_id',
        'attendance_record',
        ['user_id'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_attendance_record_user_id', table_name='attendance_record')
    op.drop_index('uq_attendance_user_course_date', table_name='attendance_record')
    op.drop_constraint('fk_attendance_record_user_id_user', 'attendance_record', type_='foreignkey')
    op.alter_column('attendance_record', 'user_id', nullable=True)
    op.drop_column('attendance_record', 'user_id')