"""Create OppFeed tables.

Adds tables for the OppFeed integration (admin-managed opportunity discovery
and faculty-facing opportunity feed):

- oppfeed_opportunity - published opportunities
- oppfeed_agent_run - agent pipeline runs
- oppfeed_run_step - individual steps within a run
- oppfeed_agent_settings - global agent configuration
- oppfeed_source_rule - allow/deny rules for source domains
- oppfeed_search_query - search queries for the agent pipeline
- oppfeed_feedback - reviewer feedback on opportunities
- oppfeed_llm_cache - cached LLM responses
- oppfeed_llm_usage - per-run LLM usage tracking

Revision: 016
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016_oppfeed_models"
down_revision: Union[str, None] = "015_class_timetable_uploads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- oppfeed_opportunity ----
    op.create_table(
        "oppfeed_opportunity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("status", sa.Enum("draft", "in_review", "approved", "scheduled", "published", "rejected", "expired", "archived", name="opportunitystatus", native_enum=False), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("organization_name", sa.String(length=200), nullable=False),
        sa.Column("organization_logo_url", sa.String(length=1000), nullable=True),
        sa.Column("banner_url", sa.String(length=1000), nullable=True),
        sa.Column("opportunity_type", sa.Enum("internship", "job", "hackathon", "fellowship", name="opportunitytype", native_enum=False), nullable=False),
        sa.Column("short_summary", sa.String(length=1000), nullable=True),
        sa.Column("full_description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("work_mode", sa.Enum("onsite", "remote", "hybrid", name="workmode", native_enum=False), nullable=True),
        sa.Column("duration", sa.String(length=200), nullable=True),
        sa.Column("start_date", sa.String(length=100), nullable=True),
        sa.Column("stipend_min", sa.Float(), nullable=True),
        sa.Column("stipend_max", sa.Float(), nullable=True),
        sa.Column("stipend_currency", sa.String(length=10), nullable=True),
        sa.Column("stipend_period", sa.String(length=50), nullable=True),
        sa.Column("stipend_notes", sa.String(length=500), nullable=True),
        sa.Column("registration_start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registration_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deadline_type", sa.Enum("fixed", "rolling", "unspecified", name="deadlinetype", native_enum=False), nullable=False),
        sa.Column("education_levels", sa.JSON(), nullable=False),
        sa.Column("allowed_branches", sa.JSON(), nullable=False),
        sa.Column("graduation_years", sa.JSON(), nullable=False),
        sa.Column("min_cgpa_or_percentage", sa.Float(), nullable=True),
        sa.Column("other_criteria", sa.String(length=2000), nullable=True),
        sa.Column("open_to_countries", sa.JSON(), nullable=False),
        sa.Column("skills_required", sa.JSON(), nullable=False),
        sa.Column("perks_benefits", sa.JSON(), nullable=False),
        sa.Column("selection_process", sa.String(length=2000), nullable=True),
        sa.Column("documents_required", sa.JSON(), nullable=False),
        sa.Column("how_to_apply", sa.String(length=2000), nullable=True),
        sa.Column("apply_url", sa.String(length=1000), nullable=False),
        sa.Column("secondary_sources", sa.JSON(), nullable=False),
        sa.Column("attachments", sa.JSON(), nullable=False),
        sa.Column("contact_email", sa.String(length=200), nullable=True),
        sa.Column("source_domain", sa.String(length=200), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_report", sa.JSON(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("field_evidence", sa.JSON(), nullable=True),
        sa.Column("llm_provider", sa.String(length=50), nullable=True),
        sa.Column("llm_model", sa.String(length=200), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by_run_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), onupdate=sa.text("now()"), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_publish_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_oppfeed_opportunity_created_at"), "oppfeed_opportunity", ["created_at"], unique=False)
    op.create_index(op.f("ix_oppfeed_opportunity_registration_deadline"), "oppfeed_opportunity", ["registration_deadline"], unique=False)
    op.create_index(op.f("ix_oppfeed_opportunity_slug"), "oppfeed_opportunity", ["slug"], unique=True)
    op.create_index(op.f("ix_oppfeed_opportunity_source_domain"), "oppfeed_opportunity", ["source_domain"], unique=False)
    op.create_index(op.f("ix_oppfeed_opportunity_status"), "oppfeed_opportunity", ["status"], unique=False)
    op.create_index(op.f("ix_oppfeed_opportunity_type"), "oppfeed_opportunity", ["opportunity_type"], unique=False)

    # ---- oppfeed_agent_run ----
    op.create_table(
        "oppfeed_agent_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.Enum("pending", "running", "completed", "failed", "cancelled", name="runstatus", native_enum=False), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("opportunities_found", sa.Integer(), nullable=False),
        sa.Column("opportunities_verified", sa.Integer(), nullable=False),
        sa.Column("opportunities_rejected", sa.Integer(), nullable=False),
        sa.Column("opportunities_drafted", sa.Integer(), nullable=False),
        sa.Column("opportunities_published", sa.Integer(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=True),
        sa.Column("llm_calls", sa.Integer(), nullable=False),
        sa.Column("llm_tokens", sa.Integer(), nullable=False),
        sa.Column("llm_cost_estimate", sa.Float(), nullable=True),
        sa.Column("checkpoint", sa.JSON(), nullable=True),
        sa.Column("current_stage", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_oppfeed_agent_run_started_at"), "oppfeed_agent_run", ["started_at"], unique=False)
    op.create_index(op.f("ix_oppfeed_agent_run_status"), "oppfeed_agent_run", ["status"], unique=False)
    op.create_index(op.f("ix_oppfeed_agent_run_run_id"), "oppfeed_agent_run", ["run_id"], unique=True)

    # ---- oppfeed_run_step ----
    op.create_table(
        "oppfeed_run_step",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("step_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.Enum("pending", "running", "completed", "failed", "skipped", name="runstepstatus", native_enum=False), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_data", sa.JSON(), nullable=True),
        sa.Column("output_data", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.String(length=2000), nullable=True),
        sa.Column("llm_provider", sa.String(length=50), nullable=True),
        sa.Column("llm_model", sa.String(length=200), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["oppfeed_agent_run.run_id"], ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_oppfeed_run_step_run_id"), "oppfeed_run_step", ["run_id"], unique=False)
    op.create_index(op.f("ix_oppfeed_run_step_status"), "oppfeed_run_step", ["status"], unique=False)

    # ---- oppfeed_agent_settings ----
    op.create_table(
        "oppfeed_agent_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_window_start", sa.String(), nullable=False),
        sa.Column("run_window_end", sa.String(), nullable=False),
        sa.Column("auto_publish_enabled", sa.Boolean(), nullable=False),
        sa.Column("auto_publish_threshold", sa.Float(), nullable=False),
        sa.Column("llm_provider_chain", sa.String(), nullable=False),
        sa.Column("llm_max_rpm", sa.Integer(), nullable=False),
        sa.Column("enable_agent", sa.Boolean(), nullable=False),
        sa.Column("enable_scheduler", sa.Boolean(), nullable=False),
        sa.Column("enable_vision", sa.Boolean(), nullable=False),
        sa.Column("enable_banner_gen", sa.Boolean(), nullable=False),
        sa.Column("enable_audio_summary", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), onupdate=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # ---- oppfeed_source_rule ----
    op.create_table(
        "oppfeed_source_rule",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("domain", sa.String(length=200), nullable=False),
        sa.Column("rule_type", sa.String(length=10), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_oppfeed_source_rule_domain"), "oppfeed_source_rule", ["domain"], unique=True)

    # ---- oppfeed_search_query ----
    op.create_table(
        "oppfeed_search_query",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("query", sa.String(length=500), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("is_seed", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_oppfeed_search_query_enabled"), "oppfeed_search_query", ["enabled"], unique=False)

    # ---- oppfeed_feedback ----
    op.create_table(
        "oppfeed_feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("thumbs_up", sa.Boolean(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("comment", sa.String(length=2000), nullable=True),
        sa.Column("applied_as_instruction", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), onupdate=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["opportunity_id"], ["oppfeed_opportunity.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_oppfeed_feedback_opportunity_id"), "oppfeed_feedback", ["opportunity_id"], unique=False)

    # ---- oppfeed_llm_cache ----
    op.create_table(
        "oppfeed_llm_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cache_key", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("response_text", sa.String(length=50000), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_oppfeed_llm_cache_cache_key"), "oppfeed_llm_cache", ["cache_key"], unique=True)
    op.create_index(op.f("ix_oppfeed_llm_cache_expires_at"), "oppfeed_llm_cache", ["expires_at"], unique=False)

    # ---- oppfeed_llm_usage ----
    op.create_table(
        "oppfeed_llm_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("step_name", sa.String(length=100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("rate_limit_remaining", sa.Integer(), nullable=True),
        sa.Column("rate_limit_total", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_oppfeed_llm_usage_created_at"), "oppfeed_llm_usage", ["created_at"], unique=False)
    op.create_index(op.f("ix_oppfeed_llm_usage_run_id"), "oppfeed_llm_usage", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_oppfeed_llm_usage_run_id"), table_name="oppfeed_llm_usage")
    op.drop_index(op.f("ix_oppfeed_llm_usage_created_at"), table_name="oppfeed_llm_usage")
    op.drop_table("oppfeed_llm_usage")
    op.drop_index(op.f("ix_oppfeed_llm_cache_expires_at"), table_name="oppfeed_llm_cache")
    op.drop_index(op.f("ix_oppfeed_llm_cache_cache_key"), table_name="oppfeed_llm_cache")
    op.drop_table("oppfeed_llm_cache")
    op.drop_index(op.f("ix_oppfeed_feedback_opportunity_id"), table_name="oppfeed_feedback")
    op.drop_table("oppfeed_feedback")
    op.drop_index(op.f("ix_oppfeed_search_query_enabled"), table_name="oppfeed_search_query")
    op.drop_table("oppfeed_search_query")
    op.drop_index(op.f("ix_oppfeed_source_rule_domain"), table_name="oppfeed_source_rule")
    op.drop_table("oppfeed_source_rule")
    op.drop_table("oppfeed_agent_settings")
    op.drop_index(op.f("ix_oppfeed_run_step_status"), table_name="oppfeed_run_step")
    op.drop_index(op.f("ix_oppfeed_run_step_run_id"), table_name="oppfeed_run_step")
    op.drop_table("oppfeed_run_step")
    op.drop_index(op.f("ix_oppfeed_agent_run_run_id"), table_name="oppfeed_agent_run")
    op.drop_index(op.f("ix_oppfeed_agent_run_status"), table_name="oppfeed_agent_run")
    op.drop_index(op.f("ix_oppfeed_agent_run_started_at"), table_name="oppfeed_agent_run")
    op.drop_table("oppfeed_agent_run")
    op.drop_index(op.f("ix_oppfeed_opportunity_type"), table_name="oppfeed_opportunity")
    op.drop_index(op.f("ix_oppfeed_opportunity_status"), table_name="oppfeed_opportunity")
    op.drop_index(op.f("ix_oppfeed_opportunity_source_domain"), table_name="oppfeed_opportunity")
    op.drop_index(op.f("ix_oppfeed_opportunity_slug"), table_name="oppfeed_opportunity")
    op.drop_index(op.f("ix_oppfeed_opportunity_registration_deadline"), table_name="oppfeed_opportunity")
    op.drop_index(op.f("ix_oppfeed_opportunity_created_at"), table_name="oppfeed_opportunity")
    op.drop_table("oppfeed_opportunity")