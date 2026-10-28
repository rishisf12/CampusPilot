"""Task API: a 24-hour personal task tracker for students.

A task lives for exactly two days. For the first 24 hours the student can
edit it and mark it complete; after that it only shows as expired, and 48
hours after creation the row is swept away by the next list read. The
optional alarm (remind_at) may only point into the upcoming 24 hours - never
into the past and never beyond a day ahead - which the server enforces: a
stale or hand-crafted payload cannot set an alarm outside that window.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from core.database import get_session
from models import Task, User
from core.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Task"])

#: A task is editable and completable for one day after creation.
TASK_LIFETIME = timedelta(hours=24)
#: One day later still, the row is deleted outright.
TASK_RETENTION = timedelta(hours=48)
#: An alarm may only point into the upcoming 24 hours.
ALARM_HORIZON = timedelta(hours=24)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    remind_at: Optional[datetime] = None


class TaskEdit(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    remind_at: Optional[datetime] = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _validate_remind_at(remind_at: Optional[datetime]) -> Optional[datetime]:
    """The alarm must land inside the upcoming 24 hours. A past time or one
    more than a day ahead is refused outright, not silently moved."""
    if remind_at is None:
        return None
    now = _utcnow()
    if remind_at.tzinfo is None:
        # A naive stamp is treated as UTC; the client always sends ISO with an
        # offset, so this only catches a hand-crafted payload.
        remind_at = remind_at.replace(tzinfo=timezone.utc)
    if remind_at <= now:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Alarm time must be in the future",
        )
    if remind_at > now + ALARM_HORIZON:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Alarm time cannot be more than 24 hours ahead",
        )
    return remind_at


def _purge(session: Session, user_id: int) -> None:
    """Delete this user's rows older than the 48-hour retention window."""
    cutoff = _utcnow() - TASK_RETENTION
    stale = session.exec(
        select(Task).where(Task.user_id == user_id, Task.created_at < cutoff)
    ).all()
    for row in stale:
        session.delete(row)
    if stale:
        session.commit()


def _serialize(task: Task, now: datetime) -> dict:
    if task.completed_at is not None:
        state = "completed"
    elif task.expires_at is not None and now >= task.expires_at:
        state = "expired"
    else:
        state = "active"
    return {
        "id": task.id,
        "title": task.title,
        "remind_at": task.remind_at.isoformat() if task.remind_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "expires_at": task.expires_at.isoformat() if task.expires_at else None,
        "status": state,
    }


def _owned_task(session: Session, task_id: int, user: User) -> Task:
    task = session.exec(
        select(Task).where(Task.id == task_id, Task.user_id == user.id)
    ).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.get("/")
def list_tasks(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """This user's tasks, newest first, with rows past retention deleted."""
    _purge(session, user.id)
    now = _utcnow()
    rows = session.exec(
        select(Task).where(Task.user_id == user.id).order_by(Task.id.desc())
    ).all()
    return {"tasks": [_serialize(t, now) for t in rows], "server_now": now.isoformat()}


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_task(
    data: TaskCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    remind = _validate_remind_at(data.remind_at)
    now = _utcnow()
    task = Task(
        user_id=user.id,
        title=data.title.strip(),
        remind_at=remind,
        created_at=now,
        expires_at=now + TASK_LIFETIME,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return _serialize(task, now)


@router.patch("/{task_id}")
def edit_task(
    task_id: int,
    data: TaskEdit,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    task = _owned_task(session, task_id, user)
    now = _utcnow()
    if task.completed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A completed task can no longer be edited",
        )
    if task.expires_at is not None and now >= task.expires_at:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task has expired and can no longer be edited",
        )
    if "title" in data.model_fields_set and data.title is not None:
        task.title = data.title.strip()
    if "remind_at" in data.model_fields_set:
        task.remind_at = _validate_remind_at(data.remind_at)
    session.add(task)
    session.commit()
    session.refresh(task)
    return _serialize(task, now)


@router.post("/{task_id}/complete")
def complete_task(
    task_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    task = _owned_task(session, task_id, user)
    now = _utcnow()
    if task.completed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Task is already completed"
        )
    if task.expires_at is not None and now >= task.expires_at:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task has expired and can no longer be completed",
        )
    task.completed_at = now
    session.add(task)
    session.commit()
    session.refresh(task)
    return _serialize(task, now)
