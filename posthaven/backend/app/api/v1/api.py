from fastapi import APIRouter
from app.api.v1 import health
from app.api.v1 import auth
from app.api.v1 import accounts
from app.api.v1 import folders
from app.api.v1 import messages
from app.api.v1 import compose
from app.api.v1 import search
from app.api.v1 import labels
from app.api.v1 import rules
from app.api.v1 import snooze
from app.api.v1 import contacts
from app.api.v1 import settings
from app.api.v1 import admin

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(accounts.router)
api_router.include_router(folders.router)
api_router.include_router(messages.router)
api_router.include_router(compose.router)
api_router.include_router(search.router)
api_router.include_router(labels.router)
api_router.include_router(rules.router)
api_router.include_router(snooze.router)
api_router.include_router(contacts.router)
api_router.include_router(settings.router)
api_router.include_router(admin.router)
