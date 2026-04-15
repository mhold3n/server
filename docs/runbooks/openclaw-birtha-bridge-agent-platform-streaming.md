# Discovery: agent-platform workflow streaming (OpenClaw bridge Phase 3)

**Date:** 2026-04-12 (repo-local note; refresh when agent-platform changes).

## Endpoints reviewed

- **Birtha api-service** calls the orchestrator via [`OrchestratorClient.execute_workflow`](../../services/api-service/src/orchestrator_client.py) — synchronous HTTP to agent-platform `POST /v1/workflows/execute` (see client implementation in the same module).
- **Cancel:** `POST /v1/workflows/:id/cancel` (proxied by Birtha `POST /api/ai/workflows/{workflow_id}/cancel`).
- **Agent-platform server tree:** [`server/src/`](../../services/agent-platform-service/server/src/) — orchestration entrypoints under `orchestration/` (e.g. `engine.ts`, `runtime-router.ts`). There is **no** first-class `text/event-stream` body on the execute path in this repository snapshot.

## Decision

There is **no incremental lifecycle stream** from agent-platform to Birtha today that Birtha can faithfully proxy into mid-run `clarification.required`, `tool_request`, or dense `run.progress` events.

**Explicit MVP decision:** Birtha `POST /api/ai/query/stream` remains a **single-shot** wrapper: `run.started` → one `execute_ai_query_pipeline` call → `run.completed` / `run.failed` → optional tail events derived from the **final** JSON (`pending_mode_change`, etc.). When agent-platform exposes a durable workflow event stream or chunked execute response, api-service should add a **mapping adapter** from platform events to `schemas/openclaw-bridge/v1/events/stream-event.schema.json` without embedding raw LangGraph logs.

## Follow-up epic (out of scope until platform ships)

1. Subscribe to or poll a platform-defined run event source keyed by `workflow_id`.
2. Map normalized lifecycle messages to bridge event types.
3. Extend OpenClaw `birtha_query_stream` consumer collapse rules for high-volume progress.
