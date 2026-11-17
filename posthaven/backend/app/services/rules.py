from __future__ import annotations

import json
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from fastapi import HTTPException, status

from app.models.message import Message
from app.models.rule import Rule, RuleCreate, RuleUpdate
from app.models.label import Label, MessageLabel


def evaluate_conditions(message: Message, conditions: list) -> bool:
    if not conditions:
        return True
    for cond in conditions:
        field = cond.get("field", "")
        operator = cond.get("operator", "contains")
        value = cond.get("value", "")

        if field == "from":
            msg_val = ""
            if message.from_json:
                try:
                    fj = json.loads(message.from_json) if isinstance(message.from_json, str) else message.from_json
                    msg_val = fj.get("address", "") if isinstance(fj, dict) else str(fj)
                except Exception:
                    msg_val = str(message.from_json)
        elif field == "to":
            msg_val = str(message.to_json or "")
        elif field == "subject":
            msg_val = message.subject or ""
        elif field == "has_attachment":
            msg_val = "yes" if message.has_attachments else "no"
        elif field == "size":
            msg_val = str(message.size or 0)
        else:
            msg_val = ""

        matched = False
        if operator == "contains":
            matched = value.lower() in msg_val.lower()
        elif operator == "not_contains":
            matched = value.lower() not in msg_val.lower()
        elif operator == "equals":
            matched = msg_val.lower() == value.lower()
        elif operator == "gt":
            try:
                matched = float(msg_val) > float(value)
            except Exception:
                matched = False
        elif operator == "lt":
            try:
                matched = float(msg_val) < float(value)
            except Exception:
                matched = False

        if not matched:
            return False
    return True


async def apply_actions(message: Message, actions: list, session: AsyncSession, user_id: str) -> bool:
    stop = False
    for action in actions:
        atype = action.get("type", "")
        params = action.get("params", {})

        if atype == "mark_read":
            flags = json.loads(message.flags) if message.flags else []
            if "\\Seen" not in flags:
                flags.append("\\Seen")
                message.flags = json.dumps(flags)
                session.add(message)
        elif atype == "star":
            flags = json.loads(message.flags) if message.flags else []
            if "\\Flagged" not in flags:
                flags.append("\\Flagged")
                message.flags = json.dumps(flags)
                session.add(message)
        elif atype == "delete":
            flags = json.loads(message.flags) if message.flags else []
            if "\\Deleted" not in flags:
                flags.append("\\Deleted")
                message.flags = json.dumps(flags)
                session.add(message)
        elif atype == "label":
            label_name = params.get("label", "")
            if label_name:
                result = session.exec(
                    select(Label).where(Label.user_id == user_id, Label.name == label_name)
                )
                label = result.first()
                if not label:
                    label = Label(user_id=user_id, name=label_name, color="#6b7280")
                    session.add(label)
                    await session.flush()
                link = session.exec(
                    select(MessageLabel).where(MessageLabel.message_id == message.id, MessageLabel.label_id == label.id)
                ).first()
                if not link:
                    session.add(MessageLabel(message_id=message.id, label_id=label.id))
        elif atype == "move":
            folder_id = params.get("folder_id")
            if folder_id:
                message.folder_id = folder_id
                session.add(message)
        elif atype == "stop":
            stop = True
    return stop


async def run_rules_on_message(
    session: AsyncSession,
    user_id: str,
    message: Message,
) -> None:
    result = await session.exec(
        select(Rule).where(Rule.user_id == user_id, Rule.enabled == True).order_by(Rule.order)
    )
    rules = result.all()
    for rule in rules:
        try:
            conditions = json.loads(rule.conditions) if isinstance(rule.conditions, str) else rule.conditions
            actions = json.loads(rule.actions) if isinstance(rule.actions, str) else rule.actions
        except Exception:
            continue
        if not evaluate_conditions(message, conditions):
            continue
        stop = await apply_actions(message, actions, session, user_id)
        if stop or rule.stop_on_match:
            break
    await session.commit()


async def list_rules(
    session: AsyncSession,
    user_id: str,
) -> list[Rule]:
    result = await session.exec(
        select(Rule).where(Rule.user_id == user_id).order_by(Rule.order)
    )
    return result.all()


async def create_rule(
    session: AsyncSession,
    user_id: str,
    data: RuleCreate,
) -> Rule:
    rule = Rule(user_id=user_id, **data.model_dump())
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule


async def update_rule(
    session: AsyncSession,
    user_id: str,
    rule_id: str,
    data: RuleUpdate,
) -> Rule:
    result = await session.exec(
        select(Rule).where(Rule.id == rule_id, Rule.user_id == user_id)
    )
    rule = result.first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule


async def delete_rule(
    session: AsyncSession,
    user_id: str,
    rule_id: str,
) -> None:
    result = await session.exec(
        select(Rule).where(Rule.id == rule_id, Rule.user_id == user_id)
    )
    rule = result.first()
    if rule:
        await session.delete(rule)
        await session.commit()

