"""Context boundary adapter over MultiAgentCoordinator."""

from __future__ import annotations

from typing import List

from app.boundaries import ContextBoundary
from app.core import ContextSource
from app.multi_agent_context_system import (
    ContextSource as CoordinatorContextSource,
    ContextSourceType,
    ContextSpecification,
    MultiAgentCoordinator,
)


def _map_context_source_type(source_type: str) -> ContextSourceType | None:
    normalized = (source_type or "").strip().upper()
    aliases = {
        "FILE": ContextSourceType.FILE,
        "DIRECTORY": ContextSourceType.DIRECTORY,
        "URL": ContextSourceType.URL,
        "API": ContextSourceType.API,
        "DATABASE": ContextSourceType.DATABASE,
        "MEMORY": ContextSourceType.MEMORY,
    }
    return aliases.get(normalized)


def _to_coordinator_sources(context_sources: List[ContextSource]) -> List[CoordinatorContextSource]:
    mapped: List[CoordinatorContextSource] = []
    for src in context_sources:
        ctype = _map_context_source_type(src.type)
        if ctype is None:
            continue
        mapped.append(CoordinatorContextSource(type=ctype, path=src.path, extra=src.extra))
    return mapped


class CoordinatorContextBoundary(ContextBoundary):
    def __init__(self, coordinator: MultiAgentCoordinator) -> None:
        self.coordinator = coordinator

    async def research(self, query: str, context_sources: List[ContextSource]) -> str:
        coordinator_sources = _to_coordinator_sources(context_sources)
        if not coordinator_sources:
            return ""
        spec = ContextSpecification(query=query, sources=coordinator_sources)
        return await self.coordinator.research_with_context(spec)
