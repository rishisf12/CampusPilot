"""
The mail app's own settings.

Every knob the mail system has, read from the environment with a safe
default, in one place. They live here rather than in the application's
central configuration module so that the mail rebuild can be changed,
rolled back and reviewed without touching the settings of the rest of the
site.

Nothing here is a secret. Credentials belong to the provider configuration
(MAIL_MAILBOXES_JSON and the provider's own variables), never to this file.
"""
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional


DEFAULT_INSTITUTE = (
    "Indian Institute of Information Technology, Design and Manufacturing, "
    "Jabalpur"
)

DEFAULT_PORTAL_URL = "https://iiitdmj.ac.in"

DEFAULT_FOOTER_TEXT = (
    "---\n"
    "{{institute}}\n"
    "{{section}}\n"
    "{{sender_name}} <{{sender_email}}>\n"
    "{{portal_url}}\n"
    "This is an official notice from the institute. Please do not remove "
    "this footer.\n"
)


def _flag(name: str, default: bool = False) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _number(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _text(name: str, default: str) -> str:
    raw = os.environ.get(name)
    return raw.strip() if raw and raw.strip() else default


@dataclass(frozen=True)
class MailSettings:
    provider: str = "dummy"
    poll_interval_seconds: int = 300
    require_auth_for_routing: bool = False
    strip_plus_tags: bool = True
    max_page_size: int = 100
    default_page_size: int = 30
    undo_send_seconds: int = 5
    retention_days: int = 90
    attachment_max_bytes: int = 25 * 1024 * 1024
    quarantine_enabled: bool = True
    institute_name: str = DEFAULT_INSTITUTE
    portal_url: str = DEFAULT_PORTAL_URL
    footer_text: str = DEFAULT_FOOTER_TEXT
    unassigned_label: str = "Unassigned"

    @property
    def is_dummy(self) -> bool:
        return self.provider == "dummy"


@lru_cache(maxsize=1)
def get_mail_settings() -> MailSettings:
    return MailSettings(
        provider=_text("MAIL_PROVIDER", "dummy"),
        poll_interval_seconds=_number("MAIL_POLL_INTERVAL_SECONDS", 300),
        require_auth_for_routing=_flag("MAIL_REQUIRE_AUTH_FOR_ROUTING", False),
        strip_plus_tags=_flag("MAIL_STRIP_PLUS_TAGS", True),
        max_page_size=_number("MAIL_MAX_PAGE_SIZE", 100),
        default_page_size=_number("MAIL_DEFAULT_PAGE_SIZE", 30),
        undo_send_seconds=_number("MAIL_UNDO_SEND_SECONDS", 5),
        retention_days=_number("MAIL_RETENTION_DAYS", 90),
        attachment_max_bytes=_number(
            "MAIL_ATTACHMENT_MAX_BYTES", 25 * 1024 * 1024
        ),
        quarantine_enabled=_flag("MAIL_QUARANTINE_ENABLED", True),
        institute_name=_text("MAIL_INSTITUTE_NAME", DEFAULT_INSTITUTE),
        portal_url=_text("MAIL_PORTAL_URL", DEFAULT_PORTAL_URL),
        footer_text=os.environ.get("MAIL_FOOTER_TEXT") or DEFAULT_FOOTER_TEXT,
        unassigned_label=_text("MAIL_UNASSIGNED_LABEL", "Unassigned"),
    )


def reset_mail_settings() -> None:
    get_mail_settings.cache_clear()
