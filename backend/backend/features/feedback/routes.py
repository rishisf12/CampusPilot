"""Feedback API: students submit text + an optional file; admin reads and replies.

Name, phone and email are snapshotted from the profile/account at submit time,
so the admin "feedback responses" view always shows who wrote what even if the
student later edits their profile. Phone lives on the profile (single source of
truth): if the student types one here and the profile has none, it is saved
back to the profile.

An admin reply is stored per feedback and returned with it, so it appears at
the bottom of the student's own feedback entry - where it was written, not in
a separate inbox.
"""
import logging
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlmodel import Session, select

from core.config import settings
from core.database import get_session
from models import Feedback, FeedbackReply, User, UserProfile
from core.deps import get_current_admin, get_current_user
from features.profile.service import get_profile_for_user
from core.files import save_upload

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Feedback"])

#: What a feedback attachment may be. Executables and scripts are never accepted.
ALLOWED_ATTACHMENT_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt", ".csv"}


class ReplyBody(BaseModel):
    message: str


class FeedbackResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str] = None
    email: str
    message: str
    attachment_original: Optional[str] = None
    attachment_size: Optional[int] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


def _replies_for(session: Session, feedback_id: int) -> List[dict]:
    rows = session.exec(
        select(FeedbackReply)
        .where(FeedbackReply.feedback_id == feedback_id)
        .order_by(FeedbackReply.id.asc())
    ).all()
    return [
        {
            "id": row.id,
            "message": row.message,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


def _to_response(session: Session, item: Feedback) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "phone": item.phone,
        "email": item.email,
        "message": item.message,
        "attachment_original": item.attachment_original,
        "attachment_size": item.attachment_size,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "replies": _replies_for(session, item.id),
    }


def _display_name(profile: UserProfile, user: User) -> str:
    parts = [profile.first_name or "", profile.last_name or ""]
    full = " ".join(part for part in parts if part).strip()
    return full or user.full_name or user.username or ""


@router.post("/", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    message: str = Form(..., min_length=1, max_length=5000),
    name: Optional[str] = Form(default=None),
    phone: Optional[str] = Form(default=None),
    email: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Submit feedback text with an optional file attachment."""
    profile = get_profile_for_user(session, user)

    clean_message = (message or "").strip()
    if not clean_message:
        raise HTTPException(status_code=400, detail="Feedback text is required.")

    clean_phone = (phone or "").strip() or (profile.phone or "").strip() or None
    # A phone typed here is worth keeping: the profile owns contact details.
    if clean_phone and clean_phone != (profile.phone or ""):
        profile.phone = clean_phone
        session.add(profile)

    clean_name = (name or "").strip() or _display_name(profile, user)
    clean_email = (email or "").strip() or user.email

    stored_name: Optional[str] = None
    original_name: Optional[str] = None
    size_bytes: Optional[int] = None
    if file is not None and file.filename:
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Attachments accept {', '.join(sorted(ALLOWED_ATTACHMENT_EXTENSIONS))}, got '{ext}'.",
            )
        saved = save_upload(file, "feedback")
        size_bytes = saved.stat().st_size
        if size_bytes > settings.max_upload_mb * 1024 * 1024:
            saved.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400,
                detail=f"File too large: {size_bytes / 1024 / 1024:.1f} MB > {settings.max_upload_mb} MB limit.",
            )
        stored_name = saved.name
        original_name = file.filename

    item = Feedback(
        user_id=user.id,
        name=clean_name,
        phone=clean_phone,
        email=clean_email,
        message=clean_message,
        attachment_filename=stored_name,
        attachment_original=original_name,
        attachment_size=size_bytes,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    logger.info("Feedback submitted by user %s", user.username)
    return _to_response(session, item)


@router.get("/mine", response_model=List[dict])
def my_feedback(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """The signed-in student's own submissions, newest first, with admin replies."""
    items = session.exec(
        select(Feedback).where(Feedback.user_id == user.id).order_by(Feedback.id.desc())
    ).all()
    return [_to_response(session, item) for item in items]


@router.get("/responses", response_model=List[dict])
def all_feedback(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """Every feedback response, newest first, with admin replies.

    Admin-only: this backs the admin "feedback responses" section.
    """
    items = session.exec(select(Feedback).order_by(Feedback.id.desc())).all()
    return [_to_response(session, item) for item in items]


@router.post("/{feedback_id}/reply", status_code=status.HTTP_201_CREATED)
def reply_to_feedback(
    feedback_id: int,
    body: ReplyBody,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """Answer one feedback as admin. Appears under the student's entry."""
    item = session.exec(select(Feedback).where(Feedback.id == feedback_id)).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Feedback not found.")

    clean = (body.message or "").strip()
    if not clean:
        raise HTTPException(status_code=400, detail="Reply text is required.")
    if len(clean) > 5000:
        raise HTTPException(status_code=400, detail="Reply is too long (max 5000 characters).")

    reply = FeedbackReply(feedback_id=item.id, admin_user_id=admin.id, message=clean)
    session.add(reply)
    session.commit()
    session.refresh(reply)
    logger.info("Admin %s replied to feedback %s", admin.username, item.id)
    return {
        "id": reply.id,
        "message": reply.message,
        "created_at": reply.created_at.isoformat() if reply.created_at else None,
    }
