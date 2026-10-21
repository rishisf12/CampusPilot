"""Daily OppFeed agent run job — CampusPilot integration.

Uses APScheduler (added to requirements) to run the agent pipeline
during the configured window (default 02:00-04:00 IST).
"""
import uuid
from datetime import datetime, timezone

from sqlmodel import Session, select

from core.database import engine
from features.oppfeed.models import AgentRun, RunStatus

# The agent package (and the scraping stack it pulls in) is imported lazily,
# inside the function that actually runs it. Scheduling the job must not
# require the optional scraping libraries to be installed.


def _load_pipeline():
    """Import the agent pipeline on demand.

    Raises with a clear message when the optional agent dependencies are
    missing, rather than an opaque ImportError at application start-up.
    """
    try:
        from features.oppfeed.agent.graph import AgentPipeline
    except ImportError as exc:
        raise ImportError(
            "The OppFeed agent needs its optional scraping dependencies. "
            "Install them with: pip install -r requirements.txt "
            f"(original error: {exc})"
        ) from exc
    return AgentPipeline


def run_daily_agent_job() -> None:
    """Trigger the daily OppFeed agent pipeline run.

    Creates a run record, checks for active runs, then launches the
    agent pipeline in the background.
    """
    with Session(engine) as db:
        # Check for existing active runs
        active = db.exec(
            select(AgentRun).where(
                AgentRun.status.in_([RunStatus.PENDING, RunStatus.RUNNING])
            )
        ).first()

        if active:
            print(f"Run {active.run_id} already active, skipping.")
            return

        # Create new run
        now = datetime.now(timezone.utc)
        run = AgentRun(
            run_id=f"run-{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}",
            status=RunStatus.PENDING,
            mode="scheduled",
            started_at=now,
            created_at=now,
        )
        db.add(run)
        db.commit()
        print(f"Created scheduled run: {run.run_id}")
        run_id = run.run_id

    # The pipeline runs in the background and records its own progress: the
    # same path a manual run takes, so the admin sees the same run either
    # way.
    from features.oppfeed.runner import start_run

    start_run(run_id, mode="scheduled")


def schedule_daily_agent_job() -> None:
    """Schedule the daily agent job via APScheduler.

    This should be called at app startup. The actual schedule
    (run window) is configured via AgentSettings in the DB.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        print("APScheduler not installed, skipping daily agent job scheduling")
        return

    # Read settings from DB to get the run window
    with Session(engine) as db:
        from features.oppfeed.models import AgentSettings
        settings = db.exec(select(AgentSettings)).first()
        if not settings or not settings.enable_scheduler:
            print("Agent scheduler disabled in settings")
            return

        # Parse run window (HH:MM format, IST)
        start_hour, start_min = map(int, settings.run_window_start.split(":"))
        end_hour, end_min = map(int, settings.run_window_end.split(":"))

    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
    # Schedule at the start of the window
    scheduler.add_job(
        run_daily_agent_job,
        CronTrigger(hour=start_hour, minute=start_min, timezone="Asia/Kolkata"),
        id="oppfeed_daily_agent",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    print(f"Scheduled OppFeed daily agent job at {settings.run_window_start} IST")

    # Store scheduler reference for graceful shutdown
    import atexit
    atexit.register(lambda: scheduler.shutdown())