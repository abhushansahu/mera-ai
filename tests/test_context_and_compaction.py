from datetime import datetime

from app.context_monitor import context_utilization_percent
from app.memory_compaction import compact_memories
from app.memory_mem0 import Mem0Wrapper


class DummyMem0(Mem0Wrapper):
    def __init__(self) -> None:
        self.items: list[dict] = []

    def store(self, user_id: str, text: str, metadata=None):  # type: ignore[override]
        self.items.append({"user_id": user_id, "text": text, "metadata": metadata or {}})

    def search(self, user_id: str, query: str, limit: int = 5):  # type: ignore[override]
        return self.items[:limit]


def test_context_utilization_percent_is_reasonable() -> None:
    msgs = [{"role": "user", "content": "hello world"}]
    pct = context_utilization_percent(msgs)
    assert 0 < pct < 1  # tiny fraction of the full window


def test_compact_memories_creates_snapshot() -> None:
    mem0 = DummyMem0()
    mem0.store("u1", "First memory")
    mem0.store("u1", "Second memory")

    result = compact_memories(mem0, user_id="u1", model="openai/gpt-4o-mini", now=datetime(2025, 1, 1))
    assert result["source_count"] == 2
    assert "Snapshot" in result["snapshot"]


