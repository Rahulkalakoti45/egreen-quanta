"""In-process fan-out pub/sub for Server-Sent Events."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any

from app.core.logging import get_logger

log = get_logger("egreen.realtime")

_MAX_QUEUE = 200


class InProcessBroker:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    async def publish(self, message: dict[str, Any]) -> None:
        dead: list[asyncio.Queue] = []
        for q in list(self._subscribers):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.discard(q)
            log.warning("realtime_subscriber_dropped_slow")

    @contextlib.asynccontextmanager
    async def subscription(self) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_MAX_QUEUE)
        self._subscribers.add(q)
        try:
            yield q
        finally:
            self._subscribers.discard(q)


broker = InProcessBroker()
