import asyncio
import json
from typing import AsyncIterator, Callable

from starlette.concurrency import run_in_threadpool


async def sse_stream(
    poll_fn: Callable[[], dict], *, interval: float = 1.0, max_iterations: int = 600
) -> AsyncIterator[bytes]:
    """Generic SSE loop: calls `poll_fn()` (a plain sync function that opens
    its own DB session) roughly every `interval` seconds, and yields an
    `event:`/`data:` frame whenever the returned dict changes. Stops once
    `poll_fn()` returns a dict with a truthy "terminal" key.

    DB-polling, not in-process pub/sub — deliberately: uvicorn may run
    multiple worker processes, and an in-memory queue written by one worker
    is invisible to another worker's SSE handler for the same job.
    """
    last_payload: dict | None = None
    for _ in range(max_iterations):
        payload = await run_in_threadpool(poll_fn)
        if payload != last_payload:
            event = payload.get("event", "stage")
            yield f"event: {event}\ndata: {json.dumps(payload)}\n\n".encode()
            last_payload = payload
        if payload.get("terminal"):
            return
        await asyncio.sleep(interval)
    yield b'event: error\ndata: {"error": "timed out waiting for job"}\n\n'
