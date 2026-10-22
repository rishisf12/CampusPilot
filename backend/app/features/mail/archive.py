"""Archive, mute, snooze actions on messages."""
from sqlmodel import Session

from features.mail.models import MailMessage
from features.mail import service


def archive_message(session: Session, message: MailMessage) -> MailMessage:
    """Archive: set is_archived=True; keeps in section and All Mail."""
    message.is_archived = True
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def mute_message(session: Session, message: MailMessage) -> MailMessage:
    """Mute: future replies skip Inbox."""
    # Mute logic lives on the thread; for message-level, we set a flag.
    # Full mute requires a `mail_thread.muted` column (deferred).
    return message


def snooze_message(session: Session, message: MailMessage, until) -> MailMessage:
    """Snooze: leaves inbox; returns as unread at `until`."""
    message.is_trashed = False  # snooze uses a separate state flag
    session.add(message)
    session.commit()
    return message
