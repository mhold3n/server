# Orchestration Routing Matrix

This document defines the **canonical routing behaviour** for orchestration
entrypoints. The API control plane is the only production ingress; it
delegates to the TypeScript `agent-platform` LangGraph service for all
orchestrated flows.

## External Entry Points

| Surface                         | Path                         | Purpose                                | Backend Workflow          |
|---------------------------------|------------------------------|----------------------------------------|---------------------------|
| API chat / query                | `/api/ai/query`             | General chat, tool-assisted queries    | `wrkhrs_chat`             |
| API task card workflow run      | `/api/ai/workflows/run`     | Code RAG, media fixups, sysadmin ops   | `wrkhrs_chat` (card-specified) |
| DevPlane task execution (API)   | `/api/dev/tasks/{id}/resume`| DevPlane backend code task orchestration | `devplane_code_task` (planned) |
| Control plane validation        | `POST /api/control-plane/validate/task-packet` | JSON Schema gate for task packets | API (`services/api`) |
| Structure classify (router)     | `POST /api/control-plane/structure/classify` | `services/structure` classifier via API bridge | API (`services/api`) |

## Internal Orchestrator (LangGraph) Surface

All orchestrated flows are implemented as workflows on the `agent-platform`
service at `settings.agent_platform_url`:

- `POST /v1/workflows/execute`
  - `workflow_name="wrkhrs_chat"` for chat and task card workflows.
  - `workflow_name="engineering_workflow"` for **unified control-plane** runs: accepts chat-originated or artifact-originated engineering requests, derives and persists `problem_brief -> engineering_state -> task_queue -> task_packet`, and uses `ORCHESTRATOR_API_URL` (or `DEVPLANE_PUBLIC_BASE_URL`) for control-plane intake plus DevPlane dossier/run-event persistence.
  - `workflow_name="rag_retrieval"` for low-level RAG utility flows.
  - `workflow_name="devplane_code_task"` (future) for DevPlane backend runs.

## Deprecated / Legacy Surfaces

The following entrypoints are considered legacy and should not be used for
new integrations:

- Python router `/route` in `services/router/src/router.py` (**returns 410 Gone**; tool-only adapter now)
- Direct `services/structure` imports from non-API callers for **ingress** (use `POST /api/control-plane/structure/classify` or in-process graph nodes that share the same contract)
- Direct AI stack prompts via `/llm/prompt`
- Legacy MBMH / `engineering_physics_v1` surfaces (archived out of the active repo)

They will be removed once the LangGraph workflows fully cover all use cases.
