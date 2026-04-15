# ADR: MCP as primary OpenClaw transport (deferred)

**Status:** Accepted (defer implementation)  
**Date:** 2026-04-12  
**Context:** OpenClaw–Birtha bridge Phases 2–4 and [`docs/external-orchestration-interfaces.md`](../external-orchestration-interfaces.md).

## Decision questions (answered)

### 1. Value vs HTTPS today

**HTTPS + `openclaw-bridge/v1`** already delivers: schema-validated envelope, attachment policy, Redis idempotency on `POST /api/ai/query`, typed SSE MVP on `POST /api/ai/query/stream`, and a clear operator path for cancel (`POST /api/ai/workflows/{id}/cancel`) with a typed **`cancel_ack`** companion object.

**MCP-primary** would require re-deriving idempotency, attachment limits, streaming, and audit semantics on top of MCP host configuration. Until product demand and operator readiness exceed the cost of that re-specification, **HTTPS remains the canonical shell ingress**.

### 2. Server host side / trust boundaries

Any future MCP surface would terminate **inside or adjacent to the same trust zone as Birtha api-service** (not arbitrary third-party MCP hosts for governed engineering actions). Tokens would mirror gateway/bearer policies; engineering artifacts would still be authored only by Birtha + agent-platform, not by OpenClaw inventing refs.

### 3. Coupling

**OpenClaw core** must not gain Birtha-specific planner or transport logic. Bridge behavior stays in **`openclaw/extensions/birtha-bridge`** and Birtha **`services/api-service`**. MCP-primary work, when allowed by the precondition checklist, should be implemented as **thin protocol adapters** reusing the same JSON contracts—not forked semantics.

## Outcome

- **No MCP-primary code** in this milestone (per original Phase 4 gate).
- Revisit only after the precondition checklist in `external-orchestration-interfaces.md` is satisfied **and** this ADR is updated or superseded.
