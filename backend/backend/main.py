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
            except Exception:  # noqa: BLE001 - the loop must outlive any failure
                logger.exception("rollup failed; will retry next interval")

    thread = threading.Thread(target=loop, name="hourly-rollup", daemon=True)
    thread.start()
    logger.info("inline rollup loop started (interval %ds)", interval_s)
    return thread


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    create_db_and_tables()
    if settings.rollup_inline:
        _start_rollup_loop()
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
from features.schedule import routes as schedule
from features.profile import routes as profile
from features.rooms import routes as rooms
from features.exam import routes as exam
from features.auth import routes as auth
from features.feedback import routes as feedback
from features.teams import routes as teams
from features.monitoring.api.routes import collect_router, monitoring_router
from ocr import routes as ocr_routes
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(attendance.router, prefix="/attendance", tags=["Attendance"])
app.include_router(timetable.router, prefix="/timetable", tags=["Timetable"])
app.include_router(schedule.router, prefix="/schedule", tags=["Schedule"])
app.include_router(profile.router, prefix="/profile", tags=["Profile"])
app.include_router(rooms.router, prefix="/rooms", tags=["Rooms"])
app.include_router(exam.router, prefix="/exam", tags=["Exam"])
app.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
app.include_router(teams.router, prefix="/teams", tags=["Teams"])
app.include_router(teams.hackathons_router, prefix="/hackathons", tags=["Hackathons"])
app.include_router(ocr_routes.router, prefix="/ocr", tags=["OCR Extraction"])
app.include_router(collect_router)
app.include_router(monitoring_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)