from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import get_session
from app.core.deps import CurrentUser, SessionDep
from app.services import rules as rules_service
from app.models.rule import RuleCreate, RuleUpdate, RuleRead

router = APIRouter(prefix="/rules", tags=["rules"])

@router.get("", response_model=list[RuleRead])
async def list_rules(current_user: CurrentUser, session: SessionDep):
    return await rules_service.list_rules(session, str(current_user.id))

@router.post("", response_model=RuleRead, status_code=status.HTTP_201_CREATED)
async def create_rule(current_user: CurrentUser, session: SessionDep, data: RuleCreate):
    return await rules_service.create_rule(session, str(current_user.id), data)

@router.patch("/{rule_id}", response_model=RuleRead)
async def update_rule(current_user: CurrentUser, session: SessionDep, rule_id: UUID, data: RuleUpdate):
    return await rules_service.update_rule(session, str(current_user.id), str(rule_id), data)

@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(current_user: CurrentUser, session: SessionDep, rule_id: UUID):
    await rules_service.delete_rule(session, str(current_user.id), str(rule_id))
    return None
