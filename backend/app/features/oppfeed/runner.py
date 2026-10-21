"""
Run the OppFeed agent pipeline, and record what it did.

The pipeline has eight stages, and the admin watches them happen. So a run
has to be a record of the work, not a row that says "pending" for ever:
each stage gets a step row, the run's current stage moves with it, and the
counts at the end are the pipeline's own.

The agent package owns its tables and knows nothing about the web layer -
it must not, or it could not be imported on its own. So this module is the
seam between the two. It drives the stages, writes the progress into the
web layer's tables, and brings the drafts the agent saved across into the
opportunities the app reads.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlmodel import Session, select

from core.config import get_settings
from core.database import engine
from features.oppfeed.models import (
    AgentRun,
    AgentSettings,
    Opportunity,
    OpportunityStatus,
    OpportunityType,
    RunStatus,
    RunStep,
    StepStatus,
)

logger = logging.getLogger(__name__)

#: How long a stage's output is kept on the step row. The step's own output
#: can be large - a page of extracted fields - and the run detail screen
#: only shows a summary of it.
_OUTPUT_SUMMARY_KEYS = ("title", "organization_name", "url", "count", "found", "passed")


def pipeline_stage_count() -> int:
    """How many stages the pipeline has.

    The agent owns the list; this reads it from there when the agent can be
    imported, and falls back to the copy below when it cannot - a progress
    bar with the wrong denominator is worse than one that says nothing.
    """
    try:
        from features.oppfeed.agent.graph import AgentPipeline

        return len(AgentPipeline.STAGES)
    except Exception:  # noqa: BLE001 - the agent is optional
        return len(PIPELINE_STAGES)


#: A copy of the pipeline's stages, for when the agent cannot be imported.
PIPELINE_STAGES = (
    "plan_queries",
    "search",
    "filter_candidates",
    "trace_source",
    "fetch_extract",
    "verify",
    "generate_template",
    "save_draft",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _async_url() -> str:
    """The database URL, in the form the async engine wants."""
    url = get_settings().database_url
    if url.startswith("sqlite"):
        return url
    # psycopg3 serves both the sync and the async driver from one URL.
    return url


def _async_connect_args() -> Dict[str, Any]:
    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        return {}
    return {
        "connect_args": {
            "connect_timeout": settings.db_connect_timeout,
            "application_name": "campuspilot-oppfeed-agent",
            # The agent's tables are unqualified, so every connection must
            # start with the same search path as the rest of the app.
            "options": "-csearch_path=core,academic,social,telemetry,public",
        },
    }


# ---------------------------------------------------------------------------
# Starting a run
# ---------------------------------------------------------------------------

def start_run(run_id: str, mode: str = "manual") -> None:
    """
    Run the pipeline for a run, in the background.

    A thread, not an event-loop task: the pipeline searches the open web and
    takes minutes, and the admin's request that started it should return at
    once rather than hold the connection open.
    """
    thread = threading.Thread(
        target=_run_in_thread,
        args=(run_id, mode),
        daemon=True,
        name=f"oppfeed-{run_id[:8]}",
    )
    thread.start()


def _run_in_thread(run_id: str, mode: str) -> None:
    try:
        if sys.platform == "win32":
            # psycopg's async mode needs a selector loop, and Windows
            # defaults to the proactor, which cannot do it. The app's own
            # loop is untouched: this one belongs to this thread.
            loop = asyncio.SelectorEventLoop()
            try:
                asyncio.set_event_loop(loop)
                loop.run_until_complete(_execute(run_id, mode))
            finally:
                asyncio.set_event_loop(None)
                loop.close()
        else:
            asyncio.run(_execute(run_id, mode))
    except Exception as exc:  # noqa: BLE001 - a thread must not die silently
        logger.exception("OppFeed run %s could not be completed", run_id)
        _fail(run_id, exc)


# ---------------------------------------------------------------------------
# The run itself
# ---------------------------------------------------------------------------

async def _execute(run_id: str, mode: str) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlmodel.ext.asyncio.session import AsyncSession

    from features.oppfeed.agent.base import agent_registry
    from features.oppfeed.agent.graph import AgentPipeline
    from features.oppfeed.agent.llm.router import LLMRouter
    from features.oppfeed.agent.schemas.pipeline import PipelineState

    async_engine = create_async_engine(_async_url(), **_async_connect_args())
    try:
        # The agent's own tables. The ones this app already has are left
        # alone; the table it saves its drafts in is not.
        async with async_engine.begin() as conn:
            await conn.run_sync(agent_registry.metadata.create_all, checkfirst=True)

        router = LLMRouter()
        chain = _provider_chain()
        if chain:
            router.set_chain(chain)

        pipeline = AgentPipeline(router)
        state = PipelineState(
            run_id=run_id,
            mode=mode,
            current_stage="init",
            max_drafts=_max_drafts(),
        )

        _mark_running(run_id)
        async with AsyncSession(async_engine) as adb:
            for stage in AgentPipeline.STAGES:
                _begin_step(run_id, stage)
                started = _now()
                try:
                    state = await pipeline.run_stage(stage, state, adb)
                except Exception as exc:  # noqa: BLE001 - recorded, then re-raised
                    _finish_step(
                        run_id,
                        stage,
                        StepStatus.FAILED,
                        error=str(exc),
                        duration_ms=_elapsed_ms(started),
                    )
                    raise
                _finish_step(
                    run_id,
                    stage,
                    StepStatus.COMPLETED,
                    output=_summarise(state, stage),
                    duration_ms=_elapsed_ms(started),
                )
                _set_stage(run_id, stage)

        drafted = _bring_drafts_across(run_id)
        published = _publish(run_id)
        _complete(run_id, state, drafted, published=published)
    finally:
        await async_engine.dispose()


def _elapsed_ms(started: datetime) -> int:
    return int((_now() - started).total_seconds() * 1000)


def _summarise(state: Any, stage: str) -> Dict[str, Any]:
    """What a step row keeps of its stage: enough to read, not the whole page."""
    summary: Dict[str, Any] = {"stage": stage}
    if stage == "plan_queries":
        summary["queries"] = len(getattr(state, "queries", []) or [])
    elif stage == "search":
        summary["results"] = len(getattr(state, "search_results", []) or [])
    elif stage == "filter_candidates":
        summary["candidates"] = len(getattr(state, "candidates", []) or [])
    elif stage == "verify":
        summary["verified"] = len(getattr(state, "verification_result", []) or [])
        summary["summary"] = dict(getattr(state, "verification_summary", {}) or {})
    elif stage == "save_draft":
        summary["drafted"] = int(getattr(state, "opportunities_drafted", 0) or 0)
    return summary


def _provider_chain() -> List[str]:
    """The chain of providers the settings ask for, in order."""
    with Session(engine) as s:
        settings = s.exec(select(AgentSettings)).first()
    if settings is None or not settings.llm_provider_chain:
        return []
    return [
        name.strip()
        for name in settings.llm_provider_chain.split(",")
        if name.strip()
    ]


# ---------------------------------------------------------------------------
# The progress, in the web layer's tables
# ---------------------------------------------------------------------------

def _mark_running(run_id: str) -> None:
    with Session(engine) as s:
        run = s.exec(select(AgentRun).where(AgentRun.run_id == run_id)).first()
        if run is None:
            return
        run.status = RunStatus.RUNNING
        run.started_at = run.started_at or _now()
        run.current_stage = "starting"
        s.add(run)
        s.commit()


def _set_stage(run_id: str, stage: str) -> None:
    with Session(engine) as s:
        run = s.exec(select(AgentRun).where(AgentRun.run_id == run_id)).first()
        if run is None:
            return
        run.current_stage = stage
        s.add(run)
        s.commit()


def _begin_step(run_id: str, stage: str) -> None:
    with Session(engine) as s:
        s.add(
            RunStep(
                run_id=run_id,
                step_name=stage,
                status=StepStatus.RUNNING,
                started_at=_now(),
            )
        )
        s.commit()


def _finish_step(
    run_id: str,
    stage: str,
    status: StepStatus,
    output: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    with Session(engine) as s:
        step = s.exec(
            select(RunStep)
            .where(RunStep.run_id == run_id, RunStep.step_name == stage)
            .order_by(RunStep.id.desc())
        ).first()
        if step is None:
            step = RunStep(run_id=run_id, step_name=stage)
        step.status = status
        step.completed_at = _now()
        step.duration_ms = duration_ms
        if output is not None:
            step.output_data = output
        if error:
            step.error_message = error[:2000]
        s.add(step)
        s.commit()


def _max_drafts() -> int:
    """How many drafts a run may write, as the settings say."""
    with Session(engine) as s:
        settings = s.exec(select(AgentSettings)).first()
    if settings is None:
        return 100
    return max(0, int(settings.max_drafts_per_run or 0))


def _publish(run_id: str) -> int:
    """
    Publish the run's drafts, when the settings say to.

    The auto-publish switch exists to say "verified work goes to the
    students' feed without a human in the loop". Wiring it to the run is
    what makes it that, rather than a field nobody reads.
    """
    from features.oppfeed.services.publishing_service import PublishingService

    try:
        with Session(engine) as s:
            published = PublishingService.process_auto_publish(s, run_id=run_id)
        return len(published)
    except Exception as exc:  # noqa: BLE001 - publishing must not lose the run
        logger.warning("OppFeed run %s could not publish: %s", run_id, exc)
        return 0


def _complete(run_id: str, state: Any, drafted: int, published: int = 0) -> None:
    """The run is done: the counts are the pipeline's own."""
    found = len(getattr(state, "candidates", []) or [])
    verified = len(getattr(state, "verification_result", []) or [])
    with Session(engine) as s:
        run = s.exec(select(AgentRun).where(AgentRun.run_id == run_id)).first()
        if run is None:
            return
        run.status = RunStatus.COMPLETED
        run.completed_at = _now()
        run.current_stage = "done"
        run.opportunities_found = found
        run.opportunities_verified = verified
        run.opportunities_rejected = max(0, found - verified)
        run.opportunities_drafted = drafted
        run.opportunities_published = published
        run.llm_calls = int(getattr(state, "llm_calls", 0) or 0)
        run.llm_tokens = int(getattr(state, "llm_tokens", 0) or 0)
        run.checkpoint = _checkpoint(state)
        errors = list(getattr(state, "errors", []) or [])
        # Say why nothing was published. A run that found work and published
        # none, with no explanation, reads as a broken switch.
        note = _publishing_note(run_id, drafted, published)
        if note:
            errors.append({"stage": "publish", "error": note})
        if errors:
            run.errors = {"errors": errors}
        s.add(run)
        s.commit()


def _publishing_note(run_id: str, drafted: int, published: int) -> str:
    """Why a run's drafts were not published, when that is the case."""
    if drafted == 0 or published > 0:
        return ""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT count(*) FROM core.oppfeed_opportunity "
                "WHERE created_by_run_id = :run_id AND (llm_provider IS NULL "
                "OR lower(llm_provider) <> 'mock')"
            ),
            {"run_id": run_id},
        ).first()
    if row and row[0]:
        # Real extractions were written but did not meet the publish
        # criteria - the confidence threshold, most likely.
        return (
            f"{drafted} draft(s) were written but none met the auto-publish "
            "criteria (the confidence threshold, most likely)."
        )
    return (
        f"{drafted} draft(s) were written but none were published: the run "
        "used the mock provider, which stands in for an LLM that is not "
        "there, so its extractions are placeholders and must not reach the "
        "students' feed."
    )


def _fail(run_id: str, exc: Exception) -> None:
    with Session(engine) as s:
        run = s.exec(select(AgentRun).where(AgentRun.run_id == run_id)).first()
        if run is None:
            return
        run.status = RunStatus.FAILED
        run.completed_at = _now()
        run.errors = {"error": str(exc)}
        s.add(run)
        s.commit()


def _checkpoint(state: Any) -> Optional[Dict[str, Any]]:
    """The pipeline's own checkpoint, small enough to keep."""
    try:
        checkpoint = state.to_checkpoint()
    except Exception:  # noqa: BLE001 - a checkpoint is a nicety, not a must
        return None
    if not isinstance(checkpoint, dict):
        return None
    keep = ("run_id", "mode", "current_stage", "stages_completed", "confidence_score")
    return {key: checkpoint.get(key) for key in keep if key in checkpoint}


# ---------------------------------------------------------------------------
# The drafts the agent saved, brought across
# ---------------------------------------------------------------------------

def _bring_drafts_across(run_id: str) -> int:
    """
    The agent saves its drafts in its own table; the app reads the
    opportunities. This is the seam between the two.

    Only the drafts this run made are considered, and a draft whose slug the
    app already knows is left alone: the same opportunity found twice is one
    opportunity, not two.
    """
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT slug, title, organization_name, opportunity_type, "
                    "short_summary, full_description, location, work_mode, "
                    "duration, start_date, stipend_min, stipend_max, "
                    "stipend_currency, stipend_period, registration_deadline, "
                    "deadline_type, education_levels, allowed_branches, "
                    "graduation_years, min_cgpa_or_percentage, other_criteria, "
                    "skills_required, perks_benefits, selection_process, "
                    "documents_required, how_to_apply, apply_url, "
                    "secondary_sources, contact_email, source_domain, "
                    "verification_report, confidence_score, field_evidence, "
                    "llm_provider, llm_model, prompt_version, tags "
                    "FROM oppfeed_opportunity_draft "
                    "WHERE created_by_run_id = :run_id"
                ),
                {"run_id": run_id},
            ).mappings().all()
    except Exception as exc:  # noqa: BLE001 - the table may not exist yet
        logger.warning("Could not read the agent's drafts: %s", exc)
        return 0

    if not rows:
        return 0

    created = 0
    with Session(engine) as s:
        for row in rows:
            slug = (row.get("slug") or "").strip()
            title = (row.get("title") or "").strip()
            if not slug or not title:
                continue
            existing = s.exec(
                select(Opportunity).where(Opportunity.slug == slug)
            ).first()
            if existing is not None:
                continue
            s.add(
                Opportunity(
                    slug=slug,
                    status=OpportunityStatus.DRAFT,
                    title=title[:500],
                    organization_name=(row.get("organization_name") or "")[:200],
                    opportunity_type=_opportunity_type(row.get("opportunity_type")),
                    short_summary=row.get("short_summary"),
                    full_description=row.get("full_description"),
                    location=row.get("location"),
                    work_mode=row.get("work_mode"),
                    duration=row.get("duration"),
                    start_date=row.get("start_date"),
                    stipend_min=row.get("stipend_min"),
                    stipend_max=row.get("stipend_max"),
                    stipend_currency=(row.get("stipend_currency") or "INR")[:10],
                    stipend_period=row.get("stipend_period"),
                    registration_deadline=row.get("registration_deadline"),
                    deadline_type=row.get("deadline_type") or "fixed",
                    education_levels=list(row.get("education_levels") or []),
                    allowed_branches=list(row.get("allowed_branches") or []),
                    graduation_years=list(row.get("graduation_years") or []),
                    min_cgpa_or_percentage=row.get("min_cgpa_or_percentage"),
                    other_criteria=row.get("other_criteria"),
                    skills_required=list(row.get("skills_required") or []),
                    perks_benefits=list(row.get("perks_benefits") or []),
                    selection_process=row.get("selection_process"),
                    documents_required=list(row.get("documents_required") or []),
                    how_to_apply=row.get("how_to_apply"),
                    apply_url=row.get("apply_url"),
                    secondary_sources=list(row.get("secondary_sources") or []),
                    contact_email=row.get("contact_email"),
                    source_domain=row.get("source_domain"),
                    verification_report=row.get("verification_report"),
                    confidence_score=row.get("confidence_score") or 0.0,
                    field_evidence=dict(row.get("field_evidence") or {}),
                    llm_provider=row.get("llm_provider"),
                    llm_model=row.get("llm_model"),
                    prompt_version=row.get("prompt_version"),
                    tags=list(row.get("tags") or []),
                    created_by_run_id=run_id,
                )
            )
            created += 1
        s.commit()
    logger.info("OppFeed run %s brought %s draft(s) across", run_id, created)
    return created


def _opportunity_type(value: Any) -> OpportunityType:
    """The app's own enum, or the safe default."""
    try:
        return OpportunityType(str(value or "Internship").strip() or "Internship")
    except (ValueError, TypeError):
        return OpportunityType.INTERNSHIP
