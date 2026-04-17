# Implementation brief: OpenClaw tool-model lane (Birtha / Xlotyl)

**Status:** Draft — encodes [ADR-0002](../adr/0002-openclaw-tool-model-lane.md).  
**Audience:** Agents and engineers implementing `api-service`, `agent-platform-service`, and `openclaw/extensions/birtha-bridge`.

## Goals

1. Add a **dedicated HTTPS ingress** for OpenClaw **class B** (AI-assisted shell) tools so they do **not** use the same code path as ordinary user **`birtha_query`** turns when a scoped tool call is intended.
2. Label every tool-lane response as **pre-authoritative** with mandatory provenance and **`requires_validation = true`**.
3. Keep **OpenClaw core unchanged** — plugin-only tool (e.g. **`birtha_tool_query`**).

## Non-goals (this lane)

- Final user-facing truth as authoritative output.
- Direct mutation of engineering or referential state.
- Creation of governed artifact IDs or publication.
- Bypassing final validation / governed execution when the work is class C.

## Suggested endpoint (name secondary to boundary)

Pick one canonical route in **`xlotyl/services/api-service`** (exact path TBD in implementation PR):

| Candidate | Notes |
|-----------|--------|
| `POST /api/ai/tool-query` | Short; pairs with `/api/ai/query` |
| `POST /api/ai/lanes/tool/v1/query` | Explicit versioning |
| `POST /api/ai/openclaw/tool-call` | Caller-obvious |

**Requirement:** Same transport stack as existing bridge (bearer auth, request logging, envelope validation, optional idempotency if replay is a concern for tool calls).

## OpenClaw bridge extension (Phase A transport)

Add alongside existing tools:

| Tool | Route | Purpose |
|------|--------|---------|
| `birtha_query` | `POST /api/ai/query` | User/governed ingress (current) |
| `birtha_query_stream` | `POST /api/ai/query/stream` | SSE (current) |
| **`birtha_tool_query`** | **New route above** | Class B tool-model calls only |

Plugin registers `registerHttpRoute` / same auth pattern as `birtha_query`.

## Request envelope (normative fields)

Minimum fields the handler must accept (JSON body or nested under `context` per existing bridge conventions — **align with `schemas/openclaw-bridge/v1/`** when adding a `tool_lane` or `openclaw_tool` sub-envelope):

| Field | Type | Purpose |
|-------|------|---------|
| `tool_name` | string | |
| `tool_version` | string | Semver or extension-defined |
| `tool_goal` | string | Short objective (not full chat) |
| `tool_schema_expected` | JSON Schema ref or inline | Constrained output |
| `input_payload` | object | Tool inputs only |
| `allowed_capabilities` | string[] | Whitelist for side effects (usually empty) |
| `max_tokens` | int | Hard cap |
| `timeout_budget_ms` | int | |
| `needs_citations` | bool | |
| `needs_structured_output` | bool | Prefer structured first |
| `session_ref` | string | Opaque continuity ref (mirror-compatible) |
| `openclaw_bridge_context` | object | Subset of bridge v1 fields needed for audit |

**Do not** pass full chat transcripts by default; pass minimal snippets and tool objective.

## Response: mandatory provenance (every success path)

Every tool-lane response **must** include:

| Field | Value / semantics |
|-------|-------------------|
| `origin` | `openclaw_tool` |
| `tool_name` | echo |
| `tool_call_id` | string |
| `model_used` | string |
| `lane` | `tool_model` |
| `confidence_mode` | `preliminary` |
| `mutation_rights` | `none` |
| `authoritative` | `false` |
| `requires_validation` | `true` |

## Response: result class (`output_type`)

One of:

| `output_type` | Meaning |
|---------------|---------|
| `tool_result_structured` | Structured intermediate success |
| `tool_result_untrusted_text` | Textual, still non-authoritative |
| `tool_result_needs_governed_escalation` | Unsafe to complete in lane; caller should escalate to governed run |
| `tool_result_rejected` | Policy / schema / authority failure |

## Policy set (tool lane vs main answering lane)

| Area | Tool lane |
|------|-----------|
| Prompt scope | Narrow, tool-task only |
| Output | Structured JSON first |
| Model | Lightweight or specialized where possible |
| Citations | Required if factual claims; optional for pure transform |
| Mutation | **None** unless explicitly whitelisted |
| Reasoning | Short-horizon, operational |
| Persistence | Intermediate log / transient only |
| Audit | Mandatory |

## Feedback loop (reference)

```text
User → OpenClaw shell orchestration → Tool selected?
  ├─ No → birtha_query → Xlotyl governed orchestration → execution + validation → final answer
  └─ Yes → class?
       ├─ A → local result → optional evidence to Xlotyl
       ├─ B → birtha_tool_query → tool-model lane → intermediate → validation / escalation
       └─ C → trigger governed Xlotyl run → DevPlane + validators → final governed result
```

## Implementation phases (checklist)

| Phase | Deliverable | Acceptance |
|-------|-------------|------------|
| **1** | Registry of OpenClaw-integrated tools with class A/B/C | No lane code ships without table |
| **2** | JSON Schemas for tool-lane request/response + error taxonomy | CI schema validation |
| **3** | `birtha_tool_query` in `birtha-bridge` extension | Plugin-only; no OpenClaw core edits |
| **4** | Xlotyl handler: validation, scoped model selection, schema output, no-mutation guarantees, escalation hook | Integration tests |
| **5** | Final-validation handoff: tool outputs never silent final truth | E2E or contract tests |
| **6** | Metrics: per-lane counts, escalation rate, rejection rate, policy-fail rate | Dashboards or logs |

## Operating rules (defaults)

1. Tool-side AI output is **never** authoritative by default.
2. Only Xlotyl may create governed artifacts or mutate referential state.
3. If a tool needs final-answer authority, it is **class C**, not a shell tool.
4. HTTPS remains canonical for OpenClaw↔Xlotyl until ADR MCP gate is satisfied.
5. MCP later: shadow-read or probe-only until conflict semantics are written.

## Files to touch (xlotyl repo — not in this server checkout)

- `xlotyl/schemas/openclaw-bridge/v1/` — new sub-schema for tool lane.
- `xlotyl/services/api-service` — route, handler, policy middleware.
- `xlotyl/services/agent-platform-service` — optional scoped executor or shared model client with stricter caps.
- `openclaw/extensions/birtha-bridge` — `birtha_tool_query` tool.

## References (this repo)

- [ADR-0002](../adr/0002-openclaw-tool-model-lane.md)
- [External orchestration interfaces](../external-orchestration-interfaces.md)
- [Runbook: OpenClaw ↔ Birtha bridge](../runbooks/openclaw-birtha-bridge.md)
