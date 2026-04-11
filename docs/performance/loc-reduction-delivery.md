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

- Narrow Zustand selectors in streaming-heavy components.
- Remove duplicate thread selection UI ownership from chat body.
- Async bridge optimization (`run_coroutine_sync`) to avoid per-call event loop creation.

Required checks:
- profile one streaming run and compare commit count
- verify no dropped stream events and no stuck loading state

## PR 3: Contract Unification

- Backend route models aligned to contracts module.
- Core context source model sourced from shared backend contract.
- Frontend API/store contract types consolidated.

Required checks:
- typecheck frontend and plugin
- backend request/response schema sanity checks
- regression pass for Obsidian event ingestion + session fetch

## Perf Note Template (include in each PR)

- Baseline reference: `docs/performance/loc-reduction-baseline.md`
- Before:
  - backend p50/p95:
  - frontend commits during stream:
- After:
  - backend p50/p95:
  - frontend commits during stream:
- Net:
  - LOC delta:
  - behavior changes:
