"""Configuration constants loaded from environment with sensible defaults."""
import os
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

    # --- Database -----------------------------------------------------------
    # PostgreSQL is the only supported database. The driver name is
    # "postgresql+psycopg" (psycopg 3). Do not write a bare "postgresql://"
    # URL - that resolves to psycopg2, which is not installed.
    database_url: str = Field(
        default="postgresql+psycopg://campuspilot:campuspilot@localhost:5432/campuspilot",
        alias="DATABASE_URL",
    )

    #: Connection pool. Sized for a 2-4 GB VPS: 10 persistent connections is
    #: ample for campus scale, while uvicorn's worker defaults can open far
    #: more and exhaust Postgres' default max_connections=100 under load.
    db_pool_size: int = Field(default=10, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=10, alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT")
    #: Seconds before a pooled connection is recycled. Postgres' own idle
    #: timeout and any upstream NAT/firewall will silently drop long-idle
    #: connections. Recycle first: 1800s sits under the usual 3600s firewall cap.
    db_pool_recycle: int = Field(default=1800, alias="DB_POOL_RECYCLE")
    #: Seconds to wait for the first connection. Lets the app tolerate Postgres
    #: still initialising on a cold `docker compose up`.
    db_connect_timeout: int = Field(default=10, alias="DB_CONNECT_TIMEOUT")
    #: TLS to the database. "prefer" because compose talks over the internal
    #: bridge network; use "require" for anything outside the host.
    db_sslmode: str = Field(default="prefer", alias="DB_SSLMODE")

    # --- Monitoring and AI scans ---------------------------------------------
    #: HMAC pepper for pseudonymising user ids in the monitoring tables.
    #: MUST be set in any deployment. The default below exists only so the test
    #: suite and a first `docker compose up` work without extra setup, and
    #: ``require_monitoring_pepper()`` refuses to let a scan or a production
    #: collector run with it. A known pepper means every `user_hash` in the
    #: database is reversible by anyone who can guess a user id - which is a
    #: sequential integer in this schema, so that is not a stretch.
    telemetry_pepper: str = Field(default="dev-only-telemetry-pepper", alias="TELEMETRY_PEPPER")

    #: Accept events from the web beacon and the Android SDK at all. Off by
    #: default because the collector is unauthenticated by necessity, and an
    #: open ingestion endpoint is a write path anyone can find.
    telemetry_enabled: bool = Field(default=False, alias="TELEMETRY_ENABLED")

    #: Events per batch the collector will accept. Bounded because the endpoint
    #: is unauthenticated: without a cap one client can send 200k events and
    #: turn a monitoring feature into a denial-of-service primitive.
    telemetry_max_batch: int = Field(default=100, alias="TELEMETRY_MAX_BATCH")

    #: Enable the `/metrics` endpoint. Separate from telemetry because Prometheus
    #: scrapes need no beacon and carry no personal data, but it does expose
    #: internal route names and should not be public on an unproxied port.
    metrics_enabled: bool = Field(default=True, alias="METRICS_ENABLED")

    #: Run the hourly rollup inside the API process on a background timer.
    #: Convenient for a single-VPS deployment where there is no separate worker.
    #: Off by default so that running more than one API replica cannot produce
    #: two rollup loops writing the same buckets - set this on exactly one
    #: process, or run `python -m features.monitoring.rollup --loop` instead.
    rollup_inline: bool = Field(default=False, alias="ROLLUP_INLINE")

    #: Accept the LLM-driven scan subsystem. Requires a local model server; see
    #: `docs/observability/ARCHITECTURE.md`. Off by default so an installation
    #: without a model is not full of ERROR verdicts.
    scan_enabled: bool = Field(default=False, alias="SCAN_ENABLED")

    #: Verify Play Store receipts. Off by default: it needs the Google Play
    #: Developer API credentials, and until then every purchase is honestly
    #: labelled unverified rather than quietly assumed good.
    enable_store_verify: bool = Field(default=False, alias="ENABLE_STORE_VERIFY")

    def require_monitoring_pepper(self) -> str:
        """Return the pepper, refusing the default outside tests.

        The check is in code rather than in a `.env` file because a deployment
        that forgets a variable should fail loudly at the point of use, not
        quietly write reversible pseudonyms forever.
        """
        if self.telemetry_pepper == "dev-only-telemetry-pepper":
            if os.environ.get("PYTEST_CURRENT_TEST"):
                return self.telemetry_pepper
            raise RuntimeError(
                "TELEMETRY_PEPPER is unset. Generate one with "
                "`python -c \"import secrets; print(secrets.token_hex(32))\"`. "
                "The default value is for local development only."
            )
        return self.telemetry_pepper

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