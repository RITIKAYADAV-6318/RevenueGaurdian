"""
Runner utilities to normalize different Runner.run return types.

Some ADK Runner implementations may return a coroutine, an async generator,
or a sync generator (streaming). This helper provides a single async
entrypoint that consumes any of those and returns the final response object.
"""
import inspect
import asyncio
from typing import Any

from google.genai import types


def make_new_message(text: str, role: str = "user") -> types.Content:
    """Constructs a Google GenAI Content object for Runner.run."""
    return types.Content(parts=[types.Part.from_text(text=text)], role=role)


async def run_runner_and_get_response(maybe_awaitable) -> Any:
    """Consume a coroutine, async generator, or sync generator and return the last item.

    If a coroutine is provided, it is awaited and the result returned.
    If an async generator is provided, it is iterated and the last yielded value returned.
    If a sync generator is provided, it is iterated and the last yielded value returned.
    Otherwise the value is returned directly.
    """
    # Awaitables (coroutines, futures, or objects implementing __await__)
    if inspect.isawaitable(maybe_awaitable):
        return await maybe_awaitable

    # Async generator (async for ...)
    if inspect.isasyncgen(maybe_awaitable):
        last = None
        async for item in maybe_awaitable:
            if inspect.isawaitable(item) or inspect.iscoroutine(item):
                last = await item
            else:
                last = item
        return last

    # Sync generator
    if inspect.isgenerator(maybe_awaitable):
        last = None
        loop = asyncio.get_event_loop()
        for item in maybe_awaitable:
            if inspect.isawaitable(item) or inspect.iscoroutine(item):
                if loop.is_running():
                    last = await item
                else:
                    last = loop.run_until_complete(item)
            else:
                last = item
        return last

    # Fallback: return as-is
    return maybe_awaitable
