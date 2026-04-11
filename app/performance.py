"""Shared performance helpers for timing and request correlation."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Dict, Iterator

_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def set_request_id(request_id: str) -> None:
    _request_id_var.set(request_id)


def get_request_id() -> str:
    return _request_id_var.get()


@dataclass
class TimingCollector:
    """Collect per-step timings for a request."""

    timings_ms: Dict[str, float] = field(default_factory=dict)

    @contextmanager
    def measure(self, key: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
        finally:
            self.timings_ms[key] = round((time.perf_counter() - started) * 1000, 2)

    def add(self, key: str, duration_ms: float) -> None:
        self.timings_ms[key] = round(duration_ms, 2)


def log_timing_summary(logger: logging.Logger, label: str, timings_ms: Dict[str, float]) -> None:
    total_ms = round(sum(timings_ms.values()), 2)
    logger.info(
        "%s | request_id=%s | total_ms=%s | steps=%s",
        label,
        get_request_id(),
        total_ms,
        timings_ms,
    )
