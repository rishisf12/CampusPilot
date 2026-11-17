from __future__ import annotations

import re
from datetime import datetime
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func
from sqlalchemy import text, or_
import sqlalchemy as sa

from app.models.message import Message
from app.models.saved_search import SavedSearch, SavedSearchCreate


def parse_query(query: str) -> dict:
    phrase_pattern = re.compile(r'"([^"]*)"')
    remaining = query
    phrases = []
    for m in phrase_pattern.finditer(query):
        phrases.append(m.group(1))
        remaining = remaining.replace(m.group(0), " ", 1)
    parts = [p for p in remaining.split() if p]
    filters = {}
    negations = {}
    free_terms = []
    for part in parts:
        if part.startswith("-"):
            inner = part[1:]
            if ":" in inner:
                key, _, val = inner.partition(":")
                negations.setdefault(key, []).append(val)
            else:
                free_terms.append(f"-{inner}")
        elif ":" in part:
            key, _, val = part.partition(":")
            key_lower = key.lower()
            if key_lower in ("is", "has"):
                combined = f"{key}:{val}".lower()
                filters.setdefault(combined, []).append(val)
            else:
                filters.setdefault(key_lower, []).append(val)
        else:
            free_terms.append(part)
    return {
        "filters": filters,
        "negations": negations,
        "free_terms": free_terms,
        "phrases": phrases,
    }


def build_search_conditions(parsed: dict) -> list:
    conditions = []
    filters = parsed.get("filters", {})
    negations = parsed.get("negations", {})
    free_terms = parsed.get("free_terms", [])
    phrases = parsed.get("phrases", [])
    for field in ("from", "to", "cc"):
        vals = filters.get(field, [])
        if vals:
            or_conds = []
            for v in vals:
                or_conds.append(getattr(Message, f"{field}_json").ilike(f"%{v}%"))
            conditions.append(or_(*or_conds))
    vals = filters.get("subject", [])
    if vals:
        conditions.append(Message.subject.ilike(f"%{' '.join(vals)}%"))
    is_filters = filters.get("is:unread", []) + filters.get("is:read", []) + \
                 filters.get("is:starred", []) + filters.get("is:important", [])
    for v in is_filters:
        key = v.lower()
        if key == "unread":
            conditions.append(~Message.flags.cast(sa.String).ilike("%\\Seen%"))
        elif key == "read":
            conditions.append(Message.flags.cast(sa.String).ilike("%\\Seen%"))
        elif key == "starred":
            conditions.append(Message.flags.cast(sa.String).ilike("%\\Flagged%"))
        elif key == "important":
            conditions.append(Message.flags.cast(sa.String).ilike("%\\Important%"))
    if filters.get("has:attachment"):
        conditions.append(Message.has_attachments == True)
    for key, col in (("before:", Message.received_at), ("after:", Message.received_at),
                     ("older_than:", Message.received_at), ("newer_than:", Message.received_at)):
        vals = filters.get(key, [])
        if vals:
            try:
                dt = datetime.fromisoformat(vals[-1])
                if key in ("before:", "older_than:"):
                    conditions.append(col < dt)
                else:
                    conditions.append(col > dt)
            except Exception:
                pass
    vals = filters.get("size:", [])
    if vals:
        try:
            size_str = vals[-1].lower()
            multiplier = 1
            if size_str.endswith("k"):
                multiplier = 1024
                size_str = size_str[:-1]
            elif size_str.endswith("m"):
                multiplier = 1024 * 1024
                size_str = size_str[:-1]
            conditions.append(Message.size >= int(size_str) * multiplier)
        except Exception:
            pass
    for key, vals in negations.items():
        if key == "from":
            conditions.append(~Message.from_json.cast(sa.String).ilike(f"%{vals[-1]}%"))
    all_terms = free_terms + phrases
    if all_terms:
        ts_query = " & ".join(all_terms)
        conditions.append(text("search_vector @@ plainto_tsquery('english', :q)").bindparams(q=ts_query))
    return conditions


async def search_messages(
    session: AsyncSession,
    user_id: str,
    query: str,
    folder_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    parsed = parse_query(query)
    conditions = build_search_conditions(parsed)
    conditions.append(Message.user_id == user_id)
    if folder_id:
        conditions.append(Message.folder_id == folder_id)
    q = select(Message).where(*conditions).order_by(Message.received_at.desc().nullslast())
    q = q.limit(limit).offset(offset)
    result = await session.exec(q)
    messages = result.all()
    count_q = select(func.count()).select_from(Message).where(*conditions)
    total = (await session.exec(count_q)).one()
    return {
        "messages": messages,
        "total": total,
        "query": query,
        "parsed": parsed,
    }


async def save_search(
    session: AsyncSession,
    user_id: str,
    data: SavedSearchCreate,
) -> SavedSearch:
    ss = SavedSearch(user_id=user_id, name=data.name, query=data.query)
    session.add(ss)
    await session.commit()
    await session.refresh(ss)
    return ss


async def list_saved_searches(
    session: AsyncSession,
    user_id: str,
) -> list[SavedSearch]:
    result = await session.exec(
        select(SavedSearch).where(SavedSearch.user_id == user_id).order_by(SavedSearch.created_at.desc())
    )
    return result.all()
