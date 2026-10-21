"""Give the agent's tables to the app.

The agent package keeps its own tables on its own registry, so it can be
imported without the web layer. It runs inside this app, in this database,
so the app has to own them: created here, migrated here, and known to the
drift check in alembic/env.py - which otherwise refuses to start the app
because the tables exist in the database but not in SQLModel.metadata.

The columns mirror the agent's exactly: the agent's queries are unqualified,
so the two must agree on the names.

Revision: 027
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "027_agent_tables"
down_revision: Union[str, None] = "026_admin_user_flags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: The tables the agent owns, and the columns they carry.
DRAFT_COLUMNS = (
    ("id", sa.Integer(), False, None),
    ("slug", sa.String(length=100), False, None),
    ("status", sa.String(length=50), False, "DRAFT"),
    ("title", sa.String(length=500), False, None),
    ("organization_name", sa.String(length=200), False, None),
    ("opportunity_type", sa.String(length=50), False, "INTERNERSHIP"),
    ("short_summary", sa.Text(), True, None),
    ("full_description", sa.Text(), True, None),
    ("location", sa.String(length=200), True, None),
    ("work_mode", sa.String(length=50), True, None),
    ("duration", sa.String(length=200), True, None),
    ("start_date", sa.DateTime(timezone=True), True, None),
    ("stipend_min", sa.Integer(), True, None),
    ("stipend_max", sa.Integer(), True, None),
    ("stipend_currency", sa.String(length=10), False, "INR"),
    ("stipend_period", sa.String(length=50), True, None),
    ("registration_deadline", sa.DateTime(timezone=True), True, None),
    ("deadline_type", sa.String(length=50), False, "fixed"),
    ("education_levels", sa.JSON(), True, None),
    ("allowed_branches", sa.JSON(), True, None),
    ("graduation_years", sa.JSON(), True, None),
    ("min_cgpa_or_percentage", sa.Float(), True, None),
    ("other_criteria", sa.Text(), True, None),
    ("skills_required", sa.JSON(), True, None),
    ("perks_benefits", sa.JSON(), True, None),
    ("selection_process", sa.Text(), True, None),
    ("documents_required", sa.JSON(), True, None),
    ("how_to_apply", sa.Text(), True, None),
    ("apply_url", sa.String(length=1000), False, None),
    ("secondary_sources", sa.JSON(), True, None),
    ("contact_email", sa.String(length=200), True, None),
    ("source_domain", sa.String(length=200), True, None),
    ("verification_report", sa.JSON(), True, None),
    ("confidence_score", sa.Float(), True, None),
    ("field_evidence", sa.JSON(), True, None),
    ("llm_provider", sa.String(length=50), False, "mock"),
    ("llm_model", sa.String(length=200), False, "mock"),
    ("prompt_version", sa.String(length=50), False, "1.0"),
    ("tags", sa.JSON(), True, None),
    ("version", sa.Integer(), False, "1"),
    ("created_by_run_id", sa.String(length=100), True, None),
    ("created_at", sa.DateTime(timezone=True), False, None),
)

VERIFY_COLUMNS = (
    ("id", sa.Integer(), False, None),
    ("organization_name", sa.String(length=200), False, None),
    ("title", sa.String(length=500), False, None),
    ("apply_url", sa.String(length=1000), False, None),
    ("status", sa.String(length=50), False, "DRAFT"),
)

TABLES = (
    ("oppfeed_opportunity_draft", DRAFT_COLUMNS),
    ("oppfeed_opportunity_verify", VERIFY_COLUMNS),
    ("oppfeed_opportunity_fewshot", DRAFT_COLUMNS),
)


def _is_postgres() -> bool:
    return op.get_context().dialect.name == "postgresql"


def _existing_tables() -> set:
    rows = op.get_bind().execute(
        sa.text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'core'"
        )
    ).all()
    return {row[0] for row in rows}


def upgrade() -> None:
    if not _is_postgres():
        return
    present = _existing_tables()
    for name, columns in TABLES:
        if name in present:
            continue
        op.create_table(
            name,
            *[
                sa.Column(
                    column,
                    type_,
                    nullable=nullable,
                    server_default=default,
                )
                for column, type_, nullable, default in columns
            ],
            sa.PrimaryKeyConstraint("id"),
            schema="core",
        )
        op.create_index(
            f"ix_{name}_slug", name, ["slug"], unique=True, schema="core"
        )


def downgrade() -> None:
    if not _is_postgres():
        return
    present = _existing_tables()
    for name, _columns in reversed(TABLES):
        if name not in present:
            continue
        # The index goes with the table, and an earlier downgrade may already
        # have taken it: dropping a table drops its indexes.
        op.drop_index(
            f"ix_{name}_slug", table_name=name, schema="core", if_exists=True
        )
        op.drop_table(name, schema="core")
