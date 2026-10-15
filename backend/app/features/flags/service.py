"""Feature flag service."""
from __future__ import annotations
from typing import Optional
from sqlmodel import Session, select
from sqlalchemy import or_

from features.flags.models import FeatureFlag, FlagTarget


def list_flags(
    session: Session,
    search: Optional[str],
    enabled: Optional[bool],
    page: int,
    size: int,
) -> tuple[list[FeatureFlag], int]:
    stmt = select(FeatureFlag)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                FeatureFlag.key.ilike(like),
                FeatureFlag.name.ilike(like),
                FeatureFlag.description.ilike(like),
            )
        )
    if enabled is not None:
        stmt = stmt.where(FeatureFlag.enabled == enabled)

    total = len(session.exec(stmt).all())
    rows = session.exec(
        stmt.order_by(FeatureFlag.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return rows, total


def create_flag(session: Session, body, created_by: int) -> FeatureFlag:
    flag = FeatureFlag(
        key=body.key,
        name=body.name,
        description=body.description,
        enabled=body.enabled,
        rollout_percentage=body.rollout_percentage,
        target_roles=body.target_roles,
        target_user_ids=body.target_user_ids,
        target_platforms=body.target_platforms,
        target_app_versions=body.target_app_versions,
        created_by=created_by,
    )
    session.add(flag)
    session.commit()
    session.refresh(flag)

    for rule in body.target_rules:
        target = FlagTarget(
            flag_id=flag.id,
            attribute=rule.attribute,
            operator=rule.operator,
            values=rule.values,
        )
        session.add(target)
    session.commit()
    session.refresh(flag)
    return flag


def get_flag(session: Session, key: str) -> Optional[FeatureFlag]:
    return session.exec(select(FeatureFlag).where(FeatureFlag.key == key)).first()


def update_flag(session: Session, key: str, body, updated_by: int) -> Optional[FeatureFlag]:
    flag = session.exec(select(FeatureFlag).where(FeatureFlag.key == key)).first()
    if not flag:
        return None

    update_data = body.model_dump(exclude_unset=True, exclude={"target_rules"})
    for field, value in update_data.items():
        setattr(flag, field, value)

    if body.target_rules is not None:
        # Delete existing targets
        session.exec(
            select(FlagTarget).where(FlagTarget.flag_id == flag.id)
        ).all()
        for t in session.exec(
            select(FlagTarget).where(FlagTarget.flag_id == flag.id)
        ).all():
            session.delete(t)

        for rule in body.target_rules:
            target = FlagTarget(
                flag_id=flag.id,
                attribute=rule.attribute,
                operator=rule.operator,
                values=rule.values,
            )
            session.add(target)

    flag.updated_at = __import__('datetime').datetime.utcnow()
    session.add(flag)
    session.commit()
    session.refresh(flag)
    return flag


def delete_flag(session: Session, key: str) -> bool:
    flag = session.exec(select(FeatureFlag).where(FeatureFlag.key == key)).first()
    if not flag:
        return False
    session.delete(flag)
    session.commit()
    return True


def to_public(flag: FeatureFlag) -> dict:
    targets = session_exec_flag_targets(flag.id)
    return {
        "id": flag.id,
        "key": flag.key,
        "name": flag.name,
        "description": flag.description,
        "enabled": flag.enabled,
        "rollout_percentage": flag.rollout_percentage,
        "target_roles": flag.target_roles if isinstance(flag.target_roles, list) else [],
        "target_user_ids": flag.target_user_ids if isinstance(flag.target_user_ids, list) else [],
        "target_platforms": flag.target_platforms if isinstance(flag.target_platforms, list) else [],
        "target_app_versions": flag.target_app_versions if isinstance(flag.target_app_versions, list) else [],
        "target_rules": [
            {"attribute": t.attribute, "operator": t.operator, "values": t.values}
            for t in targets
        ],
        "created_at": flag.created_at.isoformat() if flag.created_at else None,
        "updated_at": flag.updated_at.isoformat() if flag.updated_at else None,
    }


def session_exec_flag_targets(flag_id: int):
    from sqlmodel import Session, select
    from core.database import engine
    from features.flags.models import FlagTarget

    with Session(engine) as session:
        return session.exec(
            select(FlagTarget).where(FlagTarget.flag_id == flag_id)
        ).all()