from typing import Any

from fastapi.testclient import TestClient

from app.api import create_app


def test_boundary_research_accepts_obsidian_context_sources(monkeypatch: Any) -> None:
    app = create_app()
    captured: dict[str, Any] = {}

    class DummyBoundary:
        async def research(self, query: str, context_sources: list[Any]) -> str:
            captured["query"] = query
            captured["context_sources"] = context_sources
            return "ok"

    class DummyOrchestrator:
        context_boundary = DummyBoundary()

    app.state.orchestrator = DummyOrchestrator()  # type: ignore[attr-defined]

    client = TestClient(app)
    payload = {
        "query": "summarize note",
        "context_sources": [{"type": "OBSIDIAN", "path": "Wiki/Project.md", "extra": {"event_type": "open"}}],
    }
    response = client.post("/internal/boundary/context/research", json=payload)
    assert response.status_code == 200
    assert response.json()["content"] == "ok"
    assert captured["query"] == "summarize note"
    assert len(captured["context_sources"]) == 1
    assert captured["context_sources"][0].type == "OBSIDIAN"


def test_boundary_research_rejects_unknown_context_type(monkeypatch: Any) -> None:
    app = create_app()
    client = TestClient(app)
    payload = {
        "query": "summarize",
        "context_sources": [{"type": "UNKNOWN_KIND", "path": "abc"}],
    }
    response = client.post("/internal/boundary/context/research", json=payload)
    assert response.status_code == 500
    assert "Unsupported context source type" in response.json()["detail"]
