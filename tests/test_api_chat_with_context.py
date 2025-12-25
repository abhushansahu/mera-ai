from typing import Any, Dict, List

from fastapi.testclient import TestClient

from app.api import create_app


def test_chat_accepts_context_sources(monkeypatch: Any) -> None:
    app = create_app()

    captured: Dict[str, Any] = {}

    # Patch the orchestrator inside the app to capture context_sources.
    original_orchestrator = app.dependency_overrides.get("orchestrator", None)

    class DummyOrchestrator:
        def process_query(
            self,
            user_id: str,
            query: str,
            preferred_model: str | None,
            db: Any,
            context_sources: List[Dict[str, str]] | None = None,
        ) -> str:
            captured["user_id"] = user_id
            captured["query"] = query
            captured["context_sources"] = context_sources
            return "ok"

    # FastAPI doesn't expose orchestrator as a dependency, so we replace on the app object.
    app.dependency_overrides.clear()
    app.state.orchestrator = DummyOrchestrator()  # type: ignore[attr-defined]

    client = TestClient(app)
    payload = {
        "user_id": "u1",
        "query": "Hi",
        "context_sources": [{"type": "DIRECTORY", "path": "./src"}],
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    assert response.json()["answer"] == "ok"
    assert captured["context_sources"] == [{"type": "DIRECTORY", "path": "./src"}]


