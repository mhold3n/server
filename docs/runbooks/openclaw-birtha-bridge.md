# Runbook: OpenClaw ↔ Birtha bridge (HTTPS + SSE)

## Vocabulary

| Term | Meaning |
|------|---------|
| **openclaw-bridge v1** | Versioned envelope under `context.openclaw_bridge` (`schemas/openclaw-bridge/v1/`). |
| **Session mirror** | Plugin-local JSON keyed by `session_key`; copies `result.referential_state` strings only. |
| **Typed SSE event** | One JSON object per `data:` line; schema `stream-event.schema.json`. |

## Transports

### JSON query (idempotent)

- **Route:** `POST /api/ai/query`
- **OpenClaw tool:** `birtha_query`
- **Idempotency:** `openclaw_bridge.idempotency_key` + Redis (replay on identical payload hash). Not applied on the stream route.

### SSE stream (MVP)

- **Route:** `POST /api/ai/query/stream` (`text/event-stream`)
- **OpenClaw tool:** `birtha_query_stream`
- **Events today:** `run.started` → `run.completed` or `run.failed` → optional `pending_mode_change` tail from the final JSON snapshot.
- **Mid-run** clarification / tool / graph events require **agent-platform** to expose incremental lifecycle or a workflow stream; until then, consumers must not assume fine-grained progress.

### Tool-model lane (class B AI-assisted tools)

- **Route:** `POST /api/ai/tool-query`
- **OpenClaw tool:** `birtha_tool_query`
- **Purpose:** Scoped, non-authoritative model calls for OpenClaw tools (taxonomy class **B**). Not for final user answers or governed mutations.
- **Idempotency:** Recommended: same pattern as JSON query (`openclaw_bridge.idempotency_key` + Redis) with a **dedicated key namespace**; stricter max body size than `/api/ai/query`.
- **Schemas:** `xlotyl/schemas/openclaw-bridge/v1/tool-model/` (request, response union, provenance).
- **Registry:** `xlotyl/schemas/openclaw-bridge/v1/birtha_bridge_tools.v1.json` — only class **B** tools may hit this route; class **C** must use governed ingress.

## Agent-platform discovery (Phase 3)

The TypeScript runner (`services/agent-platform-service/server`) exposes synchronous workflow execution:

- `POST /v1/workflows/execute` — primary completion path used by `OrchestratorClient`.
- `POST /v1/workflows/:id/cancel` — cancel RPC proxied by `POST /api/ai/workflows/{workflow_id}/cancel` on api-service.
- `GET /v1/workflows/:id/status` — polling status (not yet mapped to bridge SSE).

There is **no** streaming response body from execute in the current tree; Birtha’s SSE adapter wraps the **same** `execute_ai_query_pipeline` call and emits coarse lifecycle events only.

## Cancel

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  "https://<api-host>/api/ai/workflows/<workflow_id>/cancel"
```

On success the body is the agent-platform JSON. Typed `cancel.ack` SSE events are reserved for a future combined stream.

## Resume

- **Today:** Issue a new `POST /api/ai/query` or stream request with the same `engineering_session_id` / bridge continuity fields (mirror-backed or explicit). There is no `Last-Event-ID` cursor on the MVP stream.
- **Documented future:** `resume.ack` + cursor fields are defined in `stream-event.schema.json`; wire semantics will be added when the API supports resumable streams.

## Operator surfaces (OpenClaw plugin)

- **HTTP (gateway):** `GET /plugins/birtha-bridge/v1/session?session_key=…` — opaque summary. `DELETE` clears mirror only.
- **CLI:** `openclaw birtha session show|clear --session-key …`

## Related docs

- `schemas/openclaw-bridge/v1/events/README.md` — envelope, ordering rules, “no raw logs”.
- `docs/adr/0002-openclaw-tool-model-lane.md` — tool-model lane authority and contracts.
- `docs/runbooks/openclaw-birtha-bridge-agent-platform-streaming.md` — agent-platform streaming discovery + MVP decision.
- `openclaw/extensions/birtha-bridge/CONTINUITY.md` — mirror vs authority.
- `docs/external-orchestration-interfaces.md` — repo topology + Phase 4 MCP decision gate.
