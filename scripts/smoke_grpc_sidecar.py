"""Smoke test: event -> daemon -> session visibility."""

from __future__ import annotations

import asyncio

import grpc

from app.transport.grpc.generated import sidecar_pb2, sidecar_pb2_grpc


async def main() -> None:
    target = "127.0.0.1:50051"
    async with grpc.aio.insecure_channel(target) as channel:
        stub = sidecar_pb2_grpc.SidecarContextServiceStub(channel)
        await stub.Heartbeat(
            sidecar_pb2.HeartbeatRequest(
                user_id="smoke-user",
                session_id="smoke-session",
                active_note_path="Wiki/Smoke.md",
                active_note_title="Smoke",
            )
        )
        await stub.IngestEvent(
            sidecar_pb2.IngestEventRequest(
                user_id="smoke-user",
                session_id="smoke-session",
                event=sidecar_pb2.ObsidianContextEvent(
                    event_type="open",
                    note_path="Wiki/Smoke.md",
                    note_title="Smoke",
                ),
            )
        )
        session = await stub.GetSession(
            sidecar_pb2.GetSessionRequest(user_id="smoke-user", session_id="smoke-session")
        )
        print(
            {
                "plugin_connected": session.plugin_connected,
                "active_note_path": session.active_note_path,
                "recent_events": len(session.recent_events),
            }
        )


if __name__ == "__main__":
    asyncio.run(main())
