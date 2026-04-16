"""gRPC server implementation for local sidecar transport."""

from __future__ import annotations

import json
import logging
from json import JSONDecodeError
from typing import Optional

import grpc

from app.services.obsidian_context_service import (
    ObsidianContextService,
    ObsidianPluginAuthError,
)
from app.transport.grpc.generated import sidecar_pb2, sidecar_pb2_grpc

logger = logging.getLogger(__name__)


class SidecarContextServicer(sidecar_pb2_grpc.SidecarContextServiceServicer):
    def __init__(self, context_service: ObsidianContextService) -> None:
        self.context_service = context_service

    async def Heartbeat(
        self,
        request: sidecar_pb2.HeartbeatRequest,
        context: grpc.aio.ServicerContext,
    ) -> sidecar_pb2.HeartbeatResponse:
        try:
            self.context_service.assert_plugin_secret(request.plugin_secret or None)
            payload = self.context_service.heartbeat(
                user_id=request.user_id or "default-user",
                space_id=request.space_id or None,
                session_id=request.session_id or None,
                active_note_path=request.active_note_path or None,
                active_note_title=request.active_note_title or None,
            )
            return sidecar_pb2.HeartbeatResponse(
                status=payload["status"],
                session_id=payload["session_id"],
            )
        except ObsidianPluginAuthError as exc:
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("gRPC heartbeat failed")
            await context.abort(grpc.StatusCode.INTERNAL, str(exc))

    async def IngestEvent(
        self,
        request: sidecar_pb2.IngestEventRequest,
        context: grpc.aio.ServicerContext,
    ) -> sidecar_pb2.IngestEventResponse:
        try:
            self.context_service.assert_plugin_secret(request.plugin_secret or None)
            metadata = {}
            if request.event.metadata_json:
                try:
                    metadata = json.loads(request.event.metadata_json)
                except JSONDecodeError as exc:
                    raise ValueError("event.metadata_json must contain valid JSON.") from exc
            event = {
                "event_id": request.event.event_id or None,
                "event_type": request.event.event_type,
                "note_path": request.event.note_path,
                "note_title": request.event.note_title or None,
                "selection": request.event.selection or None,
                "clicked_target": request.event.clicked_target or None,
                "cursor_line": request.event.cursor_line or None,
                "event_ts_ms": request.event.event_ts_ms or None,
                "metadata": metadata,
            }
            payload = self.context_service.ingest_event(
                user_id=request.user_id or "default-user",
                space_id=request.space_id or None,
                session_id=request.session_id or None,
                event=event,
            )
            return sidecar_pb2.IngestEventResponse(
                status=payload["status"],
                session_id=payload["session_id"],
                active_note_path=payload.get("active_note_path", "") or "",
                recent_events=int(payload.get("recent_events", 0)),
            )
        except ObsidianPluginAuthError as exc:
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, str(exc))
        except ValueError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("gRPC ingest event failed")
            await context.abort(grpc.StatusCode.INTERNAL, str(exc))

    async def GetSession(
        self,
        request: sidecar_pb2.GetSessionRequest,
        context: grpc.aio.ServicerContext,
    ) -> sidecar_pb2.GetSessionResponse:
        try:
            snapshot = self.context_service.get_session(
                user_id=request.user_id or "default-user",
                space_id=request.space_id or None,
                session_id=request.session_id or None,
            )
            events = [
                sidecar_pb2.SessionEvent(
                    event_id=str(evt.get("event_id", "")),
                    event_type=str(evt.get("event_type", "")),
                    note_path=str(evt.get("note_path", "")),
                    note_title=str(evt.get("note_title", "") or ""),
                    selection=str(evt.get("selection", "") or ""),
                    clicked_target=str(evt.get("clicked_target", "") or ""),
                    cursor_line=int(evt.get("cursor_line") or 0),
                    event_ts_ms=int(evt.get("event_ts_ms") or 0),
                    metadata_json=json.dumps(evt.get("metadata") or {}),
                    received_at=str(evt.get("received_at", "") or ""),
                )
                for evt in snapshot.recent_events
            ]
            return sidecar_pb2.GetSessionResponse(
                session_id=snapshot.session_id,
                user_id=snapshot.user_id,
                space_id=snapshot.space_id or "",
                active_note_path=snapshot.active_note_path or "",
                active_note_title=snapshot.active_note_title or "",
                active_selection=snapshot.active_selection or "",
                recent_events=events,
                last_event_at=snapshot.last_event_at or "",
                plugin_connected=snapshot.plugin_connected,
                last_heartbeat_at=snapshot.last_heartbeat_at or "",
                last_heartbeat_age_ms=int(snapshot.last_heartbeat_age_ms or 0),
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("gRPC get session failed")
            await context.abort(grpc.StatusCode.INTERNAL, str(exc))


async def serve(
    *,
    bind_address: str,
    context_service: Optional[ObsidianContextService] = None,
) -> grpc.aio.Server:
    service = context_service or ObsidianContextService()
    server = grpc.aio.server()
    sidecar_pb2_grpc.add_SidecarContextServiceServicer_to_server(
        SidecarContextServicer(service), server
    )
    server.add_insecure_port(bind_address)
    await server.start()
    logger.info("gRPC sidecar server listening on %s", bind_address)
    return server
