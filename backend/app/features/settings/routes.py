"""Per-user settings API.

`GET /settings` returns the stored document (empty when nothing has been saved),
`PATCH /settings` merges a partial document into it, and `DELETE /settings` clears
it. The key names and their types belong to the frontend registry; the server
stores what it is sent rather than validating against a list it would have to be
kept in step with.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from core.database import get_session
from core.deps import get_current_user
from features.settings import service
from features.settings.service import SettingsError
from models import User

router = APIRouter(prefix="/settings", tags=["Settings"])


class SettingsPatch(BaseModel):
    """A partial settings document.

    Wrapped in an object rather than being a bare map so the route keeps a stable
    shape if a query parameter or metadata field is added later.
    """

    settings: Dict[str, Any] = Body(default_factory=dict)


@router.get("")
def read_settings(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """This user's stored settings.

    Returns `{}` rather than 404 when nothing has been saved: the frontend falls
    back to its registry defaults, so a fresh account renders correctly with no
    row at all.
    """
    return {"settings": service.get_settings(session, user.id)}


@router.patch("")
def update_settings(
    body: SettingsPatch,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Merge settings into this user's document and return the whole thing.

    A value of `null` removes that setting, which is how "back to default" is
    expressed without the client needing to know the default.
    """
    try:
        merged = service.patch_settings(session, user.id, body.settings)
    except SettingsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"settings": merged}


@router.delete("")
def clear_settings(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Remove every stored setting for this user."""
    service.reset_settings(session, user.id)
    return {"settings": {}}