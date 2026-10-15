"""Feature flag evaluation engine (in-memory, <5ms)."""
from __future__ import annotations
from typing import Any, Optional
from dataclasses import dataclass
from sqlmodel import Session, select
from models import User


@dataclass
class FlagTargetRule:
    attribute: str
    operator: str
    values: list[Any]


@dataclass
class FeatureFlag:
    key: str
    name: str
    description: Optional[str]
    enabled: bool
    rollout_percentage: int
    target_roles: list[str]
    target_user_ids: list[int]
    target_platforms: list[str]
    target_app_versions: list[str]
    target_rules: list[FlagTargetRule]


class FlagEngine:
    """In-memory feature flag engine with targeting."""

    def __init__(self) -> None:
        self._flags: dict[str, FeatureFlag] = {}
        self._loaded = False

    def load(self, session: Session) -> None:
        """Load all flags from database into memory."""
        from models import FeatureFlag as FlagModel, FlagTarget as TargetModel

        flags = session.exec(select(FlagModel)).all()
        targets = session.exec(select(TargetModel)).all()

        targets_by_flag: dict[int, list[TargetModel]] = {}
        for t in targets:
            targets_by_flag.setdefault(t.flag_id, []).append(t)

        self._flags = {}
        for f in flags:
            rules = [
                FlagTargetRule(
                    attribute=t.attribute,
                    operator=t.operator,
                    values=t.values if isinstance(t.values, list) else [],
                )
                for t in targets_by_flag.get(f.id, [])
            ]
            self._flags[f.key] = FeatureFlag(
                key=f.key,
                name=f.name,
                description=f.description,
                enabled=f.enabled,
                rollout_percentage=f.rollout_percentage,
                target_roles=f.target_roles if isinstance(f.target_roles, list) else [],
                target_user_ids=f.target_user_ids if isinstance(f.target_user_ids, list) else [],
                target_platforms=f.target_platforms if isinstance(f.target_platforms, list) else [],
                target_app_versions=f.target_app_versions if isinstance(f.target_app_versions, list) else [],
                target_rules=rules,
            )
        self._loaded = True

    def is_enabled(
        self,
        key: str,
        *,
        user: Optional[User] = None,
        platform: Optional[str] = None,
        app_version: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> bool:
        """Evaluate if a flag is enabled for the given context."""
        if not self._loaded:
            return False

        flag = self._flags.get(key)
        if not flag or not flag.enabled:
            return False

        # Explicit user targeting
        if user and user.id in flag.target_user_ids:
            return True

        # Role targeting
        if user and user.role and user.role.value in flag.target_roles:
            return True

        # Platform targeting
        if platform and platform in flag.target_platforms:
            return True

        # App version targeting (simple prefix match)
        if app_version and flag.target_app_versions:
            for v in flag.target_app_versions:
                if app_version.startswith(v.rstrip('*')):
                    return True

        # Complex targeting rules
        if flag.target_rules:
            context = self._build_context(user, platform, app_version)
            if not self._eval_rules(flag.target_rules, context):
                return False

        # Percentage rollout (deterministic by request_id or user_id)
        if flag.rollout_percentage < 100:
            identifier = request_id or (str(user.id) if user else "anonymous")
            if not self._in_rollout(identifier, flag.rollout_percentage):
                return False

        return True

    def _build_context(
        self,
        user: Optional[User],
        platform: Optional[str],
        app_version: Optional[str],
    ) -> dict[str, Any]:
        ctx: dict[str, Any] = {}
        if user:
            ctx["user_id"] = user.id
            ctx["user_role"] = user.role.value if user.role else None
            ctx["user_branch"] = getattr(user, 'branch', None)
            ctx["user_semester"] = getattr(user, 'semester', None)
        if platform:
            ctx["platform"] = platform
        if app_version:
            ctx["app_version"] = app_version
        return ctx

    def _eval_rules(self, rules: list[FlagTargetRule], context: dict[str, Any]) -> bool:
        """Evaluate all targeting rules (AND logic)."""
        for rule in rules:
            if not self._eval_rule(rule, context):
                return False
        return True

    def _eval_rule(self, rule: FlagTargetRule, context: dict[str, Any]) -> bool:
        value = context.get(rule.attribute)
        if value is None:
            return False

        vals = rule.values
        op = rule.operator

        if op == "in":
            return value in vals
        if op == "not_in":
            return value not in vals
        if op == "eq":
            return value == vals[0] if vals else False
        if op == "neq":
            return value != vals[0] if vals else False
        if op == "gt":
            return value > vals[0] if vals else False
        if op == "gte":
            return value >= vals[0] if vals else False
        if op == "lt":
            return value < vals[0] if vals else False
        if op == "lte":
            return value <= vals[0] if vals else False
        if op == "contains":
            return isinstance(value, str) and vals[0] in value
        if op == "starts_with":
            return isinstance(value, str) and value.startswith(vals[0])
        if op == "ends_with":
            return isinstance(value, str) and value.endswith(vals[0])
        return False

    def _in_rollout(self, identifier: str, percentage: int) -> bool:
        """Deterministic rollout using hash of identifier."""
        import hashlib
        hash_val = int(hashlib.sha256(identifier.encode()).hexdigest(), 16)
        return (hash_val % 100) < percentage

    def get_all(self) -> dict[str, FeatureFlag]:
        return self._flags.copy()

    def get(self, key: str) -> Optional[FeatureFlag]:
        return self._flags.get(key)


# Global instance
flag_engine = FlagEngine()


def evaluate_flag(
    key: str,
    *,
    user: Optional[User] = None,
    platform: Optional[str] = None,
    app_version: Optional[str] = None,
    request_id: Optional[str] = None,
) -> bool:
    """Convenience function for flag evaluation."""
    return flag_engine.is_enabled(
        key, user=user, platform=platform, app_version=app_version, request_id=request_id
    )