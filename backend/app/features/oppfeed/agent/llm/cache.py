"""LLM response cache - self-contained, avoids burning free quota."""

import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlmodel import Field

from ..base import AgentBase


class LLMCache(AgentBase, table=True):
    """Cache for LLM responses to avoid burning free quota.

    Self-contained model - no backend imports needed.
    """

    __tablename__ = "oppfeed_llm_cache"

    id: Optional[int] = Field(default=None, primary_key=True)
    cache_key: str = Field(index=True, unique=True, max_length=64)
    prompt_version: str = Field(max_length=50)
    provider: str = Field(max_length=50)
    model: str = Field(max_length=200)
    response_text: str = Field(max_length=50000)
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(index=True)


class LLMCacheManager:
    """Manages LLM response caching.

    Self-contained: defines its own LLMCache model, no backend imports needed.
    """

    def __init__(self, ttl_hours: int = 24):
        self.ttl_hours = ttl_hours

    @staticmethod
    def _as_utc_naive(value: datetime) -> datetime:
        """Normalize a datetime so stored and fresh values can be compared.

        SQLite keeps no timezone offset, so ``expires_at`` comes back naive while
        ``datetime.now(timezone.utc)`` is aware - comparing them directly raises
        ``TypeError: can't compare offset-naive and offset-aware datetimes``.
        """
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def _make_key(self, prompt_version: str, input_data: dict) -> str:
        """Create cache key from prompt version and input."""
        content = json.dumps({"v": prompt_version, "i": input_data}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    async def get(
        self, db, prompt_version: str, input_data: dict
    ) -> Optional[LLMCache]:
        """Get cached response if it exists and is not expired."""
        from sqlmodel import select

        key = self._make_key(prompt_version, input_data)
        statement = select(LLMCache).where(LLMCache.cache_key == key)
        result = (await db.exec(statement)).first()

        if result and self._as_utc_naive(result.expires_at) > self._as_utc_naive(
            datetime.now(timezone.utc)
        ):
            return result
        return None

    async def set(
        self,
        db,
        prompt_version: str,
        input_data: dict,
        response_text: str,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> LLMCache:
        """Store a response in cache."""
        key = self._make_key(prompt_version, input_data)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=self.ttl_hours)

        # Delete existing entry if any
        from sqlmodel import delete

        await db.exec(delete(LLMCache).where(LLMCache.cache_key == key))

        cache_entry = LLMCache(
            cache_key=key,
            prompt_version=prompt_version,
            provider=provider,
            model=model,
            response_text=response_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            expires_at=expires_at,
        )
        db.add(cache_entry)
        await db.commit()
        return cache_entry

    async def cleanup_expired(self, db) -> int:
        """Remove expired cache entries. Returns count deleted."""
        now = datetime.now(timezone.utc)
        from sqlmodel import delete

        statement = delete(LLMCache).where(LLMCache.expires_at <= now)
        result = await db.exec(statement)
        await db.commit()
        return result.rowcount or 0