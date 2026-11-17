from fastapi import FastAPI
from app.core.database import create_db_and_tables

app = FastAPI(title="Mail Service")


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()


@app.get("/")
def root() -> dict:
    return {"message": "Mail Service"}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
