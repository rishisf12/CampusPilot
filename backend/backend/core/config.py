"""Configuration constants loaded from environment with sensible defaults."""
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    # Security
    #: Must be >= 32 bytes for HS256 (RFC 7518); override via the environment.
    SECRET_KEY: str = "dev-secret-change-in-production-0123456789abcdef"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 7 * 24 * 60  # 7 days

    # Database
    database_url: str = Field(default="sqlite:///" + str(Path(__file__).resolve().parents[3] / "database" / "classpilot.db"), alias="DATABASE_URL")

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@iiitdmj.ac.in"

    # Frontend URL for CORS
    FRONTEND_URL: str = "http://localhost:5173"

    # --- Passkeys (WebAuthn) -------------------------------------------------
    #: The relying-party id, which must be the domain the browser sees. localhost
    #: counts as a secure context, so passkeys work over plain HTTP in dev.
    PASSKEY_RP_ID: str = Field(default="localhost", alias="PASSKEY_RP_ID")
    #: Human-readable relying-party name shown by the device prompt.
    PASSKEY_RP_NAME: str = Field(default="essential - Your Campus Assistant", alias="PASSKEY_RP_NAME")
    #: Origin(s) the browser is allowed to present from. Comma-separated so a
    #: deployed app can list its own origin alongside a staging one.
    PASSKEY_ORIGINS: str = Field(default="http://localhost:5173", alias="PASSKEY_ORIGINS")

    @property
    def passkey_origins(self) -> list[str]:
        return [item.strip().rstrip("/") for item in self.PASSKEY_ORIGINS.split(",") if item.strip()]

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
    max_upload_mb: int = Field(default=25, alias="MAX_UPLOAD_MB")
    allowed_extensions: str = Field(default=".pdf,.csv", alias="ALLOWED_EXTENSIONS")

    # Team-finding (My Team): points added to the skill-match score when the
    # viewer shares the team owner's branch. Signup is restricted to one
    # college, so same-branch is real signal a skill-only model cannot express.
    branch_match_bonus: float = Field(default=15.0, alias="BRANCH_MATCH_BONUS")

    # ------------------------------------------------------- hackathon feed
    # The feed is populated by email rather than posted by hand. Gmail IMAP is
    # read with the stdlib `imaplib`, so this adds no dependency - but it needs
    # an App Password, which is why the feed stays inert until the password is
    # set. Blank credentials disable ingestion rather than raising at import,
    # so the rest of the app is unaffected.
    feed_imap_host: str = Field(default="imap.gmail.com", alias="FEED_IMAP_HOST")
    feed_imap_port: int = Field(default=993, alias="FEED_IMAP_PORT")
    feed_imap_user: str = Field(default="", alias="FEED_IMAP_USER")
    #: Gmail App Password (16 chars), not the account password.
    feed_imap_password: str = Field(default="", alias="FEED_IMAP_PASSWORD")
    feed_mailbox: str = Field(default="INBOX", alias="FEED_MAILBOX")

    #: Feed entries are removed this many days after they arrive, rows *and*
    #: their attachment files. The user asked for deletion, not hiding.
    feed_retention_days: int = Field(default=30, alias="FEED_RETENTION_DAYS")

    #: Attachment limits. Executables are never accepted - a public mailbox that
    #: accepts .exe invites anyone to use this as a file host. Media defaults
    #: under the same uploads folder the exam/timetable files use.
    feed_media_dir: str = Field(
        default=str(Path(__file__).resolve().parents[1] / "uploads" / "feed_media"),
        alias="FEED_MEDIA_DIR",
    )
    feed_max_attachments: int = Field(default=5, alias="FEED_MAX_ATTACHMENTS")
    feed_max_attachment_bytes: int = Field(default=5 * 1024 * 1024, alias="FEED_MAX_ATTACHMENT_BYTES")
    feed_max_body_chars: int = Field(default=8000, alias="FEED_MAX_BODY_CHARS")

    # Exam / branch inference
    #: Canonical branch list used across profile dropdowns and exam filtering.
    branch_options: str = Field(
        default="CSE A,CSE B,DS,ECE,ME,SM,PG,MDes",
        alias="BRANCH_OPTIONS",
    )
    #: Programme -> ordered semester count (drives the semester dropdown).
    programme_semesters: str = Field(
        default="BTech:8,BDes:8,MTech:4,MDes:4,PhD:2",
        alias="PROGRAMME_SEMESTERS",
    )
    #: College admission year used to map a roll-number prefix to a semester.
    admission_year: int = Field(default=21, alias="ADMISSION_YEAR")

    class Config:
        env_file = Path(__file__).resolve().parents[3] / ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @property
    def feed_enabled(self) -> bool:
        """Mail ingestion only runs with both halves of the credential present."""
        return bool(self.feed_imap_user and self.feed_imap_password)


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

BRANCH_OPTIONS = [b.strip() for b in settings.branch_options.split(",") if b.strip()]

PROGRAMME_SEMESTERS = {
    programme.strip(): int(count)
    for programme, count in (
        pair.split(":") for pair in settings.programme_semesters.split(",")
    )
}