"""Context boundary adapter over MultiAgentCoordinator."""

from __future__ import annotations

from typing import List

from app.boundaries import ContextBoundary
from app.core import ContextSource
from app.multi_agent_context_system import ContextSpecification, MultiAgentCoordinator
from app.services.context_source_mapper import to_coordinator_sources


class CoordinatorContextBoundary(ContextBoundary):
    def __init__(self, coordinator: MultiAgentCoordinator) -> None:
        self.coordinator = coordinator

    async def research(self, query: str, context_sources: List[ContextSource]) -> str:
        coordinator_sources = to_coordinator_sources(context_sources)
        if not coordinator_sources:
            return ""
        spec = ContextSpecification(query=query, sources=coordinator_sources)
        return await self.coordinator.research_with_context(spec)
