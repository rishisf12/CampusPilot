"""Remote config service."""
from __future__ import annotations
from typing import Optional
from sqlmodel import Session, select

from features.remote_config.models import RemoteConfig, RemoteConfigHistory


def list_remote_configs(
    session: Session,
    public_only: bool,
    page: int,
    size: int,
) -> tuple[list[RemoteConfig], int]:
    stmt = select(RemoteConfig)
    if public_only:
        stmt = stmt.where(RemoteConfig.is_public == True)

    total = len(session.exec(stmt).all())
    rows = session.exec(
        stmt.order_by(RemoteConfig.key)
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return rows, total


def get_remote_config(session: Session, key: str) -> Optional[RemoteConfig]:
    return session.exec(select(RemoteConfig).where(RemoteConfig.key == key)).first()


def set_remote_config(
    session: Session,
    key: str,
    value: dict,
    *,
    value_type: str = "json",
    description: Optional[str] = None,
    schema_json: Optional[dict] = None,
    schema_version: int = 1,
    is_public: bool = False,
    updated_by: Optional[int] = None,
    change_reason: Optional[str] = None,
) -> tuple[RemoteConfig, Optional[str]]:
    from core.remote_config import remote_config_store

    # Validate using the store
    existing = session.exec(select(RemoteConfig).where(RemoteConfig.key == key)).first()
    schema = schema_json or (existing.schema_json if existing else None)

    # Simple validation - in production use jsonschema
    # For now just basic type check
    if schema_json and schema_json.get("type"):
        expected_type = schema_json.get("type")
        if expected_type == "object" and not isinstance(value, dict):
            return None, f"Value must be an object, got {type(value).__name__}"
        elif expected_type == "array" and not isinstance(value, list):
            return None, f"Value must be an array, got {type(value).__name__}"
        elif expected_type == "string" and not isinstance(value, str):
            return None, f"Value must be a string, got {type(value).__name__}"
        elif expected_type == "number" and not isinstance(value, (int, float)):
            return None, f"Value must be a number, got {type(value).__name__}"
        elif expected_type == "boolean" and not isinstance(value, bool):
            return None, f"Value must be a boolean, got {type(value).__name__}"

    # Save to history if exists
    if existing:
        session.add(RemoteConfigHistory(
            config_key=key,
            value=existing.value,
            value_type=existing.value_type,
            schema_version=existing.schema_version,
            changed_by=updated_by,
            change_reason=change_reason or "Manual update via admin",
        ))

    # Upsert
    config = session.exec(select(RemoteConfig).where(RemoteConfig.key == key)).first()
    if config:
        config.value = value
        config.value_type = value_type
        config.description = description
        config.schema_json = schema_json
        config.schema_version = schema_version
        config.is_public = is_public
        config.updated_by = updated_by
        config.updated_at = __import__('datetime').datetime.utcnow()
    else:
        config = RemoteConfig(
            key=key,
            value=value,
            value_type=value_type,
            description=description,
            schema_json=schema_json,
            schema_version=schema_version,
            is_public=is_public,
            updated_by=updated_by,
        )
        session.add(config)

    session.commit()
    session.refresh(config)

    # Update in-memory cache
    remote_config_store._configs[key] = type('obj', (object,), {
        'key': config.key,
        'value': config.value,
        'value_type': config.value_type,
        'description': config.description,
        'schema_json': config.schema_json if isinstance(config.schema_json, dict) else None,
        'schema_version': config.schema_version,
        'is_public': config.is_public,
        'updated_by': config.updated_by,
        'updated_at': config.updated_at,
    })()

    return config, None


def rollback_remote_config(
    session: Session,
    key: str,
    target_version: int,
    updated_by: Optional[int] = None,
) -> tuple[RemoteConfig, Optional[str]]:
    history = session.exec(
        select(RemoteConfigHistory)
        .where(RemoteConfigHistory.config_key == key)
        .where(RemoteConfigHistory.schema_version == target_version)
    ).first()

    if not history:
        return None, f"Version {target_version} not found for {key}"

    return set_remote_config(
        session,
        key,
        history.value,
        value_type=history.value_type,
        schema_version=history.schema_version,
        updated_by=updated_by,
        change_reason=f"Rollback to version {target_version}",
    )


def get_remote_config_history(
    session: Session,
    key: str,
    limit: int = 50,
) -> list[dict]:
    rows = session.exec(
        select(RemoteConfigHistory)
        .where(RemoteConfigHistory.config_key == key)
        .order_by(RemoteConfigHistory.created_at.desc())
        .limit(limit)
    ).all()

    return [
        {
            "schema_version": r.schema_version,
            "value": r.value,
            "value_type": r.value_type,
            "changed_by": r.changed_by,
            "change_reason": r.change_reason,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def list_remote_configs(
    session: Session,
    public_only: bool,
    page: int,
    size: int,
) -> tuple[list[RemoteConfig], int]:
    stmt = select(RemoteConfig)
    if public_only:
        stmt = stmt.where(RemoteConfig.is_public == True)

    total = len(session.exec(stmt).all())
    rows = session.exec(
        stmt.order_by(RemoteConfig.key)
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return rows, total


def get_remote_config(session: Session, key: str) -> Optional[RemoteConfig]:
    return session.exec(select(RemoteConfig).where(RemoteConfig.key == key)).first()


def to_public(config: RemoteConfig) -> dict:
    return {
        "id": config.id,
        "key": config.key,
        "value": config.value,
        "value_type": config.value_type,
        "description": config.description,
        "schema_json": config.schema_json if isinstance(config.schema_json, dict) else None,
        "schema_version": config.schema_version,
        "is_public": config.is_public,
        "updated_by": config.updated_by,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }