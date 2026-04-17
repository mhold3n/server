# External orchestration interfaces

OpenClaw and Claw Code are developed inside the **[XLOTYL/xlotyl](https://github.com/XLOTYL/xlotyl)** product repository (as submodules there), not as checkouts in this repo.

This **server** repository integrates the AI stack at runtime via **HTTP** and **published OCI images** (`ghcr.io/xlotyl/*`, see [`config/xlotyl-images.env`](../config/xlotyl-images.env)), not by vendoring sources.

## What is active (xlotyl)

The active execution stack is implemented in **xlotyl** (clone separately). Conceptual layout:

1. `services/api-service`
2. `services/agent-platform-service/server`
3. `services/model-runtime`
4. **`schemas/`** (e.g. `openclaw-bridge/`, `model-runtime/`) and typed contracts in `services/api-service` / domain packages.

Those services implement the live orchestration and engineering pipeline.

## Where Claw Code fits today

`claw-code-main/` (vendored under the xlotyl repo) is an upstream checkout and reference codebase, not a first-class executor in the active pipeline unless wired explicitly in agent-platform.

Today there is no direct runtime import or dispatch from the control plane, DevPlane, or agent-platform into that tree from **this** repository.

Practical implication:

- Claw Code can be used as an external operator tool or future integration target.
- It is not one of the governed `selected_executor` values in the active task-packet routing model.
- It does not bypass the control-plane gating or DevPlane workspace lifecycle.

## Where OpenClaw fits today

`openclaw/` is also an upstream checkout, but its relationship to the active stack is closer: it maps to the operator/client role rather than the executor role.

In the active services, OpenClaw is treated as an external operator surface, not an internal execution backend:

- DevPlane supports `execution_mode="external"` runs.
- External runs can carry an `agent_session_id`.
- External operators can post run events and completion callbacks back into DevPlane.

That means OpenClaw can sit in front of the active platform as a client/operator shell, but the internal governed execution path still belongs to the control plane plus agent-platform.

### OpenClaw HTTPS bridge (Phase 1)

The supported shell ingress is **`POST /api/ai/query`** on **`xlotyl/services/api-service`** with a versioned envelope under **`context.openclaw_bridge`**. JSON Schemas live in **`xlotyl/schemas/openclaw-bridge/v1/`** (envelope, attachment rules, idempotency contract). The bundled OpenClaw extension **`openclaw/extensions/birtha-bridge`** implements this path as a **plugin-only** tool (`birtha_query`) so OpenClaw core stays unchanged in Phase 1.

**Phase 2–3 additions (same extension):** shell-local **session mirror** + operator HTTP/CLI (`CONTINUITY.md` in the extension), **`birtha_query_stream`** for typed SSE (`schemas/openclaw-bridge/v1/events/`), and the runbook **`docs/runbooks/openclaw-birtha-bridge.md`** for transport vocabulary and agent-platform limits.

### MCP as the primary OpenClaw transport (Phase 4 — deferred)

Cross-exposing Birtha MCP servers to OpenClaw as the **canonical** shell↔control-plane transport is **explicitly Phase 4**. Ship and harden the HTTPS + `openclaw-bridge/v1` path first; keep MCP usage focused on **internal** orchestration and tool execution inside Birtha until that milestone.

#### Phase 4 — capability map (documentation only until preconditions)

| Capability | HTTPS + bridge today | MCP-primary (future) |
|------------|----------------------|----------------------|
| Session / continuity | `birtha_query` + shell mirror + `context.openclaw_bridge` | Would require MCP resources or typed tools mirroring the same contracts |
| Streaming UX | `POST /api/ai/query/stream` (coarse MVP) | Would need framed notifications or streamable MCP (not assumed) |
| Cancel | `POST /api/ai/workflows/{id}/cancel` | Would need explicit MCP method(s) with the same authz story |
| Idempotency | Redis-backed on `/api/ai/query` | Must be re-specified (MCP has no native idempotency key) |

#### Authority preservation

Any future MCP-primary path must preserve the same **authority boundary**: Birtha remains the source of truth for engineering artifacts and `referential_state`. OpenClaw may cache **opaque string refs** only; it must not fabricate governed ids or artifact bodies.

#### Parallel-run migration

Running HTTPS bridge traffic in parallel with experimental MCP is allowed **only** for shadow reads or non-mutating probes. Do not dual-write engineering state from two transports until conflict semantics, idempotency, and audit logging are defined in writing.

#### When to keep HTTPS

Stay on HTTPS + gateway-auth `registerHttpRoute` / bearer `POST /api/ai/query` when any of the following is true:

- You need **browser-adjacent** or universal client support without MCP host configuration.
- You rely on **existing idempotency** and attachment policy from `openclaw-bridge/v1`.
- Operator compliance requires **simple audit** (“POST to one URL”) rather than MCP server graphs.

#### Precondition checklist (gate for MCP-primary **code**)

Do **not** implement MCP as the only shell transport until all items are satisfied and recorded in an ADR or engineering note:

1. **HTTPS bridge** stable in production (envelope validation, attachment limits, error taxonomy).
2. **Session mirror** (`birtha-bridge` Phase 2) exercised for resume + clear semantics.
3. **SSE stream** semantics agreed (`stream-event.schema.json`, cancel/resume story documented).
4. **Cancel + resume** either implemented end-to-end or explicitly deferred with user-visible limitations.
5. **No OpenClaw core planner edits** required for MCP parity (agent-native requirement).
6. **Auth / logging** model for MCP servers matches gateway policy (token scopes, PII redaction).

Until the checklist is complete, Phase 4 remains **documentation + decision gate only**.

Written answers to the Phase 4 decision questions (value vs HTTPS, host side, coupling): [`docs/decisions/adr-openclaw-bridge-mcp-primary.md`](decisions/adr-openclaw-bridge-mcp-primary.md).

## Engineering-governed execution path

The active engineering pipeline is packet-driven:

1. A request enters the API layer and may be promoted into `engineering_task` or `strict_engineering`.
2. The control-plane engineering intake builds governed artifacts:
   - `problem_brief`
   - `engineering_state`
   - `task_queue`
   - `task_packet`
3. DevPlane refuses launch until the problem brief is valid and the engineering state is ready for task decomposition.
4. DevPlane provisions an isolated git worktree and writes `.birtha/task-packet.json` plus the typed engineering artifacts.
5. Internal execution dispatches to **`xlotyl/services/agent-platform-service/server`** through `/v1/devplane/runs`.
6. The agent-platform runner reads the active task packet and routes by `routing_metadata.selected_executor`.
7. Deterministic verification runs before the task can become `ready_to_publish`.

## Executor model in the active pipeline

The active routing model is not “OpenClaw vs Claw Code”. It is task-packet executor selection.

Current governed executors are:

- `coding_model`
- `local_general_model`
- `multimodal_model`
- `strategic_reviewer`
- `deterministic_validator`

For code implementation specifically:

- `coding_model` runs through **Claw Code** from the TypeScript agent-platform (`claw_code` runtime), not through `model-runtime` HTTP.
- `local_general_model` and `strategic_reviewer` use **merged Open Multi-Agent** (`merged_oma`: hosted or mock LLM per `LLM_BACKEND` / provider config), not `POST /infer/general`.
- `multimodal_model` is the **only** governed executor that calls **`model-runtime`** today: **`POST /infer/multimodal`** when `MODEL_RUNTIME_URL` is set (empty URL fails strict multimodal runs).
- The **`model-runtime`** service also exposes **`POST /infer/general`** and **`POST /infer/coding`** for contracts, manual smoke, and future consumers; they are **not** invoked by the agent-platform TypeScript engine in the current tree.
- Verification is always brought back under deterministic control-plane commands.

## Net effect

The clean mental model is:

- `openclaw/`: external operator/client surface
- `claw-code-main/`: external coding-agent/reference surface
- **`xlotyl/services/api-service`** + **`xlotyl/services/agent-platform-service/server`**: authoritative orchestration and DevPlane runtime
- **`xlotyl/schemas/`** + API/domain **Pydantic** models: authoritative contract surfaces for bridge and runtime payloads (under the `xlotyl` submodule)

So if OpenClaw or Claw Code are used, they should consume the same governed worktree and `.birtha/task-packet.json` artifacts and report back through DevPlane. They are adjacent to the engineering pipeline, not replacements for it.
