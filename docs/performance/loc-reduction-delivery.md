# LOC Reduction Delivery Sequence

## PR 1: Low-Risk Dedupe and Hygiene

- Shared backend context-source mapper.
- Orchestrator message persistence helper.
- Frontend stream client/header unification.
- Remove unused workflow stream buffering.
- Plugin ignore hygiene (`node_modules`, ts build metadata).

Required checks:
- chat + chat/stream manual smoke test
- thread load/create flow
- obsidian session polling still updates UI

## PR 2: Performance-Oriented Structure

- Async bridge optimization (`run_coroutine_sync`) to avoid per-call event loop creation.
- Stream path cleanup and dedupe in API/orchestrator.
- Keep sidecar event endpoints lean and stable.

Required checks:
- verify no dropped stream events or stale heartbeat behavior

## PR 3: Contract Unification

- Backend route models aligned to contracts module.
- Core context source model sourced from shared backend contract.
- Sidecar payload types aligned to backend contracts.

Required checks:
- typecheck plugin
- backend request/response schema sanity checks
- regression pass for Obsidian event ingestion + session fetch

## Perf Note Template (include in each PR)

- Baseline reference: `docs/performance/loc-reduction-baseline.md`
- Before:
  - backend p50/p95:
  - sidecar event/heartbeat p95:
- After:
  - backend p50/p95:
  - sidecar event/heartbeat p95:
- Net:
  - LOC delta:
  - behavior changes:
