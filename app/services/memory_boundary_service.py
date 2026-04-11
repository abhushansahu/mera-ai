"""Memory boundary adapter built on top of ChromaMemoryAdapter."""

from __future__ import annotations

from typing import List, Optional

from app.adapters.chroma import ChromaMemoryAdapter
from app.boundaries import MemoryBoundary, MemoryRecord


class ChromaMemoryBoundary(MemoryBoundary):
    def __init__(self, memory: ChromaMemoryAdapter) -> None:
        self.memory = memory

    async def search(self, user_id: str, query: str, limit: int = 5) -> List[MemoryRecord]:
        results = await self.memory.search(user_id=user_id, query=query, limit=limit)
        return [
            MemoryRecord(text=item.text, metadata=item.metadata, score=float(item.score or 0.0))
            for item in results
        ]

    async def store(self, user_id: str, text: str, metadata: Optional[dict] = None) -> None:
        await self.memory.store(user_id=user_id, text=text, metadata=metadata)
