"""In-process broker + SSE endpoint."""

from __future__ import annotations

import asyncio
import json

import pytest
from app.api.v1.stream import _event_source
from app.services.realtime.broker import InProcessBroker, broker
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_broker_fans_out_to_all_subscribers() -> None:
    b = InProcessBroker()
    async with b.subscription() as q1, b.subscription() as q2:
        await b.publish({"type": "alert", "n": 1})
        assert (await asyncio.wait_for(q1.get(), 1))["n"] == 1
        assert (await asyncio.wait_for(q2.get(), 1))["n"] == 1
    assert b.subscriber_count == 0


async def test_broker_drops_slow_subscriber() -> None:
    b = InProcessBroker()
    async with b.subscription() as q:
        for i in range(300):  # queue maxsize is 200
            await b.publish({"n": i})
        assert b.subscriber_count == 0  # over-full queue was evicted
        _ = q


async def test_stream_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/stream/alerts")).status_code == 401


async def test_event_source_emits_connected_then_published() -> None:
    class _Req:
        async def is_disconnected(self) -> bool:
            return False

    gen = _event_source(_Req())  # type: ignore[arg-type]
    first = await asyncio.wait_for(gen.__anext__(), 1)
    assert first == b": connected\n\n"

    async def push() -> None:
        await asyncio.sleep(0.05)
        await broker.publish({"type": "alert", "id": "a1", "title": "boom"})

    task = asyncio.create_task(push())
    chunk = await asyncio.wait_for(gen.__anext__(), 2)
    await task
    text = chunk.decode()
    assert text.startswith("event: alert\n")
    assert json.loads(text.split("data: ", 1)[1].strip())["id"] == "a1"
    await gen.aclose()
