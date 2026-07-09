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


def _extract_response_value(item: Any) -> Any:
    if item is None:
        return None
    if hasattr(item, 'structured_output'):
        structured = getattr(item, 'structured_output')
        if structured is not None:
            return structured
    if hasattr(item, 'output'):
        output = getattr(item, 'output')
        if output is not None:
            return output
    return item


async def run_runner_and_get_response(maybe_awaitable) -> Any:
    """Consume a coroutine, async generator, or sync generator and return the final meaningful response.

    If a coroutine is provided, it is awaited and the result returned.
    If an async generator is provided, it is iterated and the last meaningful response value returned.
    If a sync generator is provided, it is iterated and the last meaningful response value returned.
    Otherwise the value is returned directly.
    """
    # Async generator (async for ...)
    if inspect.isasyncgen(maybe_awaitable):
        last_item = None
        last_response = None
        async for item in maybe_awaitable:
            if inspect.isawaitable(item) or inspect.iscoroutine(item):
                item = await item
            last_item = item
            last_response = _extract_response_value(item)
        return last_response if last_response is not None else last_item

    # Sync generator
    if inspect.isgenerator(maybe_awaitable):
        last_item = None
        last_response = None
        loop = asyncio.get_running_loop()
        for item in maybe_awaitable:
            if inspect.isawaitable(item) or inspect.iscoroutine(item):
                item = await item
            last_item = item
            last_response = _extract_response_value(item)
        return last_response if last_response is not None else last_item

    # Awaitables (coroutines, futures, or objects implementing __await__)
    if inspect.isawaitable(maybe_awaitable):
        result = await maybe_awaitable
        return _extract_response_value(result)

    # Fallback: return as-is
    return _extract_response_value(maybe_awaitable)
