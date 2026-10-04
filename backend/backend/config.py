"""Configuration constants loaded from environment with sensible defaults."""
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    # Security
    SECRET_KEY: str = "dev-secret-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 7 * 24 * 60  # 7 days

    # Database
    database_url: str = Field(default="sqlite:///" + str(Path(__file__).resolve().parents[2] / "database" / "classpilot.db"), alias="DATABASE_URL")

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@iiitdmj.ac.in"

    # Frontend URL for CORS
    FRONTEND_URL: str = "http://localhost:5173"

    # Allowed email domain
    ALLOWED_EMAIL_DOMAIN: str = "@iiitdmj.ac.in"

    # Timezone
    timezone: str = Field(default="Asia/Kolkata", alias="TIMEZONE")
    college_start: str = Field(default="09:00", alias="COLLEGE_START")
    college_end: str = Field(default="17:00", alias="COLLEGE_END")
    lunch_start: str = Field(default="13:00", alias="LUNCH_START")
    lunch_end: str = Field(default="14:00", alias="LUNCH_END")
    attendance_safe: int = Field(default=75, alias="ATTENDANCE_SAFE")
    attendance_warning: int = Field(default=65, alias="ATTENDANCE_WARNING")
    max_upload_mb: int = Field(default=10, alias="MAX_UPLOAD_MB")
    allowed_extensions: str = Field(default=".pdf,.csv", alias="ALLOWED_EMAIL_DOMAIN")

    class Config:
        env_file = Path(__file__).resolve().parents[2] / ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings():
    return Settings()


settings = Settings()

# Derived constants for easy import
COLLEGE_START_HOUR = int(settings.college_start.split(":")[0])
COLLEGE_END_HOUR = int(settings.college_end.split(":")[0])
LUNCH_START_HOUR = int(settings.lunch_start.split(":")[0])
LUNCH_END_HOUR = int(settings.lunch_end.split(":")[0])

DAYS_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_TO_INT = {d: i for i, d in enumerate(DAYS_ORDER)}