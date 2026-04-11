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

### Frontend render churn

Use React Profiler on:
- `ChatInterface`
- `ChatInput`
- `ContextPanel`

Record:
- commits during one streaming answer
- total commit time
- worst commit duration

### Build and bundle hygiene

Record:
- `frontend` build time
- `obsidian-plugin` build time
- tracked file count change and LOC delta (`git diff --stat`)

## Acceptance Gates

- Backend: no p95 regression greater than 10% on stream completion latency.
- Frontend: at least 20% fewer commits during a streaming response.
- Functional: thread loading/switching, stream rendering, and Obsidian sync remain stable.
- Hygiene: plugin dependencies/build artifacts are no longer treated as hand-maintained source.

## Phase Tracking

| Phase | Date | Backend p50/p95 | Frontend commits | Notes |
| --- | --- | --- | --- | --- |
| 0 Baseline | _pending_ | _pending_ | _pending_ | _pending_ |
| 1 Low Risk | _pending_ | _pending_ | _pending_ | _pending_ |
| 2 Perf Structure | _pending_ | _pending_ | _pending_ | _pending_ |
| 3 Contracts | _pending_ | _pending_ | _pending_ | _pending_ |
