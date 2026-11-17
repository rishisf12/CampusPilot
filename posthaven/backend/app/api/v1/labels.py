from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.db.session import get_session
from app.core.deps import CurrentUser, SessionDep
from app.models.label import Label, LabelRead

router = APIRouter(prefix="/labels", tags=["labels"])

@router.get("", response_model=list[LabelRead])
async def list_labels(current_user: CurrentUser, session: SessionDep):
    result = await session.exec(select(Label).where(Label.user_id == current_user.id).order_by(Label.name))
    return result.all()

@router.post("", response_model=LabelRead, status_code=status.HTTP_201_CREATED)
async def create_label(current_user: CurrentUser, session: SessionDep, name: str, color: str = "#6b7280"):
    label = Label(user_id=current_user.id, name=name, color=color)
    session.add(label)
    await session.commit()
    await session.refresh(label)
    return label

@router.delete("/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_label(current_user: CurrentUser, session: SessionDep, label_id: UUID):
    label = await session.get(Label, label_id)
    if not label or label.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label not found")
    await session.delete(label)
    await session.commit()
    return None
