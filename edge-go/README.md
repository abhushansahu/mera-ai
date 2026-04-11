# Mera AI Edge Prototype (Go)

Prototype high-throughput edge service for runtime migration experiments.

## Features
- Proxies `/status`, `/contracts/version`, `/chat`, `/chat/stream`, `/mem0/*`, `/spaces/*`, and `/internal/boundary/*` to the Python backend.
- Preserves and forwards request headers.
- Emits `x-contract-version: v1` and request IDs.
- Supports optional shadow traffic for safe comparisons.

## Run

```bash
cd edge-go
go run .
```

## Environment

- `EDGE_ADDR` (default `:8081`)
- `EDGE_UPSTREAM_PRIMARY` (default `http://localhost:8000`)
- `EDGE_SHADOW_ENABLED` (`true`/`false`, default `false`)
- `EDGE_UPSTREAM_SHADOW` (required only when shadow enabled)

## Example

```bash
EDGE_UPSTREAM_PRIMARY=http://localhost:8000 \
EDGE_SHADOW_ENABLED=true \
EDGE_UPSTREAM_SHADOW=http://localhost:8000 \
go run .
```
