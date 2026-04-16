from app.services.obsidian_context_service import ObsidianContextService


def test_obsidian_context_service_heartbeat_and_event_flow() -> None:
    svc = ObsidianContextService()
    heartbeat = svc.heartbeat(
        user_id="default-user",
        space_id=None,
        session_id="s1",
        active_note_path="Wiki/Test.md",
        active_note_title="Test",
    )
    assert heartbeat["status"] == "ok"

    event = svc.ingest_event(
        user_id="default-user",
        space_id=None,
        session_id="s1",
        event={"event_type": "selection", "note_path": "Wiki/Test.md", "selection": "hello"},
    )
    assert event["status"] == "accepted"
    assert event["recent_events"] == 1

    snapshot = svc.get_session(user_id="default-user", space_id=None, session_id="s1")
    assert snapshot.plugin_connected is True
    assert snapshot.active_note_path == "Wiki/Test.md"
    assert len(snapshot.recent_events) == 1


def test_obsidian_context_service_rejects_unknown_event_type() -> None:
    svc = ObsidianContextService()
    try:
        svc.ingest_event(
            user_id="default-user",
            space_id=None,
            session_id="s1",
            event={"event_type": "unknown", "note_path": "Wiki/Test.md"},
        )
    except ValueError as exc:
        assert "Unsupported Obsidian event type" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported event type.")
