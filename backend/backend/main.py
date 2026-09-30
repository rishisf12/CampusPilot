"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import create_db_and_tables
from config import settings

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


from routes import attendance, timetable, schedule, profile, rooms, exam
from ocr_engine import routes as ocr_routes
app.include_router(attendance.router, prefix="/attendance", tags=["Attendance"])
app.include_router(timetable.router, prefix="/timetable", tags=["Timetable"])
app.include_router(schedule.router, prefix="/schedule", tags=["Schedule"])
app.include_router(profile.router, prefix="/profile", tags=["Profile"])
app.include_router(rooms.router, prefix="/rooms", tags=["Rooms"])
app.include_router(exam.router, prefix="/exam", tags=["Exam"])
app.include_router(ocr_routes.router, prefix="/ocr", tags=["OCR Extraction"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)