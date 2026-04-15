# Orchestration Routing Matrix

This document defines the **canonical routing behaviour** for orchestration
entrypoints. The API control plane is the only production ingress; it
delegates to the TypeScript `agent-platform` LangGraph service for all
orchestrated flows.

## External Entry Points

| Surface                         | Path                         | Purpose                                | Backend / notes          |
|---------------------------------|------------------------------|----------------------------------------|---------------------------|
| API chat / query                | `/api/ai/query`             | General chat, tool-assisted queries    | `wrkhrs_chat` workflow on agent-platform |
| API task card workflow run      | `/api/ai/workflows/run`     | Code RAG, media fixups, sysadmin ops   | `wrkhrs_chat` (card-specified) |
| DevPlane task resume            | `POST /api/dev/tasks/{task_id}/resume` | Starts a governed backend run for an existing DevPlane task | API persists state, then calls agent-platform `POST /v1/devplane/runs` via [`DevPlaneExecutionClient`](../src/devplane/executor_client.py) (same repo) |
| DevPlane dossier                | `GET /api/dev/tasks/{task_id}/dossier` | Typed dossier for engineering session | API (`services/api-service`) |
| DevPlane run events             | `POST /api/dev/runs/{run_id}/events` (and `/complete`) | Callbacks from agent-platform into DevPlane | API; URLs built from `devplane_public_base_url` |
| Control plane validation        | `POST /api/control-plane/validate/task-packet` | JSON Schema gate for task packets | API (`services/api-service`) |
| Structure classify (router)     | `POST /api/control-plane/structure/classify` | `services/structure-service` classifier via API bridge | API (`services/api-service`) |

## Internal Orchestrator (LangGraph) Surface

All orchestrated flows are implemented as workflows on the `agent-platform`
service at `settings.agent_platform_url` (env `AGENT_PLATFORM_URL`, or alias
`ORCHESTRATOR_AGENT_PLATFORM_URL` on the API process).

- `POST /v1/workflows/execute`
  - `workflow_name="wrkhrs_chat"` for chat and task card workflows.
  - `workflow_name="engineering_workflow"` for **unified control-plane** runs: accepts chat-originated or artifact-originated engineering requests, derives and persists `problem_brief -> engineering_state -> task_queue -> task_packet`, and uses `ORCHESTRATOR_API_URL` (or `DEVPLANE_PUBLIC_BASE_URL`) for control-plane intake plus DevPlane dossier/run-event persistence.
  - `workflow_name="rag_retrieval"` for low-level RAG utility flows.

- `POST /v1/devplane/runs` — **DevPlane execution backend** used when the API DevPlane layer resumes a task: creates an internal run, executes in an isolated workspace ([`executeBackendRun`](../../agent-platform-service/server/src/devplane/runner.ts) under `services/agent-platform-service/`), and POSTs progress to the callback URLs supplied on the create payload.

## Deprecated / Legacy Surfaces

The following entrypoints are considered legacy and should not be used for
new integrations:

- Python router `/route` in `services/router-service/src/router.py` (**returns 410 Gone**; tool-only adapter now)
- Direct `services/structure-service` imports from non-API callers for **ingress** (use `POST /api/control-plane/structure/classify` or in-process graph nodes that share the same contract)
- Direct AI stack prompts via `/llm/prompt`
- Legacy MBMH / `engineering_physics_v1` surfaces (archived out of the active repo)

They will be removed once the LangGraph workflows fully cover all use cases.
