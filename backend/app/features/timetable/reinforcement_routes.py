"""
Admin API for managing reinforcement patterns.

Allows viewing, adding, editing, and disabling correction patterns.
Patterns learned from PDF mistakes are stored here and auto-applied
during timetable parsing.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from core.deps import get_current_admin
from core.database import get_session
from models import ReinforcementPattern, User

import re

from features.timetable.reinforcement import ReinforcementPatternModel

router = APIRouter(tags=["Reinforcement Patterns"])


class PatternCreate(BaseModel):
    name: str
    pattern: str
    replacement: str
    description: str


class PatternUpdate(BaseModel):
    name: str | None = None
    pattern: str | None = None
    replacement: str | None = None
    description: str | None = None
    enabled: bool | None = None


class PatternTest(BaseModel):
    """A single candidate rule plus the text to preview it against.

    Deliberately not ``PatternCreate``: testing is a read-only preview, so it
    must not demand a name or a description it has no use for. It previously
    bound ``PatternCreate`` while the admin UI sent only a pattern and some
    text, so every click failed with 422.
    """

    pattern: str
    replacement: str
    text: str


@router.get("/")
def list_patterns(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    patterns = session.exec(select(ReinforcementPattern).order_by(ReinforcementPattern.name)).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "pattern": p.pattern,
            "replacement": p.replacement,
            "description": p.description,
            "enabled": p.enabled,
        }
        for p in patterns
    ]


@router.post("/")
def create_pattern(
    data: PatternCreate,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """Add a new correction pattern."""
    pattern = ReinforcementPattern(
        name=data.name,
        pattern=data.pattern,
        replacement=data.replacement,
        description=data.description,
        enabled=True,
    )
    session.add(pattern)
    session.commit()
    return {"id": pattern.id, "message": "Pattern created"}


@router.put("/{pattern_id}")
def update_pattern(
    pattern_id: int,
    data: PatternUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """Update an existing pattern."""
    pattern = session.get(ReinforcementPattern, pattern_id)
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    if data.name is not None:
        pattern.name = data.name
    if data.pattern is not None:
        pattern.pattern = data.pattern
    if data.replacement is not None:
        pattern.replacement = data.replacement
    if data.description is not None:
        pattern.description = data.description
    if data.enabled is not None:
        pattern.enabled = data.enabled
    session.add(pattern)
    session.commit()
    return {"message": "Pattern updated"}


@router.delete("/{pattern_id}")
def delete_pattern(
    pattern_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """Delete a pattern."""
    pattern = session.get(ReinforcementPattern, pattern_id)
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    session.delete(pattern)
    session.commit()
    return {"message": "Pattern deleted"}


@router.post("/test")
def test_pattern(
    data: PatternTest,
    _: User = Depends(get_current_admin),
):
    """Preview one candidate rule against sample text.

    Uses a throwaway model whose default rules are dropped, rather than the
    shared singleton. ``learn`` appends permanently, so testing through the
    singleton would leave every rule ever previewed active in this process's
    timetable parser until restart -- and the previews would compound, each one
    seeing the output of the last.
    """
    model = ReinforcementPatternModel()
    model.rules.clear()
    try:
        model.learn("__preview__", data.pattern, data.replacement, "__preview__")
    except re.error as exc:
        raise HTTPException(status_code=400, detail=f"Invalid regex: {exc}") from exc
    output = model.apply(data.text)
    return {"input": data.text, "output": output, "matched": output != data.text}