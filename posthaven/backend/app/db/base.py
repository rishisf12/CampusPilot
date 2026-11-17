# Import all models so SQLModel metadata is populated for Alembic autogeneration.
from app.models.user import User  # noqa: F401
from app.models.token import RefreshToken  # noqa: F401
from app.models.setting import UserSetting  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401
from app.models.account import MailAccount, Identity  # noqa: F401
from app.models.folder import Folder  # noqa: F401
from app.models.message import Message  # noqa: F401
from app.models.thread import Thread  # noqa: F401
from app.models.attachment import Attachment  # noqa: F401
from app.models.label import Label, MessageLabel  # noqa: F401
from app.models.draft import Draft  # noqa: F401
from app.models.scheduled_send import ScheduledSend  # noqa: F401
from app.models.template import Template  # noqa: F401
from app.models.saved_search import SavedSearch  # noqa: F401
from app.models.snooze import Snooze  # noqa: F401
from app.models.reminder import Reminder  # noqa: F401
from app.models.rule import Rule  # noqa: F401
from app.models.vacation import VacationResponder  # noqa: F401
from app.models.contact import Contact, ContactGroup  # noqa: F401

from sqlmodel import SQLModel


Base = SQLModel.metadata
