"""phase3_academic_core_tables

Revision ID: 001_phase3_academic_core_tables
Revises: ffba99886aaf
Create Date: 2026-10-10 07:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'phase3_001_academic_core'
down_revision: Union[str, None] = 'ffba99886aaf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text('CREATE SCHEMA IF NOT EXISTS "academic"'))
    # 0001 created public.course (legacy shape with semester/branch).
    # Current models use academic.course (code,name,instructor,is_elective,is_extra).
    # Fresh rebuilds (tests) have no academic.course, so phase3 FKs fail.
    # Prod already has it via create_all, so IF NOT EXISTS is a safe no-op there.
    op.execute(sa.text('''
        CREATE TABLE IF NOT EXISTS academic.course (
            id SERIAL PRIMARY KEY,
            code VARCHAR NOT NULL UNIQUE,
            name VARCHAR NOT NULL,
            instructor VARCHAR,
            is_elective BOOLEAN NOT NULL DEFAULT false,
            is_extra BOOLEAN NOT NULL DEFAULT false
        )
    '''))
    op.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_academic_course_code ON academic.course (code)'))
    # Fresh rebuilds (tests) have no timetable_upload yet: it was created via
    # create_all in prod, never via Alembic. Full current shape; IF NOT EXISTS
    # keeps this a safe no-op where it already exists.
    op.execute(sa.text('''
        CREATE TABLE IF NOT EXISTS academic.timetable_upload (
            id SERIAL PRIMARY KEY,
            filename VARCHAR NOT NULL,
            original_name VARCHAR,
            size_bytes INTEGER,
            uploaded_at TIMESTAMP
        )
    '''))
    # 3.1 academic_term table
    op.create_table(
        'academic_term',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),  # e.g., "2025-26 Sem 1"
        sa.Column('academic_year', sa.String(length=20), nullable=False),  # e.g., "2025-26"
        sa.Column('term_number', sa.Integer(), nullable=False),  # 1=Sem 1, 2=Sem 2, etc.
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.PrimaryKeyConstraint('id'),
        schema='academic'
    )
    op.create_index('ix_academic_term_is_current', 'academic_term', ['is_current'], schema='academic')

    # 3.2 branch lookup table
    op.create_table(
        'branch',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),  # e.g., "CSE", "ECE", "ME"
        sa.Column('name', sa.String(length=100), nullable=False),  # e.g., "Computer Science"
        sa.Column('programme', sa.String(length=50), nullable=True),  # BTech, MTech, BDes, etc.
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_branch_code'),
        schema='academic'
    )

    # 3.3 course_offering table - the central concept
    op.create_table(
        'course_offering',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('course_id', sa.Integer(), nullable=False),
        sa.Column('term_id', sa.Integer(), nullable=False),
        sa.Column('branch_id', sa.Integer(), nullable=False),
        sa.Column('semester', sa.Integer(), nullable=False),
        sa.Column('section', sa.String(length=10), nullable=True),  # A, B, etc.
        sa.Column('instructor', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='academic'
    )
    op.create_foreign_key(
        'fk_course_offering_course', 'course_offering', 'course',
        ['course_id'], ['id'], source_schema='academic', referent_schema='academic', ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_course_offering_term', 'course_offering', 'academic_term',
        ['term_id'], ['id'], source_schema='academic', referent_schema='academic', ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_course_offering_branch', 'course_offering', 'branch',
        ['branch_id'], ['id'], source_schema='academic', referent_schema='academic', ondelete='CASCADE'
    )
    op.create_index('ix_course_offering_course_id', 'course_offering', ['course_id'], schema='academic')
    op.create_index('ix_course_offering_term_id', 'course_offering', ['term_id'], schema='academic')
    op.create_index('ix_course_offering_branch_id', 'course_offering', ['branch_id'], schema='academic')

    # academic.timetable_slot likewise predates Alembic (create_all in prod).
    # Full current shape so fresh rebuilds match prod; placed after
    # course_offering so the offering_id FK resolves, and before the
    # timetable_slot_branch junction below which references it.
    op.execute(sa.text('''
        CREATE TABLE IF NOT EXISTS academic.timetable_slot (
            id SERIAL PRIMARY KEY,
            day VARCHAR NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            room VARCHAR NOT NULL,
            course_code VARCHAR NOT NULL,
            instructor VARCHAR,
            branch_or_program VARCHAR NOT NULL,
            semester INTEGER,
            offering_id INTEGER REFERENCES academic.course_offering(id) ON DELETE SET NULL
        )
    '''))
    op.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_academic_timetable_slot_day ON academic.timetable_slot (day)'))
    op.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_academic_timetable_slot_course_code ON academic.timetable_slot (course_code)'))

    # 3.4 timetable_slot_branch junction table
    op.create_table(
        'timetable_slot_branch',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slot_id', sa.Integer(), nullable=False),
        sa.Column('branch_id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='academic'
    )
    op.create_foreign_key(
        'fk_timetable_slot_branch_slot', 'timetable_slot_branch', 'timetable_slot',
        ['slot_id'], ['id'], source_schema='academic', referent_schema='academic', ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_timetable_slot_branch_branch', 'timetable_slot_branch', 'branch',
        ['branch_id'], ['id'], source_schema='academic', referent_schema='academic', ondelete='CASCADE'
    )
    op.create_index('ix_timetable_slot_branch_slot_id', 'timetable_slot_branch', ['slot_id'], schema='academic')
    op.create_index('ix_timetable_slot_branch_branch_id', 'timetable_slot_branch', ['branch_id'], schema='academic')
    op.create_unique_constraint('uq_timetable_slot_branch', 'timetable_slot_branch', ['slot_id', 'branch_id'], schema='academic')

    # 3.5 Add term_id to timetable_upload
    op.add_column('timetable_upload', sa.Column('term_id', sa.Integer(), nullable=True), schema='academic')
    op.create_foreign_key(
        'fk_timetable_upload_term', 'timetable_upload', 'academic_term',
        ['term_id'], ['id'], source_schema='academic', referent_schema='academic', ondelete='SET NULL'
    )
    op.create_index('ix_timetable_upload_term_id', 'timetable_upload', ['term_id'], schema='academic')


def downgrade() -> None:
    op.drop_index('ix_timetable_upload_term_id', table_name='timetable_upload', schema='academic')
    op.drop_constraint('fk_timetable_upload_term', 'timetable_upload', schema='academic', type_='foreignkey')
    op.drop_column('timetable_upload', 'term_id', schema='academic')

    op.drop_constraint('uq_timetable_slot_branch', 'timetable_slot_branch', schema='academic')
    op.drop_index('ix_timetable_slot_branch_branch_id', table_name='timetable_slot_branch', schema='academic')
    op.drop_index('ix_timetable_slot_branch_slot_id', table_name='timetable_slot_branch', schema='academic')
    op.drop_constraint('fk_timetable_slot_branch_branch', 'timetable_slot_branch', schema='academic', type_='foreignkey')
    op.drop_constraint('fk_timetable_slot_branch_slot', 'timetable_slot_branch', schema='academic', type_='foreignkey')
    op.drop_table('timetable_slot_branch', schema='academic')

    op.drop_index('ix_course_offering_branch_id', table_name='course_offering', schema='academic')
    op.drop_index('ix_course_offering_term_id', table_name='course_offering', schema='academic')
    op.drop_index('ix_course_offering_course_id', table_name='course_offering', schema='academic')
    op.drop_constraint('fk_course_offering_branch', 'course_offering', schema='academic', type_='foreignkey')
    op.drop_constraint('fk_course_offering_term', 'course_offering', schema='academic', type_='foreignkey')
    op.drop_constraint('fk_course_offering_course', 'course_offering', schema='academic', type_='foreignkey')
    op.drop_table('course_offering', schema='academic')

    op.drop_table('branch', schema='academic')

    op.drop_index('ix_academic_term_is_current', table_name='academic_term', schema='academic')
    op.drop_table('academic_term', schema='academic')