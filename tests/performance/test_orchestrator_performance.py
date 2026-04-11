"""Performance smoke tests for core orchestration path."""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core import Memory
from app.orchestrator import CrewAIOrchestrator
from tests.performance.thresholds import GATES


class _DummyMemory:
    async def search(self, user_id: str, query: str, limit: int = 5) -> list[Memory]:
        return [Memory(text=f"memory for {query}", metadata={"user_id": user_id}, score=0.9)]

    async def store(self, user_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        return None


class _DummyObsidian:
    async def search(self, query: str, limit: int = 5) -> list[dict[str, str]]:
        return [{"path": "Wiki/note.md", "content": f"obsidian context for {query}"}]


class _DummyCoordinator:
    async def research_with_context(self, spec: Any) -> str:
        return f"context for {spec.query}"


class _DummyCrew:
    def __init__(self, agents: list[Any], tasks: list[Any], process: Any, verbose: bool) -> None:
        self.tasks = tasks

    def kickoff(self) -> SimpleNamespace:
        return SimpleNamespace(tasks_output=[task.output.raw for task in self.tasks])


def _fake_create_agents_for_space(**kwargs: Any) -> tuple[object, object, object]:
    return object(), object(), object()


def _fake_create_tasks_for_workflow(**kwargs: Any) -> tuple[Any, Any, Any]:
    return (
        SimpleNamespace(output=SimpleNamespace(raw="research-output")),
        SimpleNamespace(output=SimpleNamespace(raw="plan-output")),
        SimpleNamespace(output=SimpleNamespace(raw="final-answer")),
    )


@pytest.mark.asyncio
@pytest.mark.performance
async def test_orchestrator_p95_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep mocked orchestration latency within a tight budget."""
    monkeypatch.setattr("app.orchestrator.Crew", _DummyCrew)
    monkeypatch.setattr("app.orchestrator.create_agents_for_space", _fake_create_agents_for_space)
    monkeypatch.setattr("app.orchestrator.create_tasks_for_workflow", _fake_create_tasks_for_workflow)

    orchestrator = CrewAIOrchestrator(
        memory=_DummyMemory(),
        obsidian=_DummyObsidian(),
        coordinator=_DummyCoordinator(),
    )
    orchestrator._save_wiki_artifacts = AsyncMock(return_value={})  # type: ignore[method-assign]
    orchestrator.lint_space_wiki = AsyncMock(return_value={"summary": {}})  # type: ignore[method-assign]

    durations_ms: list[float] = []
    for i in range(20):
        started = time.perf_counter()
        result = await orchestrator.process_query(
            user_id="perf-user",
            query=f"perf query {i}",
            context_sources=[],
        )
        durations_ms.append((time.perf_counter() - started) * 1000)
        assert result.answer

    durations_ms.sort()
    p95_ms = durations_ms[int(len(durations_ms) * 0.95) - 1]
    assert p95_ms < GATES.orchestrator_mock_p95_ms
