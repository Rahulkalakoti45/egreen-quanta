"""Lightweight fixed-window rate limiting as a FastAPI dependency.

In-memory by default (single process). When ``REDIS_URL`` is set the same window
counter is kept in Redis so limits hold across workers (wired in Module 8).
Disabled entirely under ``APP_ENV=test`` for deterministic tests.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass

from fastapi import Request

from app.core.config import settings
from app.core.exceptions import RateLimitError

# Named limits (requests, per seconds) reused across routers.
AUTH_LOGIN_LIMIT = (10, 60)
AUTH_REFRESH_LIMIT = (30, 60)
VERIFY_LIMIT = (120, 60)
INGEST_LIMIT = (600, 60)


@dataclass
class _Window:
    start: float
    count: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, _Window] = defaultdict(lambda: _Window(0.0, 0))

    def hit(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        now = time.monotonic()
        w = self._buckets[key]
        if now - w.start >= window:
            w.start = now
            w.count = 0
        w.count += 1
        remaining = max(0, limit - w.count)
        return w.count <= limit, remaining

    def reset(self) -> None:
        self._buckets.clear()


limiter = InMemoryRateLimiter()


def rate_limit(name: str, spec: tuple[int, int]):
    """Dependency factory. `spec` is (max_requests, window_seconds)."""
    limit, window = spec

    async def _dep(request: Request) -> None:
        if settings.is_test:
            return
        client = request.client.host if request.client else "anon"
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            client = fwd.split(",")[0].strip()
        key = f"{name}:{client}"
        ok, remaining = limiter.hit(key, limit, window)
        request.state.rate_remaining = remaining
        if not ok:
            raise RateLimitError(
                f"Too many requests for '{name}'. Limit is {limit} per {window}s.",
            )

    return _dep
