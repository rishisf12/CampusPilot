"""Rate limiting for the unauthenticated collector.

A sliding-window counter, in-process. Redis-backed limiting would be the better
answer for a multi-replica deployment, and Redis is already a dependency for the
scan queue, but adding a Redis round-trip to the hot ingest path costs more than
it buys on the single-VPS deployment this is actually built for.

The consequence is stated rather than hidden: with N API replicas the effective
limit is N x the configured rate. That is acceptable for a rate limit whose job
is to stop a runaway client and a scanner probing for the endpoint, not to stop a
distributed attack - which a per-process limit never did anyway.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field


@dataclass
class _Window:
    hits: deque = field(default_factory=deque)


class SlidingWindowLimiter:
    """Per-key sliding window over a monotonic clock.

    Uses `time.monotonic()` rather than wall-clock time on purpose: a window
    that uses wall time collapses or extends unpredictably when NTP steps the
    clock, which during a sync is exactly when you least want the limiter to
    misbehave.
    """

    def __init__(self, limit: int, window_s: float = 60.0) -> None:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        self.limit = limit
        self.window_s = float(window_s)
        self._hits: dict[str, deque] = defaultdict(_Window().hits.__class__)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Record a hit and report whether it is within the limit."""
        now = time.monotonic()
        cutoff = now - self.window_s
        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            # Opportunistic cleanup. Without this the dict grows one entry per
            # distinct source forever, which is a memory leak driven directly
            # by whoever is scanning the endpoint.
            if not bucket and len(self._hits) > 4096:
                for k in [k for k, v in self._hits.items() if not v]:
                    self._hits.pop(k, None)
            return True

    def retry_after(self, key: str) -> int:
        """Seconds until the oldest hit leaves the window. At least 1."""
        with self._lock:
            bucket = self._hits.get(key)
            if not bucket:
                return 1
            wait = bucket[0] + self.window_s - time.monotonic()
        return max(1, int(wait) + 1)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


#: Batches per minute per source. Sized for a real client: the Android SDK
#: batches on network availability and flushes roughly every 30-60 seconds, so a
#: legitimate client sits well under this even while backgrounding and
#: foregrounding repeatedly.
COLLECT_BATCH_LIMIT = SlidingWindowLimiter(limit=30, window_s=60.0)

#: Crash reports are rarer and more expensive to store, so they get their own,
#: tighter budget. Separate on purpose: a client stuck in a crash loop must not
#: be able to exhaust the budget for ordinary telemetry.
CRASH_LIMIT = SlidingWindowLimiter(limit=10, window_s=60.0)

#: Auth endpoints: signup, verify-email, resend-code, login
#: 5 attempts per minute per IP, then 429
AUTH_LIMIT = SlidingWindowLimiter(limit=5, window_s=60.0)

#: Brute force detection: 20 failed logins per 5 minutes per IP triggers a signal
BRUTE_FORCE_LIMIT = SlidingWindowLimiter(limit=20, window_s=300.0)

#: OTP resend: 3 resends per 10 minutes per IP
OTP_RESEND_LIMIT = SlidingWindowLimiter(limit=3, window_s=600.0)