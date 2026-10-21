"""Let a run write as many drafts as the settings allow.

The template stage templated the first ten verified opportunities and
dropped the rest, so a run that verified fifty-three wrote ten and
reported ten - as if that were all it had found. The cap is a cost guard,
not a limit on what may be published, and it is now a setting the admin
sets.

Revision: 028
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "028_max_drafts_per_run"
down_revision: Union[str, None] = "027_agent_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists() -> bool:
    row = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'core' AND table_name = 'oppfeed_agent_settings' "
            "AND column_name = 'max_drafts_per_run'"
        )
    ).first()
    return row is not None


def upgrade() -> None:
    if op.get_context().dialect.name != "postgresql":
        return
    if _column_exists():
        return
    op.add_column(
        "oppfeed_agent_settings",
        sa.Column(
            "max_drafts_per_run",
            sa.Integer(),
            nullable=False,
            server_default="100",
        ),
        schema="core",
    )


def downgrade() -> None:
    if op.get_context().dialect.name != "postgresql":
        return
    if not _column_exists():
        return
    op.drop_column("oppfeed_agent_settings", "max_drafts_per_run", schema="core")
