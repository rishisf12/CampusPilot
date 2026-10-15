"""Remote config routes."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel

from core.database import get_session
from core.deps import get_current_admin
from features.remote_config import service

router = APIRouter(prefix="/admin/remote-config", tags=["Admin - Remote Config"])


class RemoteConfigCreate(BaseModel):
    key: str
    value: dict
    value_type: str = "json"
    description: Optional[str] = None
    schema_json: Optional[dict] = None
    schema_version: int = 1
    is_public: bool = False


class RemoteConfigUpdate(BaseModel):
    value: Optional[dict] = None
    value_type: Optional[str] = None
    description: Optional[str] = None
    schema_json: Optional[dict] = None
    schema_version: Optional[int] = None
    is_public: Optional[bool] = None


class RemoteConfigResponse(BaseModel):
    id: int
    key: str
    value: dict
    value_type: str
    description: Optional[str]
    schema_json: Optional[dict]
    schema_version: int
    is_public: bool
    updated_by: Optional[int]
    updated_at: str


class RemoteConfigListResponse(BaseModel):
    total: int
    page: int
    size: int
    configs: list[RemoteConfigResponse]


class ConfigHistoryResponse(BaseModel):
    schema_version: int
    value: dict
    value_type: str
    changed_by: Optional[int]
    change_reason: Optional[str]
    created_at: str


@router.get("", response_model=RemoteConfigListResponse)
def admin_list_remote_configs(
    public_only: bool = False,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    page = max(1, page)
    size = max(1, min(size, 100))
    rows, total = service.list_remote_configs(session, public_only, page, size)
    return {
        "total": total,
        "page": page,
        "size": size,
        "configs": [service.to_public(r) for r in rows],
    }


@router.post("", response_model=RemoteConfigResponse, status_code=201)
def admin_create_remote_config(
    body: RemoteConfigCreate,
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    config, error = service.set_remote_config(
        session, body.key, body.value,
        value_type=body.value_type,
        description=body.description,
        schema_json=body.schema_json,
        schema_version=body.schema_version,
        is_public=body.is_public,
        updated_by=admin.id,
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    return service.to_public(config)


@router.get("/{key}", response_model=RemoteConfigResponse)
def admin_get_remote_config(
    key: str,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    config = service.get_remote_config(session, key)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    return service.to_public(config)


@router.patch("/{key}", response_model=RemoteConfigResponse)
def admin_update_remote_config(
    key: str,
    body: RemoteConfigUpdate,
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    config = service.get_remote_config(session, key)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    update_data = body.model_dump(exclude_unset=True)
    config, error = service.set_remote_config(
        session, key, update_data.get("value", config.value),
        value_type=update_data.get("value_type", config.value_type),
        description=update_data.get("description", config.description),
        schema_json=update_data.get("schema_json", config.schema_json),
        schema_version=update_data.get("schema_version", config.schema_version),
        is_public=update_data.get("is_public", config.is_public),
        updated_by=admin.id,
        change_reason="Manual update via admin",
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    return service.to_public(config)


@router.post("/{key}/rollback", response_model=RemoteConfigResponse)
def admin_rollback_remote_config(
    key: str,
    version: int,
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    config, error = service.rollback_remote_config(session, key, version, admin.id)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return service.to_public(config)


@router.get("/{key}/history")
def admin_get_remote_config_history(
    key: str,
    limit: int = 50,
    session: Session = Depends(get_session),
    _: None = Depends(get_current_admin),
):
    history = service.get_remote_config_history(session, key, limit)
    return {"history": history}