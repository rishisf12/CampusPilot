"""admin feature tables catchup

Revision ID: 009_admin_feature_tables
Revises: 855f4aa53d70
Create Date: 2026-10-15

Creates every table the new admin features need that no earlier migration
created: alerts (3), analytics (5), broadcasts (2), errors (2), force_update
(1), health (2), moderation (1), security feed + event (2), user_control (1).

Each table is created from its SQLModel definition with checkfirst=True rather
than transcribed DDL, so the migration cannot drift from the models. Tables
that already exist (audit_log, feature_flag, maintenance_window,
remote_config, ...) are untouched - only the 18 verified-missing names below
are created. Downgrade drops exactly those tables.
"""
from typing import Sequence, Union

from alembic import op

revision: str = '009_admin_feature_tables'
down_revision: Union[str, None] = '855f4aa53d70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (module, Table key in metadata). Keys are schema-qualified because several
# table names exist in more than one schema (e.g. core.security_event vs
# telemetry.security_event).
TABLES: list[tuple[str, str]] = [
    ("features.alerts.models", "core.alert_channel"),
    ("features.alerts.models", "core.alert_rule"),
    ("features.alerts.models", "core.alert_incident"),
    ("features.analytics.models", "core.analytics_event"),
    ("features.analytics.models", "core.analytics_segment"),
    ("features.analytics.models", "core.analytics_funnel"),
    ("features.analytics.models", "core.analytics_anomaly"),
    ("features.analytics.models", "core.analytics_daily_aggregate"),
    ("features.broadcasts.models", "core.broadcast"),
    ("features.broadcasts.models", "core.broadcast_delivery"),
    ("features.errors.models", "core.error_fingerprint"),
    ("features.errors.models", "core.error_event"),
    ("features.force_update.models", "core.force_update_rule"),
    ("features.health.models", "core.health_check"),
    ("features.health.models", "core.health_history"),
    ("features.moderation.models", "core.moderation_queue"),
    ("features.security.models", "core.security_feed"),
    ("features.security.models", "core.security_event"),
    ("features.user_control.models", "core.user_control_action"),
]


def _tables():
    import importlib

    from sqlmodel import SQLModel

    seen: set[str] = set()
    for module_name, _key in TABLES:
        if module_name in seen:
            continue
        seen.add(module_name)
        importlib.import_module(module_name)
    return SQLModel.metadata.tables


def _drop_legacy_misplaced_table(bind) -> None:
    """Remove the monitoring-shaped `core.security_event` if present.

    The 27f44ac2c78b migration created `security_event` with no schema, and
    the test/dev search_path (`core` first) landed it in `core` with the
    monitoring columns (kind/platform/ts). The ORM model for monitoring lives
    in `telemetry`, so this table was never written or read - dead weight that
    now blocks the admin-shaped table of the same name: CREATE TABLE IF NOT
    EXISTS skips (name taken) and the admin indexes fail (no such columns).

    Only drops when the table is both wrong-shaped (no `event_type`) and
    empty. Anything else raises instead of destroying data.
    """
    from sqlalchemy import text

    cols = {
        row[0]
        for row in bind.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'core' AND table_name = 'security_event'"
            )
        ).fetchall()
    }
    if not cols or "event_type" in cols:
        return
    count = bind.execute(text("SELECT count(*) FROM core.security_event")).scalar()
    if count:
        raise RuntimeError(
            f"core.security_event has {count} rows but not the admin shape; "
            "refusing to replace it automatically."
        )
    bind.execute(text("DROP TABLE core.security_event"))


def upgrade() -> None:
    from sqlalchemy.schema import CreateIndex, CreateTable

    tables = _tables()
    bind = op.get_bind()
    _drop_legacy_misplaced_table(bind)
    # Table and indexes are created as separate IF NOT EXISTS statements.
    # `Table.create(checkfirst=True)` was tried first and failed: some models
    # declare `index=True` inside an explicit `sa_column=Column(...)`, which
    # makes SQLAlchemy emit the same CREATE INDEX twice inside one call, and
    # the resulting DuplicateTable error rolled back the table creation along
    # with it. Separate idempotent statements cannot fail that way.
    for _, key in TABLES:
        table = tables[key]
        bind.execute(CreateTable(table, if_not_exists=True))
        for index in table.indexes:
            bind.execute(CreateIndex(index, if_not_exists=True))


def downgrade() -> None:
    tables = _tables()
    bind = op.get_bind()
    for _, key in reversed(TABLES):
        tables[key].drop(bind=bind, checkfirst=True)
