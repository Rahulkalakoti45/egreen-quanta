"""Server-Sent Events: live alert / event stream (Module 8)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser
from app.core.logging import get_logger
from app.services.realtime import broker

router = APIRouter(prefix="/stream", tags=["stream"])
log = get_logger("egreen.stream")

_KEEPALIVE_SECONDS = 20


async def _event_source(request: Request) -> AsyncIterator[bytes]:
    async with broker.subscription() as queue:
        yield b": connected\n\n"
        while True:
            if await request.is_disconnected():
                break
            try:
                message = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_SECONDS)
            except TimeoutError:
                yield b": keepalive\n\n"
                continue
            payload = json.dumps(message, default=str)
            yield f"event: {message.get('type', 'message')}\ndata: {payload}\n\n".encode()


@router.get("/alerts")
async def alert_stream(request: Request, _: CurrentUser) -> StreamingResponse:
    return StreamingResponse(
        _event_source(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
