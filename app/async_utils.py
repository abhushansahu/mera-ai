"""Helpers for safely bridging sync and async code."""

from __future__ import annotations

import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Coroutine, TypeVar

T = TypeVar("T")

_bridge_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="async-bridge")


def run_coroutine_sync(coro: Coroutine[object, object, T]) -> T:
    """Run an async coroutine from sync code, even if an event loop is already running."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    def _runner() -> T:
        return asyncio.run(coro)

    future: Future[T] = _bridge_executor.submit(_runner)
    return future.result()
