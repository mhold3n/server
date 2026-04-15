# OpenClaw bridge v1 — typed stream events

JSON Schema: [`stream-event.schema.json`](stream-event.schema.json).

## Transport

- **Producer (today):** `POST /api/ai/query/stream` on `services/api-service` returns `text/event-stream`. Each event is one SSE `data:` line containing a single JSON object (no pretty-printed multi-line payloads).
- **Consumer:** OpenClaw `birtha_query_stream` uses a Node `fetch` streaming reader (see `openclaw/extensions/birtha-bridge/src/sse-client.ts`).

## Envelope

Every wire event includes:

| Field       | Meaning |
|------------|---------|
| `type`     | Discriminator (`run.started`, `run.completed`, …). |
| `version`  | Envelope semver string (currently `1.0.0`). |
| `event_id` | Monotonic string counter for this HTTP response (best-effort; suitable for logs). |
| `cursor`   | Optional opaque cursor string (reserved for future replay; producers may omit). |
| `ts`       | **Canonical** UTC timestamp (`date-time`). |
| `timestamp` | Deprecated alias for `ts`; do not emit in new producers. |

Type-specific fields may appear at the top level (for example `workflow_id` on `run.completed`) **and** inside `payload`. Producers should keep **governed facts** out of ad-hoc strings; prefer structured `payload` for new fields.

## Ordering and reconnect

- Ordering is **best-effort monotonic** by `event_id` within a single SSE response body.
- **Resume hints (opaque, no durable replay yet):** Clients may send **`Last-Event-ID`** (standard SSE header) and/or query **`event_cursor`** on `POST /api/ai/query/stream`. When either is non-empty, Birtha emits a leading **`resume.ack`** event echoing those inputs (and `engineering_session_id` from `context` when present), then runs the normal MVP sequence. **This does not replay skipped events** — there is no server-side event buffer; each request still executes `execute_ai_query_pipeline` once unless you add idempotency/stream replay separately.
- **Durable cursor / `Last-Event-ID` replay** is explicitly **out of scope** for the original bridge MVP.

Discovery (why mid-run events are coarse today): [`openclaw-birtha-bridge-agent-platform-streaming.md`](../../../../docs/runbooks/openclaw-birtha-bridge-agent-platform-streaming.md).

## Contract rules

1. **No raw LangGraph / orchestrator log lines** as the primary UX contract — only typed events from this schema family.
2. **MVP limitation:** until `agent-platform` exposes incremental lifecycle or a workflow stream, Birtha emits **`run.started`**, then **`run.completed`** or **`run.failed`**, plus optional tail events such as **`pending_mode_change`** derived from the final JSON snapshot. Mid-run `clarification.required` / `tool_request` appear only when the backend can produce them.

## Cancel

Workflow cancel is **`POST /api/ai/workflows/{workflow_id}/cancel`** (proxy to agent-platform). On **HTTP 200**, the JSON body includes:

- **`orchestrator`** — raw agent-platform response (shape upstream-defined).
- **`cancel_ack`** — typed object matching the **`cancel.ack`** branch of this schema (same fields as an SSE `data:` line would use: `type`, `version`, `event_id`, `ts`, `payload.workflow_id`).

## Validation

Golden fixtures live under [`fixtures/`](fixtures/). CI loads each fixture with `jsonschema` (see `services/api-service/tests/test_openclaw_stream_event_fixtures.py`).
