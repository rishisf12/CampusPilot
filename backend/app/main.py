"""FastAPI application entry point."""
import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from core.database import create_db_and_tables
from core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _start_rollup_loop(interval_s: int = 3600) -> threading.Thread:
    """Recompute the hourly rollup on a timer, in this process.

    Only started when ROLLUP_INLINE is on, and the docstring on that setting
    explains why: with more than one replica, two timers rebuild the same
    buckets concurrently. They would each delete-then-insert, so the result
    converges anyway, but the intermediate window where the rollup is empty is
    visible to a dashboard and is exactly the kind of flapping that trains an
    admin to ignore the alerts.
    """
    from core.database import session_scope
    from features.monitoring.infrastructure import rollup as rollup_mod

    def loop() -> None:
        while True:
            time.sleep(interval_s)
            try:
                with session_scope() as db:
                    summary = rollup_mod.rollup(db)
                logger.info("rollup: %s", summary)
            except Exception:
                logger.exception("rollup failed; will retry next interval")

    thread = threading.Thread(target=loop, name="hourly-rollup", daemon=True)
    thread.start()
    logger.info("inline rollup loop started (interval %ds)", interval_s)
    return thread


def _start_health_loop(interval_s: int | None = None) -> threading.Thread:
    """Sample the Prometheus instruments into `health_metric` on a timer.

    Gated by HEALTH_SAMPLE_INLINE for the same multi-replica reason as the
    rollup loop: each replica computes its deltas from its own in-process
    counters, so a dashboard pointed at a different replica than the one
    sampling would compare two unrelated processes.
    """
    from features.monitoring.infrastructure import health as health_mod

    return health_mod.start_loop(interval_s)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    create_db_and_tables()

    # Load feature flags and maintenance mode
    from core.database import engine as _engine
    from core.feature_flags import flag_engine
    from core.maintenance import maintenance_mode
    from sqlmodel import Session

    with Session(_engine) as session:
        flag_engine.load(session)
        maintenance_mode.load(session)

        # The default alert rules, so alerting works on a fresh install
        # instead of waiting for somebody to create them. Idempotent: a rule
        # that already exists is left alone.
        try:
            from features.alerts.seed import seed_default_rules

            created = seed_default_rules(session)
            if created:
                logger.info("seeded %d default alert rule(s)", created)
        except Exception as e:  # noqa: BLE001 - a missing rule must not stop the boot
            logger.warning("Failed to seed the default alert rules: %s", e)

    # Instruments DB_QUERY_DURATION / DB_QUERIES, which are otherwise declared
    # and never incremented, and which the health sampler reads.
    from features.monitoring.infrastructure import db_instrumentation

    db_instrumentation.attach()

    if settings.rollup_inline:
        _start_rollup_loop()
    if settings.health_sample_inline:
        _start_health_loop()

    # Schedule OppFeed daily agent job if enabled
    try:
        from features.oppfeed.jobs import schedule_daily_agent_job
        schedule_daily_agent_job()
    except Exception as e:
        logger.warning("Failed to schedule OppFeed daily agent job: %s", e)

    yield
    logger.info("Shutting down...")


app = FastAPI(title="ClassPilot API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Maintenance mode middleware (must be early)
from core.maintenance import MaintenanceMiddleware
app.add_middleware(MaintenanceMiddleware)

# Request monitoring middleware
from core.monitoring import RequestMonitoringMiddleware
app.add_middleware(RequestMonitoringMiddleware)


@app.get("/health")
def health_check():
    return {"status": "ok"}


def _metrics_middleware():
    """Instrument every request, and serve `/metrics`.

    Installed as middleware rather than by wrapping the app so that it also
    captures requests that 404 or raise. A latency figure that silently omits
    the slowest requests - which are precisely the ones that error - is worse
    than no figure, because it looks like good news.

    Path collapsing happens before the label is set. Without it,
    `/feedback/12345` and `/feedback/67890` are different time series, a busy
    endpoint quietly multiplies the size of the metrics store, and a client that
    polls a distinct URL per request can exhaust it.
    """
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    from features.monitoring.infrastructure.metrics import (
        REGISTRY, REQUESTS, REQUEST_DURATION, REQUEST_IN_FLIGHT,
        route_template, status_class,
    )

    @app.middleware("http")
    async def instrument(request: Request, call_next):
        # The scrape endpoint is excluded from its own instrumentation. Counting
        # it would mean every scrape adds a sample to the histogram it is about
        # to read, and the metrics endpoint would report latency numbers that
        # include its own serialization cost.
        if request.url.path == "/metrics":
            return await call_next(request)

        route = route_template(request.url.path)
        # Label-less gauge, so it is inc()/dec() directly. An in-flight count
        # labelled by route would be useless for its actual job, which is
        # "is the whole server backed up" - a sum across routes.
        REQUEST_IN_FLIGHT.inc()
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            REQUESTS.labels(route, request.method, "5xx").inc()
            REQUEST_DURATION.labels(route, request.method).observe(
                time.perf_counter() - started
            )
            REQUEST_IN_FLIGHT.dec()
            raise
        REQUEST_DURATION.labels(route, request.method).observe(time.perf_counter() - started)
        REQUESTS.labels(route, request.method, status_class(response.status_code)).inc()
        REQUEST_IN_FLIGHT.dec()
        return response

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        if not settings.metrics_enabled:
            return PlainTextResponse("metrics disabled\n", status_code=404)
        return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


_metrics_middleware()


from features.attendance import routes as attendance
from features.timetable import routes as timetable
from features.timetable import reinforcement_routes as reinforcement
from features.schedule import routes as schedule
from features.profile import routes as profile
from features.rooms import routes as rooms
from features.exam import routes as exam
from features.auth import routes as auth
from features.feedback import routes as feedback
from features.monitoring.api.routes import collect_router, monitoring_router
from features.admin import routes as admin_routes
from features.audit import routes as audit_routes
from features.flags import routes as flags_routes
from features.maintenance import routes as maintenance_routes
from features.remote_config import routes as remote_config_routes
from features.errors import routes as errors_routes
from features.alerts import routes as alerts_routes
from features.health import routes as health_routes
from features.analytics import routes as analytics_routes
from features.user_control import routes as user_control_routes
from features.broadcasts import routes as broadcasts_routes
from features.force_update import routes as force_update_routes
from features.security import routes as security_routes
from ocr import routes as ocr_routes
from features.settings import routes as settings_routes
from features.oppfeed.api import router as oppfeed_router
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(attendance.router, prefix="/attendance", tags=["Attendance"])
app.include_router(timetable.router, prefix="/timetable", tags=["Timetable"])
app.include_router(reinforcement.router, prefix="/reinforcement", tags=["Reinforcement Patterns"])
app.include_router(schedule.router, prefix="/schedule", tags=["Schedule"])
app.include_router(profile.router, prefix="/profile", tags=["Profile"])
app.include_router(settings_routes.router, tags=["Settings"])
app.include_router(oppfeed_router, tags=["OppFeed"])
app.include_router(rooms.router, prefix="/rooms", tags=["Rooms"])
app.include_router(exam.router, prefix="/exam", tags=["Exam"])
app.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
app.include_router(ocr_routes.router, prefix="/ocr", tags=["OCR Extraction"])
app.include_router(admin_routes.router, prefix="/admin", tags=["Admin"])
# The feature routers below already declare their own "/admin/..." prefix
# internally, so no prefix is passed here. Passing prefix="/admin" as well
# concatenated to "/admin/admin/..." on every route, 404ing the entire new
# admin surface while the paths looked right in both files. `health` was
# already registered this way, which is why only it worked.
app.include_router(audit_routes.router, tags=["Admin - Audit"])
app.include_router(flags_routes.router, tags=["Admin - Feature Flags"])
app.include_router(maintenance_routes.router, tags=["Admin - Maintenance"])
app.include_router(remote_config_routes.router, tags=["Admin - Remote Config"])
app.include_router(errors_routes.router, tags=["Admin - Errors"])
app.include_router(alerts_routes.router, tags=["Admin - Alerts"])
app.include_router(health_routes.router)
app.include_router(analytics_routes.router, tags=["Admin - Analytics"])
app.include_router(user_control_routes.router, tags=["Admin - User Control"])
app.include_router(broadcasts_routes.router, tags=["Admin - Broadcasts"])
app.include_router(force_update_routes.router, tags=["Admin - Force Update"])
app.include_router(security_routes.router, tags=["Admin - Security"])
app.include_router(collect_router)
app.include_router(monitoring_router)

# The HTTP MCP endpoint is optional and off by default: with the flag false
# the paths do not exist at all, rather than existing and refusing.
if settings.enable_admin_mcp:
    from mcp.api.routes import router as mcp_router

    app.include_router(mcp_router, prefix="/api/mcp", tags=["Admin - MCP"])
    logger.info("admin MCP endpoint mounted at /api/mcp (ENABLE_ADMIN_MCP=true)")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
