"""Shared Obsidian context session management for transports (REST/gRPC)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Any, Dict, Optional
from uuid import uuid4

from app.config import get_settings

_ALLOWED_EVENT_TYPES = {"open", "click", "selection", "navigate"}


@dataclass
class ObsidianSessionSnapshot:
    session_id: str
    user_id: str
    space_id: Optional[str]
    active_note_path: Optional[str]
    active_note_title: Optional[str]
    active_selection: Optional[str]
    recent_events: list[Dict[str, Any]]
    last_event_at: Optional[str]
    plugin_connected: bool
    last_heartbeat_at: Optional[str]
    last_heartbeat_age_ms: Optional[int]


class ObsidianContextService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._sessions: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def session_key(user_id: str, space_id: Optional[str], session_id: Optional[str]) -> str:
        return f"{user_id}:{space_id or 'global'}:{session_id or 'default'}"

    @staticmethod
    def assert_plugin_secret(plugin_secret: Optional[str]) -> None:
        settings = get_settings()
        required = (settings.obsidian_plugin_shared_secret or "").strip()
        if not required:
            return
        provided = (plugin_secret or "").strip()
        if not provided or provided != required:
            raise ValueError("Invalid Obsidian plugin secret.")

    def heartbeat(
        self,
        *,
        user_id: str,
        space_id: Optional[str],
        session_id: Optional[str],
        active_note_path: Optional[str] = None,
        active_note_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        key = self.session_key(user_id, space_id, session_id)
        with self._lock:
            session = self._sessions.get(key) or {
                "session_id": session_id or "default",
                "user_id": user_id,
                "space_id": space_id,
                "active_note_path": None,
                "active_note_title": None,
                "active_selection": None,
                "recent_events": [],
                "last_event_at": None,
                "last_event_id": None,
                "last_heartbeat_at": None,
            }
            session["last_heartbeat_at"] = now
            if active_note_path:
                session["active_note_path"] = active_note_path
            if active_note_title:
                session["active_note_title"] = active_note_title
            self._sessions[key] = session
        return {"status": "ok", "session_id": session_id or "default"}

    def ingest_event(
        self,
        *,
        user_id: str,
        space_id: Optional[str],
        session_id: Optional[str],
        event: Dict[str, Any],
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        event_type = str(event.get("event_type", "")).strip().lower()
        if event_type not in _ALLOWED_EVENT_TYPES:
            raise ValueError(f"Unsupported Obsidian event type: {event.get('event_type')}")

        event_payload = {
            "event_id": event.get("event_id") or str(uuid4()),
            "event_type": event_type,
            "note_path": event.get("note_path"),
            "note_title": event.get("note_title"),
            "selection": event.get("selection"),
            "clicked_target": event.get("clicked_target"),
            "cursor_line": event.get("cursor_line"),
            "event_ts_ms": event.get("event_ts_ms") or int(time.time() * 1000),
            "metadata": event.get("metadata") or {},
            "received_at": now,
        }
        key = self.session_key(user_id, space_id, session_id)
        with self._lock:
            session = self._sessions.get(key) or {
                "session_id": session_id or "default",
                "user_id": user_id,
                "space_id": space_id,
                "active_note_path": None,
                "active_note_title": None,
                "active_selection": None,
                "recent_events": [],
                "last_event_at": None,
                "last_event_id": None,
                "last_heartbeat_at": None,
            }
            if session.get("last_event_id") == event_payload["event_id"]:
                return {"status": "deduplicated", "session_id": session["session_id"]}
            session["last_event_id"] = event_payload["event_id"]
            session["active_note_path"] = event_payload["note_path"]
            session["active_note_title"] = event_payload["note_title"] or session.get("active_note_title")
            if event_payload["selection"] is not None:
                session["active_selection"] = event_payload["selection"]
            session["last_event_at"] = now
            session["last_heartbeat_at"] = now
            recent = list(session.get("recent_events") or [])
            recent.append(event_payload)
            session["recent_events"] = recent[-25:]
            self._sessions[key] = session
            recent_count = len(session["recent_events"])
        return {
            "status": "accepted",
            "session_id": session_id or "default",
            "active_note_path": event_payload["note_path"],
            "recent_events": recent_count,
        }

    def get_session(
        self,
        *,
        user_id: str,
        space_id: Optional[str],
        session_id: Optional[str],
    ) -> ObsidianSessionSnapshot:
        now = datetime.utcnow()
        key = self.session_key(user_id, space_id, session_id)

        def heartbeat_age_ms(value: Optional[str]) -> Optional[int]:
            if not value:
                return None
            try:
                then = datetime.fromisoformat(value)
                return int((now - then).total_seconds() * 1000)
            except Exception:
                return None

        with self._lock:
            existing = self._sessions.get(key)
            if not existing:
                return ObsidianSessionSnapshot(
                    session_id=session_id or "default",
                    user_id=user_id,
                    space_id=space_id,
                    active_note_path=None,
                    active_note_title=None,
                    active_selection=None,
                    recent_events=[],
                    last_event_at=None,
                    plugin_connected=False,
                    last_heartbeat_at=None,
                    last_heartbeat_age_ms=None,
                )
            age = heartbeat_age_ms(existing.get("last_heartbeat_at"))
            return ObsidianSessionSnapshot(
                session_id=existing.get("session_id", session_id or "default"),
                user_id=existing.get("user_id", user_id),
                space_id=existing.get("space_id", space_id),
                active_note_path=existing.get("active_note_path"),
                active_note_title=existing.get("active_note_title"),
                active_selection=existing.get("active_selection"),
                recent_events=list(existing.get("recent_events") or []),
                last_event_at=existing.get("last_event_at"),
                plugin_connected=bool(age is not None and age <= 10_000),
                last_heartbeat_at=existing.get("last_heartbeat_at"),
                last_heartbeat_age_ms=age,
            )
