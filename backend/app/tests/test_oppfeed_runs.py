"""A run is a piece of work, and the admin can watch it happen.

The trigger used to create a run row and stop there - the pipeline was a
TODO - so every run sat at "pending" for ever and the admin's screen showed
two runs that had never done anything. These tests pin the run down: it
starts, it records each stage, it counts what it found, and the drafts it
saves reach the opportunities the app reads.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from core.database import engine
from features.auth.routes import create_access_token
from features.oppfeed.models import (
    AgentRun,
    Opportunity,
    RunStatus,
    RunStep,
    StepStatus,
)
from main import app
from models import User, UserRole

RUN_ID = "test-run-0001"


@pytest.fixture
def anon_client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_headers():
    with Session(engine) as s:
        user = s.exec(select(User).where(User.username == "run_admin")).first()
        if user is None:
            user = User(
                email="run_admin@iiitdmj.ac.in",
                password_hash="x",
                full_name="run_admin",
                username="run_admin",
                roll_number="23BCS001",
                is_email_verified=True,
                role=UserRole.ADMIN,
            )
            s.add(user)
            s.commit()
            s.refresh(user)
        user.role = UserRole.ADMIN
        s.add(user)
        s.commit()
        user_id = user.id
    return {"Authorization": f"Bearer {create_access_token(user_id, 'run_admin')}"}


@pytest.fixture(autouse=True)
def clean():
    yield
    with Session(engine) as s:
        s.exec(delete(RunStep).where(RunStep.run_id == RUN_ID))
        s.exec(delete(AgentRun).where(AgentRun.run_id == RUN_ID))
        s.exec(delete(Opportunity).where(Opportunity.created_by_run_id == RUN_ID))
        s.commit()


def test_triggering_a_run_starts_it(anon_client, admin_headers, monkeypatch):
    """The trigger starts the pipeline instead of writing a TODO."""
    from features.oppfeed import routes as oppfeed_routes

    started = {}

    def fake_start(run_id, mode="manual"):
        started["run_id"] = run_id
        started["mode"] = mode

    monkeypatch.setattr(oppfeed_routes, "start_run", fake_start, raising=False)
    # The route imports the runner lazily, so the name it looks up is patched
    # on the module it imports from.
    monkeypatch.setattr(
        "features.oppfeed.runner.start_run", fake_start, raising=True
    )

    response = anon_client.post(
        "/admin/oppfeed/runs", headers=admin_headers, json={"mode": "manual"}
    )
    assert response.status_code == 201, response.text
    assert started, "the pipeline was never started"
    assert started["run_id"] == response.json()["run_id"]


def test_a_run_records_its_stages(anon_client, admin_headers, monkeypatch):
    """Each stage leaves a step behind, so the run can be read as it goes."""
    from features.oppfeed import runner

    with Session(engine) as s:
        s.add(AgentRun(run_id=RUN_ID, status=RunStatus.PENDING, mode="manual"))
        s.commit()

    runner._mark_running(RUN_ID)
    runner._begin_step(RUN_ID, "search")
    runner._finish_step(
        RUN_ID, "search", StepStatus.COMPLETED, output={"results": 12}, duration_ms=420
    )
    runner._set_stage(RUN_ID, "search")

    with Session(engine) as s:
        run = s.exec(select(AgentRun).where(AgentRun.run_id == RUN_ID)).first()
        assert run.status == RunStatus.RUNNING
        assert run.current_stage == "search"
        steps = s.exec(select(RunStep).where(RunStep.run_id == RUN_ID)).all()
        assert len(steps) == 1
        step = steps[0]
        assert step.step_name == "search"
        assert step.status == StepStatus.COMPLETED
        assert step.duration_ms == 420
        assert step.output_data["results"] == 12


def test_a_finished_run_carries_the_counts(anon_client, admin_headers):
    """The counts are the pipeline's own, not guesses."""
    from features.oppfeed import runner

    class FakeState:
        candidates = [1, 2, 3, 4, 5]
        verification_result = [1, 2, 3]
        opportunities_drafted = 2
        llm_calls = 7
        llm_tokens = 900
        errors = []
        current_stage = "done"

        def to_checkpoint(self):
            return {"run_id": RUN_ID, "current_stage": "done"}

    with Session(engine) as s:
        s.add(AgentRun(run_id=RUN_ID, status=RunStatus.RUNNING, mode="manual"))
        s.commit()

    runner._complete(RUN_ID, FakeState(), drafted=2)

    with Session(engine) as s:
        run = s.exec(select(AgentRun).where(AgentRun.run_id == RUN_ID)).first()
        assert run.status == RunStatus.COMPLETED
        assert run.completed_at is not None
        assert run.opportunities_found == 5
        assert run.opportunities_verified == 3
        assert run.opportunities_rejected == 2
        assert run.opportunities_drafted == 2
        assert run.llm_calls == 7
        assert run.llm_tokens == 900


def test_a_failed_run_says_why(anon_client, admin_headers):
    """A run that could not finish says so, rather than staying pending."""
    from features.oppfeed import runner

    with Session(engine) as s:
        s.add(AgentRun(run_id=RUN_ID, status=RunStatus.RUNNING, mode="manual"))
        s.commit()

    runner._fail(RUN_ID, RuntimeError("the search provider was unreachable"))

    with Session(engine) as s:
        run = s.exec(select(AgentRun).where(AgentRun.run_id == RUN_ID)).first()
        assert run.status == RunStatus.FAILED
        assert run.completed_at is not None
        assert "unreachable" in str(run.errors)


def test_the_drafts_reach_the_opportunities(anon_client, admin_headers):
    """The agent saves drafts in its own table; the app reads opportunities."""
    from features.oppfeed import runner

    with engine.begin() as conn:
        conn.execute(
            __import__("sqlalchemy").text(
                "INSERT INTO core.oppfeed_opportunity_draft "
                "(slug, status, title, organization_name, opportunity_type, "
                "apply_url, deadline_type, education_levels, allowed_branches, "
                "graduation_years, skills_required, perks_benefits, "
                "documents_required, secondary_sources, verification_report, "
                "field_evidence, llm_provider, llm_model, prompt_version, tags, "
                "version, created_by_run_id, stipend_currency) "
                "VALUES (:slug, 'DRAFT', :title, :org, 'INTERNSHIP', :url, "
                "'fixed', '[]', '[]', '[]', '[]', '[]', '[]', '[]', '{}', '{}', "
                "'mock', 'mock-model-1', '1.0', '[]', 1, :run_id, 'INR') "
                "ON CONFLICT (slug) DO NOTHING"
            ),
            {
                "slug": "test-run-draft-1",
                "title": "Software Engineering Internship 2026",
                "org": "Freshersbridge",
                "url": "https://example.org/internships",
                "run_id": RUN_ID,
            },
        )

    created = runner._bring_drafts_across(RUN_ID)
    assert created == 1

    with Session(engine) as s:
        opp = s.exec(
            select(Opportunity).where(Opportunity.slug == "test-run-draft-1")
        ).first()
        assert opp is not None
        assert opp.title == "Software Engineering Internship 2026"
        assert opp.created_by_run_id == RUN_ID
        assert opp.status == "draft"

    # And again: the same draft is not a second opportunity.
    assert runner._bring_drafts_across(RUN_ID) == 0


def test_a_run_publishes_its_drafts_when_auto_publish_is_on(anon_client, admin_headers):
    """
    The auto-publish switch is wired to the run.

    It existed, and the publishing service existed, and nothing called
    them: a run finished, its drafts sat in the queue, and the feed stayed
    empty. A switch that is wired to nothing is a lie the admin reads.
    """
    from features.oppfeed import runner
    from features.oppfeed.models import AgentSettings

    with Session(engine) as s:
        settings = s.exec(select(AgentSettings)).first()
        if settings is None:
            settings = AgentSettings()
            s.add(settings)
            s.commit()
            s.refresh(settings)
        was_enabled = settings.auto_publish_enabled
        was_threshold = settings.auto_publish_threshold
        settings.auto_publish_enabled = True
        settings.auto_publish_threshold = 0.5
        s.add(settings)
        s.commit()

    try:
        with Session(engine) as s:
            s.add(
                Opportunity(
                    slug="test-run-publish-1",
                    status="draft",
                    title="A verified internship",
                    organization_name="Somewhere",
                    opportunity_type="INTERNSHIP",
                    apply_url="https://example.org/verified",
                    confidence_score=0.9,
                    verification_report={"checks": {"url_live": True}},
                    llm_provider="nvidia_nim",
                    created_by_run_id=RUN_ID,
                )
            )
            s.commit()

        published = runner._publish(RUN_ID)
        assert published == 1, published

        with Session(engine) as s:
            opp = s.exec(
                select(Opportunity).where(Opportunity.slug == "test-run-publish-1")
            ).first()
            assert opp.status == "published"
    finally:
        with Session(engine) as s:
            settings = s.exec(select(AgentSettings)).first()
            if settings is not None:
                settings.auto_publish_enabled = was_enabled
                settings.auto_publish_threshold = was_threshold
                s.add(settings)
                s.commit()


def test_a_mock_extraction_is_never_published(anon_client, admin_headers):
    """
    A placeholder must not reach the students' feed.

    The mock provider stands in for an LLM that is not there, so what it
    extracts is a stand-in. Publishing one would put an invented opportunity
    in front of students, which is worse than publishing nothing.
    """
    from features.oppfeed.services.publishing_service import PublishingService

    with Session(engine) as s:
        s.add(
            Opportunity(
                slug="test-run-mock-1",
                status="draft",
                title="An invented internship",
                organization_name="Nobody",
                opportunity_type="INTERNSHIP",
                apply_url="https://example.org/invented",
                confidence_score=0.95,
                verification_report={"checks": {"url_live": True}},
                llm_provider="mock",
                created_by_run_id=RUN_ID,
            )
        )
        s.commit()

    with Session(engine) as s:
        opp = s.exec(
            select(Opportunity).where(Opportunity.slug == "test-run-mock-1")
        ).first()
        assert PublishingService.should_auto_publish(
            opp, enabled=True, threshold=0.5
        ) is False


def test_the_run_list_carries_the_progress(anon_client, admin_headers):
    """The progress bar is counted in the pipeline's own stages."""
    from features.oppfeed import runner

    with Session(engine) as s:
        s.add(AgentRun(run_id=RUN_ID, status=RunStatus.RUNNING, mode="manual"))
        s.commit()
    runner._begin_step(RUN_ID, "search")
    runner._finish_step(RUN_ID, "search", StepStatus.COMPLETED, output={})
    runner._set_stage(RUN_ID, "search")

    response = anon_client.get("/admin/oppfeed/runs", headers=admin_headers)
    assert response.status_code == 200, response.text
    rows = [r for r in response.json() if r["run_id"] == RUN_ID]
    assert rows, response.json()
    row = rows[0]
    assert row["stages_completed"] == 1
    assert row["total_stages"] >= 1
    assert row["current_stage"]
    # The counts the list shows are the run's own.
    assert "opportunities_verified" in row
    assert "opportunities_drafted" in row
