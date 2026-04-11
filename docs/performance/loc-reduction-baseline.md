# LOC Reduction Baseline and Gates

This file is the baseline contract for the cross-cutting LOC reduction rollout.

## Baseline Capture Commands

### Backend stream latency

```bash
curl -N -X POST "http://localhost:8081/chat/stream" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: default-user" \
  -d '{"query":"baseline check","user_id":"default-user"}'
```

Record:
- `time_to_first_event_ms`: wall clock to first `data:`
- `time_to_done_ms`: wall clock to final `done`
- `error_rate`: failures per 50 runs

### Obsidian sidecar responsiveness

Record:
- event ingest latency (`/obsidian/context/events`) p50/p95
- heartbeat round-trip (`/obsidian/context/heartbeat`) p50/p95
- plugin flush success rate over 50 events

### Build and bundle hygiene

Record:
- API container start/build time
- `obsidian-plugin` build time
- tracked file count change and LOC delta (`git diff --stat`)

## Acceptance Gates

- Backend: no p95 regression greater than 10% on stream completion latency.
- Obsidian sidecar: no regression in event ingest/heartbeat p95 greater than 10%.
- Functional: stream responses and Obsidian sync remain stable.
- Hygiene: plugin dependencies/build artifacts are no longer treated as hand-maintained source.

## Phase Tracking

| Phase | Date | Backend p50/p95 | Sidecar ingest p50/p95 | Notes |
| --- | --- | --- | --- | --- |
| 0 Baseline | _pending_ | _pending_ | _pending_ | _pending_ |
| 1 Low Risk | _pending_ | _pending_ | _pending_ | _pending_ |
| 2 Perf Structure | _pending_ | _pending_ | _pending_ | _pending_ |
| 3 Contracts | _pending_ | _pending_ | _pending_ | _pending_ |
