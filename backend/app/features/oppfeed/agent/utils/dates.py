"""Date parsing utilities."""

from datetime import datetime, timezone, timedelta
from typing import Optional

import dateparser

# India Standard Time timezone
IST = timezone(timedelta(hours=5, minutes=30))


def parse_deadline(text: str, default_tz: timezone = IST) -> Optional[datetime]:
    """
    Parse a deadline from text using dateparser.
    Returns timezone-aware datetime or None.
    """
    if not text:
        return None

    try:
        # Try dateparser with various settings
        parsed = dateparser.parse(
            text,
            settings={
                "RETURN_AS_TIMEZONE_AWARE": True,
                "PREFER_DAY_OF_MONTH": "last",
                "PREFER_DATES_FROM": "future",
                "RELATIVE_BASE": datetime.now(default_tz),
            },
        )

        if parsed and parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=default_tz)

        return parsed

    except Exception:
        return None


def is_future_deadline(deadline: Optional[datetime], tz: timezone = IST) -> bool:
    """Check if deadline is in the future."""
    if not deadline:
        return False

    now = datetime.now(tz)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=tz)

    return deadline > now


def days_until_deadline(deadline: Optional[datetime], tz: timezone = IST) -> Optional[int]:
    """Calculate days until deadline."""
    if not deadline:
        return None

    now = datetime.now(tz)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=tz)

    delta = deadline - now
    return max(0, delta.days)


def format_deadline_countdown(deadline: Optional[datetime], tz: timezone = IST) -> str:
    """Format deadline as countdown string."""
    days = days_until_deadline(deadline, tz)
    if days is None:
        return "No deadline"
    if days == 0:
        return "Closes today"
    if days == 1:
        return "Closes in 1 day"
    if days <= 30:
        return f"Closes in {days} days"
    months = days // 30
    if months == 1:
        return "Closes in 1 month"
    return f"Closes in {months} months"
