"""Token bucket rate limiter for LLM providers."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""

    rate: float  # tokens per second
    capacity: int  # maximum tokens
    tokens: float = field(default=0)
    last_refill: float = field(default_factory=time.monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens from the bucket.
        Returns wait time in seconds (0 if acquired immediately).
        """
        async with self.lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return 0.0
            # Calculate wait time
            deficit = tokens - self.tokens
            wait_time = deficit / self.rate
            # Don't actually consume - let caller retry
            return wait_time

    async def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens without waiting."""
        async with self.lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now


class RateLimiter:
    """Per-provider rate limiter with concurrency cap."""

    def __init__(self, max_rpm: int = 30, max_concurrency: int = 5):
        self.max_rpm = max_rpm
        self.max_concurrency = max_concurrency
        self.buckets: Dict[str, TokenBucket] = {}
        self.semaphores: Dict[str, asyncio.Semaphore] = {}

    def get_bucket(self, provider: str) -> TokenBucket:
        """Get or create token bucket for a provider."""
        if provider not in self.buckets:
            self.buckets[provider] = TokenBucket(
                rate=self.max_rpm / 60.0,  # tokens per second
                capacity=self.max_rpm,
            )
        return self.buckets[provider]

    def get_semaphore(self, provider: str) -> asyncio.Semaphore:
        """Get or create semaphore for concurrency control."""
        if provider not in self.semaphores:
            self.semaphores[provider] = asyncio.Semaphore(self.max_concurrency)
        return self.semaphores[provider]

    async def acquire(self, provider: str, tokens: int = 1) -> float:
        """Acquire rate limit for a provider."""
        bucket = self.get_bucket(provider)
        return await bucket.acquire(tokens)

    async def execute_with_limit(self, provider: str, func, *args, **kwargs):
        """Execute a function with rate limiting and concurrency control."""
        semaphore = self.get_semaphore(provider)
        async with semaphore:
            wait_time = await self.acquire(provider)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            return await func(*args, **kwargs)
