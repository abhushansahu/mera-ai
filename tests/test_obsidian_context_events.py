from fastapi.testclient import TestClient

from app.api import create_app


def test_obsidian_context_event_round_trip() -> None:
    app = create_app()
    client = TestClient(app)

    ingest_response = client.post(
        "/obsidian/context/events",
        json={
            "user_id": "default-user",
            "session_id": "default",
            "event": {
                "event_type": "open",
                "note_path": "Wiki/Architecture.md",
                "note_title": "Architecture",
                "event_ts_ms": 1234,
            },
        },
    )
    assert ingest_response.status_code == 200
    assert ingest_response.json()["status"] in {"accepted", "deduplicated"}

    session_response = client.get(
        "/obsidian/context/session",
        params={"user_id": "default-user", "session_id": "default"},
    )
    assert session_response.status_code == 200
    payload = session_response.json()
    assert payload["active_note_path"] == "Wiki/Architecture.md"
    assert len(payload["recent_events"]) >= 1


def test_obsidian_heartbeat_marks_plugin_connected() -> None:
    app = create_app()
    client = TestClient(app)

    heartbeat = client.post(
        "/obsidian/context/heartbeat",
        json={
            "user_id": "default-user",
            "session_id": "default",
            "active_note_path": "Wiki/Live.md",
            "active_note_title": "Live",
        },
    )
    assert heartbeat.status_code == 200
    assert heartbeat.json()["status"] == "ok"

    session_response = client.get(
        "/obsidian/context/session",
        params={"user_id": "default-user", "session_id": "default"},
    )
    assert session_response.status_code == 200
    payload = session_response.json()
    assert payload["plugin_connected"] is True
    assert payload["active_note_path"] == "Wiki/Live.md"
    assert payload["last_heartbeat_age_ms"] is not None


def test_obsidian_context_event_requires_secret_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://user:pass@localhost:5432/db")
    monkeypatch.setenv("OBSIDIAN_PLUGIN_SHARED_SECRET", "secret-123")
    from app.config import get_settings

    get_settings.cache_clear()
    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/obsidian/context/events",
        json={
            "user_id": "default-user",
            "session_id": "default",
            "event": {"event_type": "open", "note_path": "Wiki/Architecture.md"},
        },
    )
    assert response.status_code == 401

    heartbeat_response = client.post(
        "/obsidian/context/heartbeat",
        json={"user_id": "default-user", "session_id": "default"},
    )
    assert heartbeat_response.status_code == 401
