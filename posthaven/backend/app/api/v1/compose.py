from typing import Annotated, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.db.session import get_session
from app.core.deps import CurrentUser, SessionDep
from app.models.draft import Draft, DraftRead, DraftUpsert
from app.models.scheduled_send import ScheduledSend, ScheduledSendRead, SendStatus
from app.models.template import Template, TemplateRead, TemplateCreate
from app.models.account import MailAccount

class ScheduledSendCreateRequest(BaseModel):
    account_id: UUID
    to_json: str
    subject: str
    send_at: datetime
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    cc_json: Optional[str] = None
    bcc_json: Optional[str] = None
    identity_id: Optional[UUID] = None
    idempotency_key: Optional[str] = None

router = APIRouter(prefix="/compose", tags=["compose"])


# ---- Drafts ----
@router.get("/drafts", response_model=list[DraftRead])
async def list_drafts(
    current_user: CurrentUser,
    session: SessionDep,
):
    result = await session.exec(
        select(Draft).where(Draft.user_id == current_user.id).order_by(Draft.updated_at.desc())
    )
    return result.all()


@router.post("/drafts", response_model=DraftRead, status_code=status.HTTP_201_CREATED)
async def upsert_draft(
    current_user: CurrentUser,
    session: SessionDep,
    data: DraftUpsert,
):
    account = await session.get(MailAccount, data.account_id)
    if not account or account.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    result = await session.exec(
        select(Draft).where(Draft.user_id == current_user.id, Draft.account_id == data.account_id)
    )
    draft = result.first()
    if draft:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(draft, field, value)
    else:
        draft = Draft(user_id=current_user.id, **data.model_dump())
        session.add(draft)
    await session.commit()
    await session.refresh(draft)
    return draft


@router.delete("/drafts/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft(
    current_user: CurrentUser,
    session: SessionDep,
    draft_id: UUID,
):
    draft = await session.get(Draft, draft_id)
    if not draft or draft.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    await session.delete(draft)
    await session.commit()
    return None


# ---- Scheduled sends ----
@router.get("/scheduled", response_model=list[ScheduledSendRead])
async def list_scheduled(
    current_user: CurrentUser,
    session: SessionDep,
):
    result = await session.exec(
        select(ScheduledSend).where(ScheduledSend.user_id == current_user.id).order_by(ScheduledSend.send_at)
    )
    return result.all()


@router.post("/scheduled", response_model=ScheduledSendRead, status_code=status.HTTP_201_CREATED)
async def create_scheduled(
    current_user: CurrentUser,
    session: SessionDep,
    data: ScheduledSendCreateRequest,
):
    import uuid
    account = await session.get(MailAccount, data.account_id)
    if not account or account.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    key = data.idempotency_key or str(uuid.uuid4())
    scheduled = ScheduledSend(
        user_id=current_user.id,
        account_id=data.account_id,
        identity_id=data.identity_id,
        to_json=data.to_json,
        subject=data.subject,
        send_at=data.send_at,
        body_text=data.body_text,
        body_html=data.body_html,
        cc_json=data.cc_json,
        bcc_json=data.bcc_json,
        idempotency_key=key,
    )
    session.add(scheduled)
    await session.commit()
    await session.refresh(scheduled)
    return scheduled


# ---- Templates ----
@router.get("/templates", response_model=list[TemplateRead])
async def list_templates(
    current_user: CurrentUser,
    session: SessionDep,
):
    result = await session.exec(select(Template).where(Template.user_id == current_user.id))
    return result.all()


@router.post("/templates", response_model=TemplateRead, status_code=status.HTTP_201_CREATED)
async def create_template(
    current_user: CurrentUser,
    session: SessionDep,
    data: TemplateCreate,
):
    template = Template(user_id=current_user.id, **data.model_dump())
    session.add(template)
    await session.commit()
    await session.refresh(template)
    return template
