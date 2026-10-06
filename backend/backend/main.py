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


from features.attendance import routes as attendance
from features.timetable import routes as timetable
from features.schedule import routes as schedule
from features.profile import routes as profile
from features.rooms import routes as rooms
from features.exam import routes as exam
from features.auth import routes as auth
from features.feedback import routes as feedback
from features.teams import routes as teams
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)