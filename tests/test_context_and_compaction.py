from datetime import datetime

from app.context_monitor import context_utilization_percent
from app.memory_compaction import compact_memories
from app.memory_factory import MemoryManager


class DummyMemory(MemoryManager):
    def __init__(self) -> None:
        self.items: list[dict] = []

    async def store(self, user_id: str, text: str, metadata=None):  # type: ignore[override]
        self.items.append({"user_id": user_id, "text": text, "metadata": metadata or {}})

    async def search(self, user_id: str, query: str, limit: int = 5):  # type: ignore[override]
        return self.items[:limit]


def test_context_utilization_percent_is_reasonable() -> None:
    msgs = [{"role": "user", "content": "hello world"}]
    pct = context_utilization_percent(msgs)
    assert 0 < pct < 1  # tiny fraction of the full window


async def test_compact_memories_creates_snapshot() -> None:
    import asyncio
    memory = DummyMemory()
    await memory.store("u1", "First memory")
    await memory.store("u1", "Second memory")

    result = await compact_memories(memory, user_id="u1", model="openai/gpt-4o-mini", now=datetime(2025, 1, 1))
    assert result["source_count"] == 2
    assert "Snapshot" in result["snapshot"]


