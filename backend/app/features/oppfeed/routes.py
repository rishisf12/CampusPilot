"""OppFeed API routes — CampusPilot integration.

Admin endpoints: /admin/oppfeed/*  (require admin role)
Faculty endpoints: /faculty/oppfeed/*  (require authenticated user)
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, delete, select

from core.database import get_session
from core.deps import get_current_admin, get_current_user
from models import User
from .models import (
    Opportunity,
    AgentRun,
    RunStep,
    AgentSettings,
    SourceRule,
    SearchQuery,
    OppFeedFeedback,
    OpportunityStatus,
    RunStatus,
    StepStatus,
)
from .schemas import (
    OpportunityCard,
    OpportunityDetail,
    FeedFilters,
    PaginatedOpportunities,
    OpportunityListItem,
    OpportunityDetailAdmin,
    OpportunityUpdateRequest,
    BulkActionRequest,
    StateTransitionRequest,
    RunResponse,
    RunListItem,
    RunStepResponse,
    RunCreateRequest,
    AgentSettingsResponse,
    AgentSettingsUpdateRequest,
    SourceRuleResponse,
    SourceRuleCreateRequest,
    SourceRuleUpdateRequest,
    SearchQueryResponse,
    SearchQueryCreateRequest,
    SearchQueryUpdateRequest,
    LLMStatusResponse,
    LLMTestRequest,
    LLMTestResponse,
    FeedbackResponse,
    FeedbackCreateRequest,
    OpportunityFilterParams,
    RunFilterParams,
    PaginationParams,
)

# NOTE: the agent package is imported lazily, inside the handler that needs it.
# Importing it at module level would pull in the scraping stack
# (trafilatura -> justext -> lxml.html.clean), and a missing optional scraping
# library must not stop the whole API from booting — the agent is off by
# default (ENABLE_AGENT=false) and is only needed when a run is triggered.

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

admin_router = APIRouter(prefix="/admin/oppfeed", tags=["Admin - OppFeed"])
faculty_router = APIRouter(prefix="/faculty/oppfeed", tags=["Faculty - OppFeed"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_card(opp: Opportunity) -> OpportunityCard:
    """Convert Opportunity model to OpportunityCard for feed."""
    days_left = None
    if opp.registration_deadline:
        # The column is timezone-aware, so the "now" it is compared against must
        # be too: subtracting a naive local time from an aware UTC value raises
        # TypeError, which surfaced as a 500 on the whole faculty feed.
        delta = opp.registration_deadline - datetime.now(timezone.utc)
        days_left = max(0, delta.days)
    return OpportunityCard(
        slug=opp.slug,
        title=opp.title,
        organization_name=opp.organization_name,
        organization_logo_url=opp.organization_logo_url,
        opportunity_type=opp.opportunity_type.value,
        location=opp.location,
        work_mode=opp.work_mode.value if opp.work_mode else None,
        stipend_min=opp.stipend_min,
        stipend_max=opp.stipend_max,
        stipend_currency=opp.stipend_currency,
        stipend_period=opp.stipend_period,
        registration_deadline=opp.registration_deadline,
        deadline_type=opp.deadline_type.value,
        short_summary=opp.short_summary,
        eligibility_summary=_eligibility_summary(opp),
        skills_required=opp.skills_required or [],
        tags=opp.tags or [],
        apply_url=opp.apply_url,
        days_until_deadline=days_left,
    )


def _eligibility_summary(opp: Opportunity) -> Optional[str]:
    parts = []
    if opp.education_levels:
        parts.append(f"Education: {', '.join(opp.education_levels)}")
    if opp.allowed_branches:
        parts.append(f"Branches: {', '.join(opp.allowed_branches)}")
    if opp.graduation_years:
        years = ', '.join(str(y) for y in sorted(opp.graduation_years))
        parts.append(f"Graduation: {years}")
    return '; '.join(parts) if parts else None


def _to_detail(opp: Opportunity) -> OpportunityDetail:
    """Convert Opportunity model to OpportunityDetail for faculty view."""
    days_left = None
    if opp.registration_deadline:
        delta = opp.registration_deadline - datetime.now(timezone.utc)
        days_left = max(0, delta.days)
    return OpportunityDetail(
        slug=opp.slug,
        title=opp.title,
        organization_name=opp.organization_name,
        organization_logo_url=opp.organization_logo_url,
        banner_url=opp.banner_url,
        opportunity_type=opp.opportunity_type.value,
        short_summary=opp.short_summary,
        full_description=opp.full_description,
        location=opp.location,
        work_mode=opp.work_mode.value if opp.work_mode else None,
        duration=opp.duration,
        start_date=opp.start_date,
        stipend_min=opp.stipend_min,
        stipend_max=opp.stipend_max,
        stipend_currency=opp.stipend_currency,
        stipend_period=opp.stipend_period,
        stipend_notes=opp.stipend_notes,
        registration_start_date=opp.registration_start_date,
        registration_deadline=opp.registration_deadline,
        deadline_type=opp.deadline_type.value,
        education_levels=opp.education_levels or [],
        allowed_branches=opp.allowed_branches or [],
        graduation_years=opp.graduation_years or [],
        min_cgpa_or_percentage=opp.min_cgpa_or_percentage,
        other_criteria=opp.other_criteria,
        open_to_countries=opp.open_to_countries or [],
        skills_required=opp.skills_required or [],
        perks_benefits=opp.perks_benefits or [],
        selection_process=opp.selection_process,
        documents_required=opp.documents_required or [],
        how_to_apply=opp.how_to_apply,
        apply_url=opp.apply_url,
        secondary_sources=opp.secondary_sources or [],
        contact_email=opp.contact_email,
        tags=opp.tags or [],
        attachments=opp.attachments or [],
        published_at=opp.published_at,
        days_until_deadline=days_left,
    )


def _to_detail_admin(opp: Opportunity) -> OpportunityDetailAdmin:
    """Convert Opportunity model to admin detail view."""
    return OpportunityDetailAdmin(
        id=opp.id,
        slug=opp.slug,
        title=opp.title,
        organization_name=opp.organization_name,
        organization_logo_url=opp.organization_logo_url,
        banner_url=opp.banner_url,
        opportunity_type=opp.opportunity_type.value,
        status=opp.status.value,
        short_summary=opp.short_summary,
        full_description=opp.full_description,
        location=opp.location,
        work_mode=opp.work_mode.value if opp.work_mode else None,
        duration=opp.duration,
        start_date=opp.start_date,
        stipend_min=opp.stipend_min,
        stipend_max=opp.stipend_max,
        stipend_currency=opp.stipend_currency,
        stipend_period=opp.stipend_period,
        stipend_notes=opp.stipend_notes,
        registration_start_date=opp.registration_start_date,
        registration_deadline=opp.registration_deadline,
        deadline_type=opp.deadline_type.value,
        education_levels=opp.education_levels or [],
        allowed_branches=opp.allowed_branches or [],
        graduation_years=opp.graduation_years or [],
        min_cgpa_or_percentage=opp.min_cgpa_or_percentage,
        other_criteria=opp.other_criteria,
        open_to_countries=opp.open_to_countries or [],
        skills_required=opp.skills_required or [],
        perks_benefits=opp.perks_benefits or [],
        selection_process=opp.selection_process,
        documents_required=opp.documents_required or [],
        how_to_apply=opp.how_to_apply,
        apply_url=opp.apply_url,
        secondary_sources=opp.secondary_sources or [],
        attachments=opp.attachments or [],
        contact_email=opp.contact_email,
        source_domain=opp.source_domain,
        verified_at=opp.verified_at,
        verification_report=opp.verification_report,
        confidence_score=opp.confidence_score,
        field_evidence=opp.field_evidence,
        llm_provider=opp.llm_provider,
        llm_model=opp.llm_model,
        prompt_version=opp.prompt_version,
        tags=opp.tags or [],
        version=opp.version,
        created_by_run_id=opp.created_by_run_id,
        created_at=opp.created_at,
        updated_at=opp.updated_at,
        published_at=opp.published_at,
        scheduled_publish_at=opp.scheduled_publish_at,
    )


def _to_list_item(opp: Opportunity) -> OpportunityListItem:
    return OpportunityListItem(
        id=opp.id,
        slug=opp.slug,
        title=opp.title,
        organization_name=opp.organization_name,
        opportunity_type=opp.opportunity_type.value,
        status=opp.status.value,
        confidence_score=opp.confidence_score,
        source_domain=opp.source_domain,
        created_at=opp.created_at,
        updated_at=opp.updated_at,
    )


# ---------------------------------------------------------------------------
# Faculty Feed Endpoints
# ---------------------------------------------------------------------------

@faculty_router.get("", response_model=PaginatedOpportunities)
async def list_opportunities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    opportunity_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    work_mode: Optional[str] = Query(None),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """List published opportunities for faculty/student feed."""
    stmt = select(Opportunity).where(Opportunity.status == OpportunityStatus.PUBLISHED)

    if opportunity_type:
        try:
            stmt = stmt.where(Opportunity.opportunity_type == opportunity_type)
        except ValueError:
            pass
    if location:
        stmt = stmt.where(Opportunity.location.ilike(f"%{location}%"))
    if work_mode:
        try:
            stmt = stmt.where(Opportunity.work_mode == work_mode)
        except ValueError:
            pass
    if search:
        stmt = stmt.where(
            Opportunity.title.ilike(f"%{search}%") |
            Opportunity.organization_name.ilike(f"%{search}%")
        )

    # Order by most recent published first
    stmt = stmt.order_by(Opportunity.published_at.desc().nullslast(), Opportunity.created_at.desc())

    # Count total
    total = len(session.exec(stmt).all())

    # Paginate
    offset = (page - 1) * page_size
    items = session.exec(stmt.offset(offset).limit(page_size)).all()

    cards = [_to_card(o) for o in items]
    return PaginatedOpportunities(
        items=cards,
        total=total,
        page=page,
        page_size=page_size,
        has_more=offset + page_size < total,
    )


@faculty_router.get("/filters", response_model=FeedFilters)
async def get_feed_filters(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Get available filter values for the feed."""
    opps = session.exec(
        select(Opportunity).where(Opportunity.status == OpportunityStatus.PUBLISHED)
    ).all()

    types = sorted({o.opportunity_type.value for o in opps})
    locations = sorted({o.location for o in opps if o.location})
    work_modes = sorted({o.work_mode.value for o in opps if o.work_mode})

    edu_levels = set()
    branches = set()
    grad_years = set()
    skills = set()
    for o in opps:
        edu_levels.update(o.education_levels or [])
        branches.update(o.allowed_branches or [])
        grad_years.update(o.graduation_years or [])
        skills.update(o.skills_required or [])

    return FeedFilters(
        opportunity_types=types,
        locations=locations,
        work_modes=work_modes,
        education_levels=sorted(edu_levels),
        allowed_branches=sorted(branches),
        graduation_years=sorted(grad_years),
        skills=sorted(skills),
    )


@faculty_router.get("/{slug}", response_model=OpportunityDetail)
async def get_opportunity(
    slug: str,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Get full opportunity detail by slug."""
    opp = session.exec(
        select(Opportunity).where(
            Opportunity.slug == slug,
            Opportunity.status == OpportunityStatus.PUBLISHED,
        )
    ).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return _to_detail(opp)


# ---------------------------------------------------------------------------
# Admin: Opportunities Management
# ---------------------------------------------------------------------------

@admin_router.get("/opportunities", response_model=List[OpportunityListItem])
async def admin_list_opportunities(
    status: Optional[str] = Query(None),
    opportunity_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    source_domain: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """List all opportunities for admin management."""
    stmt = select(Opportunity)

    if status:
        try:
            stmt = stmt.where(Opportunity.status == status)
        except ValueError:
            pass
    if opportunity_type:
        try:
            stmt = stmt.where(Opportunity.opportunity_type == opportunity_type)
        except ValueError:
            pass
    if search:
        stmt = stmt.where(
            Opportunity.title.ilike(f"%{search}%") |
            Opportunity.organization_name.ilike(f"%{search}%") |
            Opportunity.slug.ilike(f"%{search}%")
        )
    if source_domain:
        stmt = stmt.where(Opportunity.source_domain.ilike(f"%{source_domain}%"))

    stmt = stmt.order_by(Opportunity.created_at.desc().nullslast())
    offset = (page - 1) * page_size
    items = session.exec(stmt.offset(offset).limit(page_size)).all()

    return [_to_list_item(o) for o in items]


@admin_router.get("/opportunities/{opp_id}", response_model=OpportunityDetailAdmin)
async def admin_get_opportunity(
    opp_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """Get full opportunity detail for admin."""
    opp = session.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return _to_detail_admin(opp)


@admin_router.patch("/opportunities/{opp_id}", response_model=OpportunityDetailAdmin)
async def admin_update_opportunity(
    opp_id: int,
    payload: OpportunityUpdateRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """Update an opportunity (admin)."""
    opp = session.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        if hasattr(opp, field):
            setattr(opp, field, value)

    opp.updated_at = datetime.now(timezone.utc)
    session.add(opp)
    session.commit()
    session.refresh(opp)
    return _to_detail_admin(opp)


@admin_router.post("/opportunities/bulk", status_code=status.HTTP_200_OK)
async def admin_bulk_action(
    payload: BulkActionRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """Bulk action on opportunities."""
    opps = session.exec(
        select(Opportunity).where(Opportunity.id.in_(payload.ids))
    ).all()

    if len(opps) != len(payload.ids):
        raise HTTPException(status_code=404, detail="Some opportunities not found")

    action = payload.action
    for opp in opps:
        if action == "approve":
            opp.status = OpportunityStatus.APPROVED
        elif action == "reject":
            opp.status = OpportunityStatus.REJECTED
        elif action == "publish":
            if opp.status != OpportunityStatus.APPROVED:
                raise HTTPException(
                    status_code=400,
                    detail=f"Opportunity {opp.id} must be approved before publishing",
                )
            opp.status = OpportunityStatus.PUBLISHED
            opp.published_at = datetime.now(timezone.utc)
        elif action == "schedule":
            if not payload.scheduled_publish_at:
                raise HTTPException(status_code=400, detail="scheduled_publish_at required")
            opp.status = OpportunityStatus.SCHEDULED
            opp.scheduled_publish_at = payload.scheduled_publish_at
        elif action == "archive":
            opp.status = OpportunityStatus.ARCHIVED
        elif action == "delete":
            session.delete(opp)
            continue
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

        opp.updated_at = datetime.now(timezone.utc)
        session.add(opp)

    session.commit()
    return {"processed": len(opps), "action": action}


@admin_router.post("/opportunities/{opp_id}/transition", response_model=OpportunityDetailAdmin)
async def admin_transition_state(
    opp_id: int,
    payload: StateTransitionRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """Transition opportunity through workflow states."""
    opp = session.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    action = payload.action
    if action == "approve":
        if opp.status not in (OpportunityStatus.DRAFT, OpportunityStatus.IN_REVIEW):
            raise HTTPException(status_code=400, detail="Only draft/in_review can be approved")
        opp.status = OpportunityStatus.APPROVED
    elif action == "reject":
        opp.status = OpportunityStatus.REJECTED
    elif action == "publish":
        if opp.status != OpportunityStatus.APPROVED:
            raise HTTPException(status_code=400, detail="Must be approved before publishing")
        opp.status = OpportunityStatus.PUBLISHED
        opp.published_at = datetime.now(timezone.utc)
    elif action == "schedule":
        if not payload.scheduled_publish_at:
            raise HTTPException(status_code=400, detail="scheduled_publish_at required")
        opp.status = OpportunityStatus.SCHEDULED
        opp.scheduled_publish_at = payload.scheduled_publish_at
    elif action == "archive":
        opp.status = OpportunityStatus.ARCHIVED
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    opp.updated_at = datetime.now(timezone.utc)
    session.add(opp)
    session.commit()
    session.refresh(opp)
    return _to_detail_admin(opp)


# ---------------------------------------------------------------------------
# Admin: Agent Runs
# ---------------------------------------------------------------------------

@admin_router.get("/runs", response_model=List[RunListItem])
async def admin_list_runs(
    status: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """List agent runs."""
    stmt = select(AgentRun)

    if status:
        try:
            stmt = stmt.where(AgentRun.status == status)
        except ValueError:
            pass
    if mode:
        stmt = stmt.where(AgentRun.mode == mode)

    stmt = stmt.order_by(AgentRun.created_at.desc().nullslast())
    offset = (page - 1) * page_size
    items = session.exec(stmt.offset(offset).limit(page_size)).all()

    from features.oppfeed.runner import pipeline_stage_count

    # How far each run has got, counted in stages: the progress bar is the
    # pipeline's own stages, not a number the UI made up.
    steps_by_run: Dict[str, List[RunStep]] = {}
    if items:
        run_ids = [r.run_id for r in items]
        steps = session.exec(
            select(RunStep).where(RunStep.run_id.in_(run_ids))
        ).all()
        for step in steps:
            steps_by_run.setdefault(step.run_id, []).append(step)

    total_stages = pipeline_stage_count()
    return [
        RunListItem(
            run_id=r.run_id,
            status=r.status.value,
            mode=r.mode,
            started_at=r.started_at,
            completed_at=r.completed_at,
            opportunities_found=r.opportunities_found,
            opportunities_verified=r.opportunities_verified,
            opportunities_rejected=r.opportunities_rejected,
            opportunities_drafted=r.opportunities_drafted,
            opportunities_published=r.opportunities_published,
            current_stage=r.current_stage,
            stages_completed=sum(
                1
                for step in steps_by_run.get(r.run_id, [])
                if step.status == StepStatus.COMPLETED
            ),
            total_stages=total_stages,
        )
        for r in items
    ]


@admin_router.post("/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_run(
    payload: RunCreateRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """
    Trigger a manual agent run.

    The run is started, not simulated: the pipeline runs in the background
    and the run row records what it did, stage by stage, so the admin can
    watch it work. The response carries the run as it stands now - the
    detail endpoint is where the progress is read from.
    """
    import uuid

    from features.oppfeed.runner import start_run

    settings = session.exec(select(AgentSettings)).first()
    if settings is not None and not settings.enable_agent:
        raise HTTPException(
            status_code=400,
            detail="The agent is disabled. Turn it on in Agent Settings first.",
        )

    run = AgentRun(
        run_id=str(uuid.uuid4()),
        status=RunStatus.PENDING,
        mode=payload.mode,
        started_at=datetime.now(timezone.utc),
    )
    session.add(run)
    session.commit()

    # The pipeline runs in the background: it searches the open web and takes
    # minutes, and the admin's request should return at once.
    start_run(run.run_id, mode=payload.mode)

    return RunResponse(
        run_id=run.run_id,
        status=run.status.value,
        mode=run.mode,
        started_at=run.started_at,
        completed_at=run.completed_at,
        current_stage=run.current_stage,
    )


@admin_router.get("/runs/{run_id}", response_model=RunResponse)
async def admin_get_run(
    run_id: str,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """Get full run detail with steps."""
    run = session.exec(
        select(AgentRun).where(AgentRun.run_id == run_id)
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    steps = session.exec(
        select(RunStep).where(RunStep.run_id == run_id)
    ).all()

    return RunResponse(
        run_id=run.run_id,
        status=run.status.value,
        mode=run.mode,
        started_at=run.started_at,
        completed_at=run.completed_at,
        opportunities_found=run.opportunities_found,
        opportunities_verified=run.opportunities_verified,
        opportunities_rejected=run.opportunities_rejected,
        opportunities_drafted=run.opportunities_drafted,
        opportunities_published=run.opportunities_published,
        errors=list(run.errors.keys()) if run.errors else None,
        llm_calls=run.llm_calls,
        llm_tokens=run.llm_tokens,
        current_stage=run.current_stage,
        steps=[
            RunStepResponse(
                step_name=s.step_name,
                status=s.status.value,
                started_at=s.started_at,
                completed_at=s.completed_at,
                duration_ms=s.duration_ms,
                output_data=s.output_data,
                error_message=s.error_message,
                llm_provider=s.llm_provider,
                llm_model=s.llm_model,
            )
            for s in steps
        ],
    )


# ---------------------------------------------------------------------------
# Admin: Agent Settings
# ---------------------------------------------------------------------------

@admin_router.get("/settings", response_model=AgentSettingsResponse)
async def admin_get_settings(
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """Get current agent settings."""
    settings = session.exec(select(AgentSettings)).first()
    if not settings:
        # Create default
        settings = AgentSettings()
        session.add(settings)
        session.commit()
        session.refresh(settings)

    return AgentSettingsResponse(
        run_window_start=settings.run_window_start,
        run_window_end=settings.run_window_end,
        auto_publish_enabled=settings.auto_publish_enabled,
        auto_publish_threshold=settings.auto_publish_threshold,
        llm_provider_chain=settings.llm_provider_chain,
        llm_max_rpm=settings.llm_max_rpm,
        enable_agent=settings.enable_agent,
        enable_scheduler=settings.enable_scheduler,
        enable_vision=settings.enable_vision,
        enable_banner_gen=settings.enable_banner_gen,
        enable_audio_summary=settings.enable_audio_summary,
    )


@admin_router.patch("/settings", response_model=AgentSettingsResponse)
async def admin_update_settings(
    payload: AgentSettingsUpdateRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """Update agent settings."""
    settings = session.exec(select(AgentSettings)).first()
    if not settings:
        settings = AgentSettings()
        session.add(settings)

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        if hasattr(settings, field):
            setattr(settings, field, value)

    settings.updated_at = datetime.now(timezone.utc)
    session.add(settings)
    session.commit()
    session.refresh(settings)

    return AgentSettingsResponse(
        run_window_start=settings.run_window_start,
        run_window_end=settings.run_window_end,
        auto_publish_enabled=settings.auto_publish_enabled,
        auto_publish_threshold=settings.auto_publish_threshold,
        llm_provider_chain=settings.llm_provider_chain,
        llm_max_rpm=settings.llm_max_rpm,
        enable_agent=settings.enable_agent,
        enable_scheduler=settings.enable_scheduler,
        enable_vision=settings.enable_vision,
        enable_banner_gen=settings.enable_banner_gen,
        enable_audio_summary=settings.enable_audio_summary,
    )


# ---------------------------------------------------------------------------
# Admin: Source Rules
# ---------------------------------------------------------------------------

@admin_router.get("/source-rules", response_model=List[SourceRuleResponse])
async def admin_list_source_rules(
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """List all source rules."""
    rules = session.exec(select(SourceRule).order_by(SourceRule.domain)).all()
    return [
        SourceRuleResponse(
            id=r.id,
            domain=r.domain,
            rule_type=r.rule_type,
            enabled=r.enabled,
            description=r.description,
            created_at=r.created_at,
        )
        for r in rules
    ]


@admin_router.post("/source-rules", response_model=SourceRuleResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_source_rule(
    payload: SourceRuleCreateRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """Create a source rule."""
    rule = SourceRule(
        domain=payload.domain,
        rule_type=payload.rule_type,
        enabled=payload.enabled,
        description=payload.description,
    )
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return SourceRuleResponse(
        id=rule.id,
        domain=rule.domain,
        rule_type=rule.rule_type,
        enabled=rule.enabled,
        description=rule.description,
        created_at=rule.created_at,
    )


@admin_router.patch("/source-rules/{rule_id}", response_model=SourceRuleResponse)
async def admin_update_source_rule(
    rule_id: int,
    payload: SourceRuleUpdateRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """Update a source rule."""
    rule = session.get(SourceRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Source rule not found")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        if hasattr(rule, field):
            setattr(rule, field, value)

    session.add(rule)
    session.commit()
    session.refresh(rule)
    return SourceRuleResponse(
        id=rule.id,
        domain=rule.domain,
        rule_type=rule.rule_type,
        enabled=rule.enabled,
        description=rule.description,
        created_at=rule.created_at,
    )


@admin_router.delete("/source-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_source_rule(
    rule_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """Delete a source rule."""
    rule = session.get(SourceRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Source rule not found")
    session.delete(rule)
    session.commit()


# ---------------------------------------------------------------------------
# Admin: Search Queries
# ---------------------------------------------------------------------------

@admin_router.get("/search-queries", response_model=List[SearchQueryResponse])
async def admin_list_search_queries(
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """List all search queries."""
    queries = session.exec(select(SearchQuery).order_by(SearchQuery.priority.desc())).all()
    return [
        SearchQueryResponse(
            id=q.id,
            query=q.query,
            category=q.category,
            enabled=q.enabled,
            is_seed=q.is_seed,
            priority=q.priority,
            created_at=q.created_at,
        )
        for q in queries
    ]


@admin_router.post("/search-queries", response_model=SearchQueryResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_search_query(
    payload: SearchQueryCreateRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """Create a search query."""
    query = SearchQuery(
        query=payload.query,
        category=payload.category,
        enabled=payload.enabled,
        is_seed=payload.is_seed,
        priority=payload.priority,
    )
    session.add(query)
    session.commit()
    session.refresh(query)
    return SearchQueryResponse(
        id=query.id,
        query=query.query,
        category=query.category,
        enabled=query.enabled,
        is_seed=query.is_seed,
        priority=query.priority,
        created_at=query.created_at,
    )


@admin_router.patch("/search-queries/{query_id}", response_model=SearchQueryResponse)
async def admin_update_search_query(
    query_id: int,
    payload: SearchQueryUpdateRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """Update a search query."""
    query = session.get(SearchQuery, query_id)
    if not query:
        raise HTTPException(status_code=404, detail="Search query not found")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        if hasattr(query, field):
            setattr(query, field, value)

    session.add(query)
    session.commit()
    session.refresh(query)
    return SearchQueryResponse(
        id=query.id,
        query=query.query,
        category=query.category,
        enabled=query.enabled,
        is_seed=query.is_seed,
        priority=query.priority,
        created_at=query.created_at,
    )


@admin_router.delete("/search-queries/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_search_query(
    query_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """Delete a search query."""
    query = session.get(SearchQuery, query_id)
    if not query:
        raise HTTPException(status_code=404, detail="Search query not found")
    session.delete(query)
    session.commit()


# ---------------------------------------------------------------------------
# Admin: LLM Status
# ---------------------------------------------------------------------------

@admin_router.get("/llm-status", response_model=LLMStatusResponse)
async def admin_llm_status(
    admin: User = Depends(get_current_admin),
):
    """Get LLM provider health status."""
    # TODO: Implement actual health checks via LLMRouter
    # For now return a placeholder
    return LLMStatusResponse(
        providers=[],
        active_provider="nvidia_nim",
        cache_hit_rate=0.0,
        total_calls_today=0,
    )


@admin_router.post("/llm-test", response_model=LLMTestResponse)
async def admin_test_llm(
    payload: LLMTestRequest,
    admin: User = Depends(get_current_admin),
):
    """Test an LLM provider."""
    # TODO: Implement via LLMRouter
    return LLMTestResponse(
        provider=payload.provider or "nvidia_nim",
        model="unknown",
        success=False,
        error="Not yet implemented",
    )


# ---------------------------------------------------------------------------
# Admin: Feedback
# ---------------------------------------------------------------------------

# The path segment is "feedback", not the model class name: the frontend
# client (frontend/src/api.ts -> oppfeedApi.listFeedback) calls
# /admin/oppfeed/opportunities/{id}/feedback.
@admin_router.get("/opportunities/{opp_id}/feedback", response_model=List[FeedbackResponse])
async def admin_list_feedback(
    opp_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """List reviewer feedback for an opportunity."""
    opp = session.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    feedback_list = session.exec(
        select(OppFeedFeedback).where(OppFeedFeedback.opportunity_id == opp_id).order_by(OppFeedFeedback.created_at.desc())
    ).all()

    return [
        FeedbackResponse(
            id=f.id,
            opportunity_id=f.opportunity_id,
            version=f.version,
            thumbs_up=f.thumbs_up,
            rating=f.rating,
            tags=f.tags or [],
            comment=f.comment,
            applied_as_instruction=f.applied_as_instruction,
            created_at=f.created_at,
            updated_at=f.updated_at,
        )
        for f in feedback_list
    ]


# ---------------------------------------------------------------------------
# Combine routers
# ---------------------------------------------------------------------------

router = APIRouter()
router.include_router(admin_router)
router.include_router(faculty_router)

