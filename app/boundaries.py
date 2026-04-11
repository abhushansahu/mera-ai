"""Language-agnostic boundary contracts for core services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class MemoryRecord:
    text: str
    metadata: Dict[str, Any]
    score: float


class MemoryBoundary(Protocol):
    async def search(self, user_id: str, query: str, limit: int = 5) -> List[MemoryRecord]:
        ...

    async def store(self, user_id: str, text: str, metadata: Optional[dict] = None) -> None:
        ...


class ContextBoundary(Protocol):
    async def research(self, query: str, context_sources: List[Any]) -> str:
        ...
