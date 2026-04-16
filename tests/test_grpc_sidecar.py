import asyncio

import grpc

from app.config import get_settings
from app.services.obsidian_context_service import ObsidianContextService
from app.transport.grpc.generated import sidecar_pb2, sidecar_pb2_grpc
from app.transport.grpc.server import serve


async def _exercise_grpc_server() -> None:
    bind = "127.0.0.1:50061"
    server = await serve(bind_address=bind, context_service=ObsidianContextService())
    try:
        async with grpc.aio.insecure_channel(bind) as channel:
            stub = sidecar_pb2_grpc.SidecarContextServiceStub(channel)
            hb = await stub.Heartbeat(
                sidecar_pb2.HeartbeatRequest(
                    user_id="default-user",
                    session_id="grpc-test",
                    active_note_path="Wiki/G.md",
                    active_note_title="G",
                )
            )
            assert hb.status == "ok"
            ingest = await stub.IngestEvent(
                sidecar_pb2.IngestEventRequest(
                    user_id="default-user",
                    session_id="grpc-test",
                    event=sidecar_pb2.ObsidianContextEvent(
                        event_type="open",
                        note_path="Wiki/G.md",
                        note_title="G",
                    ),
                )
            )
            assert ingest.status in {"accepted", "deduplicated"}
            session = await stub.GetSession(
                sidecar_pb2.GetSessionRequest(user_id="default-user", session_id="grpc-test")
            )
            assert session.plugin_connected is True
            assert session.active_note_path == "Wiki/G.md"
    finally:
        await server.stop(0)


def test_grpc_sidecar_round_trip() -> None:
    asyncio.run(_exercise_grpc_server())


async def _exercise_grpc_auth_and_validation_errors() -> None:
    bind = "127.0.0.1:50062"
    server = await serve(bind_address=bind, context_service=ObsidianContextService())
    try:
        async with grpc.aio.insecure_channel(bind) as channel:
            stub = sidecar_pb2_grpc.SidecarContextServiceStub(channel)
            try:
                await stub.Heartbeat(
                    sidecar_pb2.HeartbeatRequest(
                        user_id="default-user",
                        session_id="grpc-auth-test",
                    )
                )
            except grpc.aio.AioRpcError as exc:
                assert exc.code() == grpc.StatusCode.UNAUTHENTICATED
            else:
                raise AssertionError("Expected UNAUTHENTICATED when plugin secret is required.")

            try:
                await stub.IngestEvent(
                    sidecar_pb2.IngestEventRequest(
                        user_id="default-user",
                        session_id="grpc-auth-test",
                        plugin_secret="secret-123",
                        event=sidecar_pb2.ObsidianContextEvent(
                            event_type="open",
                            note_path="Wiki/G.md",
                            metadata_json="{not-json}",
                        ),
                    )
                )
            except grpc.aio.AioRpcError as exc:
                assert exc.code() == grpc.StatusCode.INVALID_ARGUMENT
                assert "metadata_json" in (exc.details() or "")
            else:
                raise AssertionError("Expected INVALID_ARGUMENT for malformed metadata_json.")
    finally:
        await server.stop(0)


def test_grpc_sidecar_auth_and_validation_failures(monkeypatch) -> None:
    monkeypatch.setenv("OBSIDIAN_PLUGIN_SHARED_SECRET", "secret-123")
    get_settings.cache_clear()
    try:
        asyncio.run(_exercise_grpc_auth_and_validation_errors())
    finally:
        monkeypatch.delenv("OBSIDIAN_PLUGIN_SHARED_SECRET", raising=False)
        get_settings.cache_clear()
