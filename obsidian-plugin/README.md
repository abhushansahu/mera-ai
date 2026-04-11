# Mera Context Bridge (Obsidian Plugin)

Streams Obsidian context events and heartbeat to a local Mera gRPC daemon so the assistant can stay aware of:

- active/open note
- clicks/navigation
- text selections
- live plugin presence (heartbeat)

## Dev Setup

1. Copy this folder into your vault plugin directory (`.obsidian/plugins/mera-context-bridge`).
2. Build TypeScript (`npm install && npm run build`).
3. Enable plugin in Obsidian community plugins.
4. Start the local daemon:
   - `python -m app.grpc_daemon`
5. Open plugin settings in Obsidian and configure:
   - gRPC daemon address (default: `127.0.0.1:50051`)
   - user ID / session ID
   - optional shared secret (if backend enforces one)
6. Click `Send heartbeat` to verify the daemon connection.

## gRPC Contract

The plugin calls `SidecarContextService` in `sidecar.proto`:
- `Heartbeat`
- `IngestEvent`
- `GetSession`
