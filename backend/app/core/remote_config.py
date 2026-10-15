"""Remote configuration management."""
from __future__ import annotations
from typing import Any, Optional
from dataclasses import dataclass
from sqlmodel import Session, select
import json


@dataclass
class RemoteConfig:
    key: str
    value: Any
    value_type: str
    description: Optional[str]
    schema_json: Optional[dict]
    schema_version: int
    is_public: bool
    updated_by: Optional[int]
    updated_at: Any


class RemoteConfigStore:
    """In-memory remote config store with validation."""

    def __init__(self) -> None:
        self._configs: dict[str, RemoteConfig] = {}
        self._loaded = False

    def load(self, session: Session) -> None:
        """Load all configs from database."""
        from models import RemoteConfig as RCModel

        configs = session.exec(select(RCModel)).all()

        self._configs = {}
        for c in configs:
            self._configs[c.key] = RemoteConfig(
                key=c.key,
                value=c.value,
                value_type=c.value_type,
                description=c.description,
                schema_json=c.schema_json if isinstance(c.schema_json, dict) else None,
                schema_version=c.schema_version,
                is_public=c.is_public,
                updated_by=c.updated_by,
                updated_at=c.updated_at,
            )
        self._loaded = True

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value."""
        if not self._loaded:
            return default
        config = self._configs.get(key)
        return config.value if config else default

    def get_all(self, public_only: bool = False) -> dict[str, Any]:
        """Get all config values."""
        if not self._loaded:
            return {}
        result = {}
        for key, config in self._configs.items():
            if public_only and not config.is_public:
                continue
            result[key] = config.value
        return result

    def get_with_meta(self, key: str) -> Optional[RemoteConfig]:
        """Get config with metadata."""
        if not self._loaded:
            return None
        return self._configs.get(key)

    def validate_value(self, key: str, value: Any, schema_json: Optional[dict]) -> tuple[bool, Optional[str]]:
        """Validate a value against the schema."""
        if not schema_json:
            return True, None

        # Simple JSON Schema validation (subset)
        try:
            import jsonschema
            jsonschema.validate(value, schema_json)
            return True, None
        except ImportError:
            # jsonschema not installed, skip validation
            return True, None
        except Exception as e:
            return False, str(e)

    def set(
        self,
        session: Session,
        key: str,
        value: Any,
        *,
        value_type: str = "json",
        description: Optional[str] = None,
        schema_json: Optional[dict] = None,
        schema_version: int = 1,
        is_public: bool = False,
        updated_by: Optional[int] = None,
        change_reason: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """Set a config value with validation and history."""
        from models import RemoteConfig as RCModel, RemoteConfigHistory as RCHModel

        # Validate against existing schema
        existing = self._configs.get(key)
        schema = schema_json or (existing.schema_json if existing else None)
        valid, error = self.validate_value(key, value, schema)
        if not valid:
            return False, error

        # Save to history if exists
        if existing:
            session.add(RCHModel(
                config_key=key,
                value=existing.value,
                value_type=existing.value_type,
                schema_version=existing.schema_version,
                changed_by=updated_by,
                change_reason=change_reason,
            ))

        # Upsert
        config = session.exec(select(RCModel).where(RCModel.key == key)).first()
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
            config = RCModel(
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
        self._configs[key] = RemoteConfig(
            key=config.key,
            value=config.value,
            value_type=config.value_type,
            description=config.description,
            schema_json=config.schema_json if isinstance(config.schema_json, dict) else None,
            schema_version=config.schema_version,
            is_public=config.is_public,
            updated_by=config.updated_by,
            updated_at=config.updated_at,
        )
        return True, None

    def rollback(
        self,
        session: Session,
        key: str,
        target_version: int,
        *,
        updated_by: Optional[int] = None,
    ) -> tuple[bool, Optional[str]]:
        """Rollback to a previous version."""
        from models import RemoteConfigHistory as RCHModel

        history = session.exec(
            select(RCHModel)
            .where(RCHModel.config_key == key)
            .where(RCHModel.schema_version == target_version)
        ).first()

        if not history:
            return False, f"Version {target_version} not found for {key}"

        return self.set(
            session,
            key,
            history.value,
            value_type=history.value_type,
            schema_version=history.schema_version,
            updated_by=updated_by,
            change_reason=f"Rollback to version {target_version}",
        )

    def get_history(self, session: Session, key: str, limit: int = 50) -> list[dict]:
        """Get config history."""
        from models import RemoteConfigHistory as RCHModel

        rows = session.exec(
            select(RCHModel)
            .where(RCHModel.config_key == key)
            .order_by(RCHModel.created_at.desc())
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


remote_config_store = RemoteConfigStore()