"""The webmail's foundation tables: sections, threads, labels, state, audit.

The old mail app had one table (the message) and filed by the address a
notice was sent to. The rebuild needs the pieces a real mailbox is made of:

- core.mail_section - the sections a group's mail is filed under, and who
  may read or moderate them (core.mail_section_access);
- core.mail_thread - the conversations;
- core.mail_label / core.mail_message_label - the labels a person puts on
  their own mail;
- core.mail_user_message_state - what one account did with one message;
- core.mail_audit_log - who changed a rule, re-routed a message or moved a
  cluster;
- core.mail_footer_template, core.mail_signature, core.mail_user_settings.

The message itself grows the headers a mail app needs (the full recipient
lists, the reply-to, the threading headers), the intake address it came
through, the routing metadata that answers "why is this here?", and the
authentication verdicts. The sender rule grows a priority, an active flag
and a note; the attachment grows a hash and a scan status.

Revision: 029
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "029_mail_foundation"
down_revision: Union[str, None] = "028_max_drafts_per_run"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: The tables this revision creates, with their columns.
TABLES = (
    (
        "mail_section",
        (
            ("id", sa.Integer(), False, None),
            ("group", sa.String(length=16), False, "ug"),
            ("key", sa.String(length=32), False, None),
            ("label", sa.String(length=64), False, None),
            ("description", sa.String(length=255), True, None),
            ("sort_order", sa.Integer(), False, "0"),
            ("is_public", sa.Boolean(), False, sa.true()),
            ("created_by", sa.Integer(), True, None),
            ("created_at", sa.DateTime(timezone=True), False, sa.func.now()),
        ),
        (
            ("uq_mail_section_group_key", ["group", "key"], True),
        ),
    ),
    (
        "mail_section_access",
        (
            ("id", sa.Integer(), False, None),
            ("user_id", sa.Integer(), False, None),
            ("section_id", sa.Integer(), False, None),
            ("can_read", sa.Boolean(), False, sa.true()),
            ("can_manage", sa.Boolean(), False, sa.false()),
            ("created_at", sa.DateTime(timezone=True), False, sa.func.now()),
        ),
        (
            (
                "uq_mail_section_access_user_section",
                ["user_id", "section_id"],
                True,
            ),
        ),
    ),
    (
        "mail_thread",
        (
            ("id", sa.Integer(), False, None),
            ("group", sa.String(length=16), False, "ug"),
            ("subject_key", sa.String(length=255), False, None),
            ("subject", sa.String(length=500), True, None),
            ("message_count", sa.Integer(), False, "0"),
            ("last_message_at", sa.DateTime(timezone=True), True, None),
            ("created_at", sa.DateTime(timezone=True), False, sa.func.now()),
        ),
        (
            ("ix_mail_thread_group_last", ["group", "last_message_at"], False),
        ),
    ),
    (
        "mail_label",
        (
            ("id", sa.Integer(), False, None),
            ("user_id", sa.Integer(), False, None),
            ("name", sa.String(length=64), False, None),
            ("color", sa.String(length=32), False, "cp-accent"),
            ("parent_id", sa.Integer(), True, None),
            ("is_system", sa.Boolean(), False, sa.false()),
            ("created_at", sa.DateTime(timezone=True), False, sa.func.now()),
        ),
        (
            ("uq_mail_label_user_name", ["user_id", "name"], True),
        ),
    ),
    (
        "mail_message_label",
        (
            ("id", sa.Integer(), False, None),
            ("message_id", sa.Integer(), False, None),
            ("label_id", sa.Integer(), False, None),
            ("created_at", sa.DateTime(timezone=True), False, sa.func.now()),
        ),
        (
            ("uq_mail_message_label", ["message_id", "label_id"], True),
        ),
    ),
    (
        "mail_user_message_state",
        (
            ("id", sa.Integer(), False, None),
            ("user_id", sa.Integer(), False, None),
            ("message_id", sa.Integer(), False, None),
            ("is_read", sa.Boolean(), False, sa.false()),
            ("is_starred", sa.Boolean(), False, sa.false()),
            ("is_important", sa.Boolean(), False, sa.false()),
            ("is_archived", sa.Boolean(), False, sa.false()),
            ("is_trashed", sa.Boolean(), False, sa.false()),
            ("snoozed_until", sa.DateTime(timezone=True), True, None),
            ("created_at", sa.DateTime(timezone=True), False, sa.func.now()),
        ),
        (
            (
                "uq_mail_user_message_state_user_message",
                ["user_id", "message_id"],
                True,
            ),
        ),
    ),
    (
        "mail_audit_log",
        (
            ("id", sa.Integer(), False, None),
            ("group", sa.String(length=16), False, "ug"),
            ("actor_user_id", sa.Integer(), True, None),
            ("action", sa.String(length=64), False, None),
            ("target_type", sa.String(length=32), True, None),
            ("target_id", sa.String(length=255), True, None),
            ("detail", sa.JSON(), True, None),
            ("created_at", sa.DateTime(timezone=True), False, sa.func.now()),
        ),
        (
            ("ix_mail_audit_log_group_created", ["group", "created_at"], False),
        ),
    ),
    (
        "mail_footer_template",
        (
            ("id", sa.Integer(), False, None),
            ("group", sa.String(length=16), False, "ug"),
            ("section", sa.String(length=32), False, ""),
            ("body_text", sa.Text(), False, ""),
            ("body_html", sa.Text(), True, None),
            ("is_default", sa.Boolean(), False, sa.false()),
            ("created_by", sa.Integer(), True, None),
            ("created_at", sa.DateTime(timezone=True), False, sa.func.now()),
        ),
        (
            (
                "uq_mail_footer_template_group_section",
                ["group", "section"],
                True,
            ),
        ),
    ),
    (
        "mail_signature",
        (
            ("id", sa.Integer(), False, None),
            ("user_id", sa.Integer(), False, None),
            ("body_text", sa.Text(), True, None),
            ("body_html", sa.Text(), True, None),
            ("created_at", sa.DateTime(timezone=True), False, sa.func.now()),
        ),
        (
            ("uq_mail_signature_user", ["user_id"], True),
        ),
    ),
    (
        "mail_user_settings",
        (
            ("id", sa.Integer(), False, None),
            ("user_id", sa.Integer(), False, None),
            ("settings", sa.JSON(), True, None),
            ("created_at", sa.DateTime(timezone=True), False, sa.func.now()),
            ("updated_at", sa.DateTime(timezone=True), False, sa.func.now()),
        ),
        (
            ("uq_mail_user_settings_user", ["user_id"], True),
        ),
    ),
    (
        "mail_cluster",
        (
            ("id", sa.Integer(), False, None),
            ("group", sa.String(length=16), False, "ug"),
            ("name", sa.String(length=120), False, None),
            ("section", sa.String(length=32), False, "other"),
            ("description", sa.String(length=500), True, None),
            ("created_by", sa.Integer(), True, None),
            ("created_at", sa.DateTime(timezone=True), False, sa.func.now()),
        ),
        (
            ("uq_mail_cluster_group_name", ["group", "name"], True),
        ),
    ),
    (
        "mail_sender_rule",
        (
            ("id", sa.Integer(), False, None),
            ("group", sa.String(length=16), False, "ug"),
            ("pattern", sa.String(length=255), False, None),
            ("kind", sa.String(length=16), False, "exact"),
            ("section", sa.String(length=32), False, "other"),
            ("cluster_id", sa.Integer(), True, None),
            ("priority", sa.Integer(), False, "0"),
            ("is_active", sa.Boolean(), False, sa.true()),
            ("notes", sa.String(length=500), True, None),
            ("created_by", sa.Integer(), True, None),
            ("created_at", sa.DateTime(timezone=True), False, sa.func.now()),
        ),
        (
            ("uq_mail_sender_rule_group_pattern", ["group", "pattern"], True),
        ),
    ),
    (
        "mail_message",
        (
            ("id", sa.Integer(), False, None),
            ("message_id", sa.String(length=255), False, None),
            ("group", sa.String(length=16), False, "ug"),
            ("section", sa.String(length=32), False, "other"),
            ("cluster_id", sa.Integer(), True, None),
            ("thread_id", sa.String(length=255), True, None),
            ("direction", sa.String(length=16), False, "inbox"),
            ("is_archived", sa.Boolean(), False, sa.false()),
            ("is_trashed", sa.Boolean(), False, sa.false()),
            ("from_email", sa.String(length=255), False, None),
            ("from_name", sa.String(length=255), True, None),
            ("to_email", sa.String(length=255), True, None),
            ("to_emails", sa.JSON(), True, None),
            ("cc_emails", sa.JSON(), True, None),
            ("bcc_emails", sa.JSON(), True, None),
            ("reply_to", sa.String(length=255), True, None),
            ("reply_to_name", sa.String(length=255), True, None),
            ("in_reply_to", sa.String(length=255), True, None),
            ("references", sa.String(length=500), True, None),
            ("subject", sa.String(length=500), True, None),
            ("body_text", sa.Text(), True, None),
            ("body_html", sa.Text(), True, None),
            ("snippet", sa.String(length=500), True, None),
            ("intake_address", sa.String(length=255), True, None),
            ("received_at", sa.DateTime(timezone=True), True, None),
            ("matched_rule_id", sa.Integer(), True, None),
            ("routing_reason", sa.String(length=255), True, None),
            ("routed_at", sa.DateTime(timezone=True), True, None),
            ("routed_by", sa.String(length=64), True, None),
            ("auth_spf", sa.String(length=32), True, None),
            ("auth_dkim", sa.String(length=32), True, None),
            ("auth_dmarc", sa.String(length=32), True, None),
            ("auth_summary", sa.String(length=255), True, None),
            ("is_quarantined", sa.Boolean(), False, sa.false()),
            ("is_important", sa.Boolean(), False, sa.false()),
            ("has_attachments", sa.Boolean(), False, sa.false()),
            ("attachments", sa.JSON(), True, None),
            ("labels", sa.JSON(), True, None),
            ("created_by", sa.Integer(), True, None),
            ("created_at", sa.DateTime(timezone=True), False, sa.func.now()),
        ),
        (
            ("ix_mail_message_message_id", ["message_id"], True),
            ("ix_mail_message_group", ["group"], False),
            ("ix_mail_message_section", ["section"], False),
            ("ix_mail_message_received_at", ["received_at"], False),
            ("ix_mail_message_created_by", ["created_by"], False),
            ("ix_mail_message_from_email", ["from_email"], False),
            (
                "ix_mail_message_group_section_received",
                ["group", "section", "received_at"],
                False,
            ),
        ),
    ),
    (
        "mail_file",
        (
            ("id", sa.Integer(), False, None),
            ("message_id", sa.Integer(), False, None),
            ("filename", sa.String(length=500), False, None),
            ("content_type", sa.String(length=255), True, None),
            ("size", sa.Integer(), False, "0"),
            ("sha256", sa.String(length=64), True, None),
            ("scan_status", sa.String(length=16), False, "pending"),
            ("section", sa.String(length=32), True, None),
            ("data", sa.LargeBinary(), False, None),
            ("created_at", sa.DateTime(timezone=True), False, sa.func.now()),
        ),
        (
            ("ix_mail_file_message", ["message_id"], False),
        ),
    ),
)


def _is_postgres() -> bool:
    return op.get_context().dialect.name == "postgresql"


def _table_exists(table: str) -> bool:
    rows = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'core' AND table_name = :table"
        ),
        {"table": table},
    ).all()
    return bool(rows)


def _index_exists(table: str, name: str) -> bool:
    rows = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM pg_indexes "
            "WHERE schemaname = 'core' AND tablename = :table AND indexname = :name"
        ),
        {"table": table, "name": name},
    ).all()
    return bool(rows)


def upgrade() -> None:
    if not _is_postgres():
        return

    for table, columns, indexes in TABLES:
        if _table_exists(table):
            continue
        op.create_table(
            table,
            *[
                sa.Column(
                    name,
                    type_,
                    nullable=nullable,
                    server_default=default,
                )
                for name, type_, nullable, default in columns
            ],
            sa.PrimaryKeyConstraint("id"),
            schema="core",
        )
        for name, index_columns, unique in indexes:
            op.create_index(
                name, table, index_columns, unique=unique, schema="core"
            )


def downgrade() -> None:
    if not _is_postgres():
        return

    for table, _columns, indexes in reversed(TABLES):
        if not _table_exists(table):
            continue
        for name, _index_columns, _unique in reversed(indexes):
            if _index_exists(table, name):
                op.drop_index(name, table_name=table, schema="core")
        op.drop_table(table, schema="core")
