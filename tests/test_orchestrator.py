from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.memory_mem0 import Mem0Wrapper
from app.multi_agent_context_system import MultiAgentCoordinator
from app.orchestrator import (
    UnifiedOrchestrator,
    _build_initial_state,
    _retrieve_mem0_node,
    _store_mem0_node,
    _research_node,
)


class DummySession:
    """Very small stand-in for a SQLAlchemy session for unit tests."""

    def __init__(self) -> None:
        self.added: List[Dict[str, Any]] = []
        self.committed: bool = False

    def add(self, obj: Any) -> None:
        self.added.append(obj)  # type: ignore[arg-type]

    def commit(self) -> None:
        self.committed = True


class DummyMem0(Mem0Wrapper):
    def __init__(self) -> None:
        self.stored: List[Dict[str, Any]] = []
        self.to_return: List[Dict[str, Any]] = []

    def store(self, user_id: str, text: str, metadata: Dict[str, Any] | None = None) -> None:  # type: ignore[override]
        self.stored.append({"user_id": user_id, "text": text, "metadata": metadata or {}})

    def search(self, user_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:  # type: ignore[override]
        return self.to_return


def test_build_initial_state() -> None:
    state = _build_initial_state("u1", "hello", "model-x")
    assert state["user_id"] == "u1"
    assert state["messages"][0]["content"] == "hello"


def test_mem0_retrieve_injects_context() -> None:
    mem0 = DummyMem0()
    mem0.to_return = [{"text": "User likes short answers."}]
    state = _build_initial_state("u1", "hello", "model-x")

    new_state = _retrieve_mem0_node(state, mem0)
    assert new_state["mem0_results"]
    assert new_state["messages"][0]["role"] == "system"


def test_mem0_store_persists_answer() -> None:
    mem0 = DummyMem0()
    state = _build_initial_state("u1", "hello", "model-x")
    state["answer"] = "Hi there"

    _store_mem0_node(state, mem0)
    assert mem0.stored


def test_orchestrator_process_query_monkeypatch(monkeypatch: Any) -> None:
    """Patch the graph to avoid real LLM calls in unit tests."""

    orch = UnifiedOrchestrator(mem0=DummyMem0(), coordinator=MultiAgentCoordinator.default())

    def fake_invoke(state: dict) -> dict:
        state["answer"] = "test-answer"
        state["messages"].append({"role": "assistant", "content": "test-answer"})
        return state

    orch._app.invoke = fake_invoke  # type: ignore[assignment]

    db: Session = DummySession()  # type: ignore[assignment]
    answer = orch.process_query("user-1", "Hi", None, db, context_sources=None)

    assert answer == "test-answer"


def test_research_node_uses_coordinator_when_context_sources_present() -> None:
    class DummyCoordinator(MultiAgentCoordinator):
        def __init__(self) -> None:  # type: ignore[override]
            # Bypass parent init
            pass

        def research_with_context(self, spec):  # type: ignore[override]
            return "AGENT_RESEARCH"

    state = _build_initial_state("u1", "hello", "model-x")
    state["context_sources"] = [{"type": "DIRECTORY", "path": "./src"}]
    coord = DummyCoordinator()

    new_state = _research_node(state, coord)
    assert new_state["research_output"] == "AGENT_RESEARCH"



