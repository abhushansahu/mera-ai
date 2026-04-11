"""Performance gate thresholds for migration decisions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PerformanceGates:
    orchestrator_mock_p95_ms: float = 750.0
    edge_proxy_p95_ms: float = 250.0
    max_memory_growth_mb: float = 150.0


GATES = PerformanceGates()
