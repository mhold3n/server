# ADR-0002: OpenClaw tool-model lane (HTTPS-first)

## Status

Accepted (architecture); implementation tracked in [`../drafts/openclaw-tool-model-lane-implementation-brief.md`](../drafts/openclaw-tool-model-lane-implementation-brief.md).

## Context

OpenClaw is the **operator shell** (UX, tool discovery, streaming, session continuity). Xlotyl (`api-service` + `agent-platform-service`) is the **authoritative** orchestration and governed execution surface for Birtha. The supported ingress today is **`POST /api/ai/query`** with **`context.openclaw_bridge`**, exposed to OpenClaw via the plugin tool **`birtha_query`** (and **`birtha_query_stream`** for SSE), without OpenClaw core edits.

A gap appears when **OpenClaw AI-assisted tools** need scoped model calls: routing them through the **same generic user-query path** as ordinary chat blurs audit boundaries and risks treating tool-side model output as final, governed truth.

We need a **third lane**—distinct from shell orchestration and from full governed execution—that is explicitly **pre-authoritative**, schema-bounded, and auditable.

## Decision

Introduce a dedicated **tool-model lane** on the Xlotyl side, reachable over **HTTPS first** (same bridge family as `birtha_query`), with a new plugin tool (e.g. **`birtha_tool_query`**) that does **not** require OpenClaw core planner changes.

### Orchestration domains (do not blur)

| Domain | Owns | Must not own |
|--------|------|----------------|
| **OpenClaw shell orchestration** | User/session UX, tool discovery, tool selection, tool-local workflows, session mirror, streaming UX, operator-side continuity | Governed artifacts, final truth state, engineering state mutation, final publication authority |
| **OpenClaw tool-model lane** (contract) | Scoped model calls for tools, tool-oriented prompts, temporary/tool-local reasoning, schema-constrained outputs | Final answer synthesis, referential-state mutation, artifact publication, direct authoritative IDs |
| **Xlotyl ingress / orchestration** | Bridge validation, classification, policy enforcement, task decomposition, DevPlane lifecycle, authoritative routing | Shell UX details, OpenClaw-native local flow control |
| **Xlotyl governed execution** | Task packets, executor routing, validators, final answer or artifact generation | OpenClaw front-end planner logic |
| **Xlotyl final validation** | Fact-checking, policy checks, evidence review, deterministic verification, publish decision | Shell-local convenience formatting as source of truth |

### Tool taxonomy (required before shipping lane behavior)

| Class | Behavior | Model use | Where it runs |
|-------|----------|-----------|----------------|
| **A — Deterministic shell** | Formatting, routing, file transforms, UI, browser steps | None | OpenClaw only |
| **B — AI-assisted shell** | Summarize, classify, extract fields, propose search terms | Yes, scoped | **Tool-model lane** |
| **C — Governed product** | Engineering analysis, official synthesis, task-packet execution, artifact generation | Yes, authoritative | **Governed Xlotyl path** (OpenClaw only *triggers*) |

### Authority rules

- **OpenClaw** may control: shell UX, tool discovery, operator continuity, streaming presentation, local tool chaining, non-governed transient state.
- **Xlotyl** must control: final classification into governed work, task-packet creation, executor selection, engineering and referential state, artifact IDs, publishability, final policy verdict, final answer acceptance.

### Transport

- **Phase A:** Extend the existing HTTPS bridge with **`birtha_tool_query`** (parallel to `birtha_query` / `birtha_query_stream`), preserving idempotency, auth, audit, and envelope validation patterns.
- **Phase B (deferred):** MCP for selected non-mutating resources only after bridge hardening; no dual-write of governed state (see [`../external-orchestration-interfaces.md`](../external-orchestration-interfaces.md)).

## Consequences

### Positive

- Clear audit boundary: tool-side AI vs governed answer AI.
- Off-the-shelf OpenClaw tools remain usable without forcing every tool through full governed execution.
- Aligns with existing docs: OpenClaw as shell, Birtha as authority ([`../external-orchestration-interfaces.md`](../external-orchestration-interfaces.md)).

### Negative / risks

- New route, schemas, policies, and observability to maintain.
- OpenClaw extension must classify tools (A/B/C) consistently; misclassification is a product risk.

### Follow-ups

Implementation phases, JSON shapes, endpoint names, and acceptance criteria: [`../drafts/openclaw-tool-model-lane-implementation-brief.md`](../drafts/openclaw-tool-model-lane-implementation-brief.md).

## Related

- [`../external-orchestration-interfaces.md`](../external-orchestration-interfaces.md) — topology and MCP deferral.
- [`../runbooks/openclaw-birtha-bridge.md`](../runbooks/openclaw-birtha-bridge.md) — current bridge routes and tools.
- [`../decisions/adr-openclaw-bridge-mcp-primary.md`](../decisions/adr-openclaw-bridge-mcp-primary.md) — MCP-primary gate.
