"""
Runner utilities to normalize different Runner.run return types.

Some ADK Runner implementations may return a coroutine, an async generator,
or a sync generator (streaming). This helper provides a single async
entrypoint that consumes any of those and returns the final response object.
"""
import inspect
import asyncio
from typing import Any


async def run_runner_and_get_response(maybe_awaitable) -> Any:
    """Consume a coroutine, async generator, or sync generator and return the last item.

    If a coroutine is provided, it is awaited and the result returned.
    If an async generator is provided, it is iterated and the last yielded value returned.
    If a sync generator is provided, it is iterated and the last yielded value returned.
    Otherwise the value is returned directly.
    """
    # Coroutine (awaitable)
    if asyncio.iscoroutine(maybe_awaitable):
        return await maybe_awaitable

    # Async generator
    if inspect.isasyncgen(maybe_awaitable):
        last = None
        async for item in maybe_awaitable:
            last = item
        return last

    # Sync generator
    if inspect.isgenerator(maybe_awaitable):
        last = None
        for item in maybe_awaitable:
            last = item
        return last

    # Plain value
    return maybe_awaitable
