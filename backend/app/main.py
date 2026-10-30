"""FastAPI application entry point."""
import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.database import create_db_and_tables
from core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


@app.get("/health")
def health_check():
    return {"status": "ok"}


from features.attendance import routes as attendance
from features.timetable import routes as timetable
from features.timetable import reinforcement_routes as reinforcement
from features.schedule import routes as schedule
from features.profile import routes as profile
from features.rooms import routes as rooms
from features.exam import routes as exam
from features.auth import routes as auth
from features.feedback import routes as feedback
from features.task import routes as task_routes
from features.admin import routes as admin_routes
from features.audit import routes as audit_routes
from features.flags import routes as flags_routes
from features.maintenance import routes as maintenance_routes
from features.remote_config import routes as remote_config_routes
from features.errors import routes as errors_routes
from features.health import routes as health_routes
from features.analytics import routes as analytics_routes
from features.user_control import routes as user_control_routes
from features.broadcasts import routes as broadcasts_routes
from features.force_update import routes as force_update_routes
from features.security import routes as security_routes
from ocr import routes as ocr_routes
from features.settings import routes as settings_routes
from features.mail.routes import router as mail_router
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(attendance.router, prefix="/attendance", tags=["Attendance"])
app.include_router(timetable.router, prefix="/timetable", tags=["Timetable"])
app.include_router(reinforcement.router, prefix="/reinforcement", tags=["Reinforcement Patterns"])
app.include_router(schedule.router, prefix="/schedule", tags=["Schedule"])
app.include_router(profile.router, prefix="/profile", tags=["Profile"])
# The administrator's own profile - a separate surface from the student one.
from features.profile import admin_routes as profile_admin  # noqa: E402

app.include_router(profile_admin.router, prefix="/profile", tags=["Profile"])
app.include_router(settings_routes.router, tags=["Settings"])
if settings.enable_agent:
    from features.oppfeed.api import router as oppfeed_router
    app.include_router(oppfeed_router, tags=["OppFeed"])
app.include_router(mail_router, tags=["Mail"])
app.include_router(rooms.router, prefix="/rooms", tags=["Rooms"])
app.include_router(exam.router, prefix="/exam", tags=["Exam"])
app.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
app.include_router(task_routes.router, prefix="/tasks", tags=["Task"])
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
app.include_router(health_routes.router)
app.include_router(analytics_routes.router, tags=["Admin - Analytics"])
app.include_router(user_control_routes.router, tags=["Admin - User Control"])
app.include_router(broadcasts_routes.router, tags=["Admin - Broadcasts"])
app.include_router(force_update_routes.router, tags=["Admin - Force Update"])
app.include_router(security_routes.router, tags=["Admin - Security"])
from features.extra_events import router as extra_events_router
app.include_router(extra_events_router, tags=["Extra Events"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
