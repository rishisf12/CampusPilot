from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "PostHaven"
    APP_VERSION: str = "0.1.0"
    ENV: str = "development"

    # Database (async for app, sync for Alembic)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/posthaven"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://postgres:postgres@db:5432/posthaven"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Security
    SECRET_KEY: str = "dev-secret-change-me"
    ENCRYPTION_KEY: str = "dev-encryption-key-32bytes!!"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # SSRF guard
    ALLOW_PRIVATE_MAIL_HOSTS: bool = True  # needed for GreenMail in dev

    # Sync
    SYNC_HEADERS_LIMIT: int = 200

    # CORS
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
