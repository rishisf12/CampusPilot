from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.middleware import SecurityHeadersMiddleware, RequestIDMiddleware, RateLimitMiddleware
from app.db.session import init_db
from app.api.v1.api import api_router
from app.api.v1 import ws as ws_router
from app.workers.idle_supervisor import get_supervisor

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    supervisor = get_supervisor()
    await supervisor.start()
    yield
    # Shutdown
    await supervisor.stop()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
# WebSocket endpoint lives at /ws (proxied by nginx; not under /api/v1)
app.include_router(ws_router.router)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(RateLimitMiddleware, limit=20, window=60)


@app.get("/", tags=["root"])
def root():
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION}
