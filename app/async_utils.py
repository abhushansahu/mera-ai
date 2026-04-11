"""Helpers for safely bridging sync and async code."""

from __future__ import annotations

import asyncio
from concurrent.futures import Future
from threading import Thread
from typing import Coroutine, TypeVar

T = TypeVar("T")

_loop_ready = Future[asyncio.AbstractEventLoop]()


def _start_bridge_loop() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _loop_ready.set_result(loop)
    loop.run_forever()


_bridge_thread = Thread(target=_start_bridge_loop, name="async-bridge", daemon=True)
_bridge_thread.start()


def run_coroutine_sync(coro: Coroutine[object, object, T]) -> T:
    """Run an async coroutine from sync code, even if an event loop is already running."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    bridge_loop = _loop_ready.result()
    future = asyncio.run_coroutine_threadsafe(coro, bridge_loop)
    return future.result()
