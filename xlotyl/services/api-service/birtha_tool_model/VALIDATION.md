# Tool-model lane vs governed pipeline

## Guarantees (reference handler)

1. **No task packets** — `process_tool_query` does not create DevPlane workspaces, `.birtha/task-packet.json`, or engineering artifacts.
2. **No referential mutation** — responses are labeled `mutation_rights: none` in provenance when present.
3. **Default escalation** — without `BIRTHA_TOOL_MODEL_MOCK=1`, class **B** requests return `tool_result_needs_governed_escalation` so operators route work through `POST /api/ai/query` or governed workflows instead of silently trusting tool AI.

## Product integration checklist (xlotyl api-service)

When merging this router into the production app:

- Ensure **`POST /api/ai/query`** and workflow completion paths **never** copy `tool_result_*` bodies into `referential_state` or publishable artifacts without passing **final validation**.
- If the main pipeline merges tool outputs from OpenClaw, require an explicit **`requires_validation`** gate or strip `lane=tool_model` payloads unless promoted by policy.
- Wire **Redis idempotency** for `/api/ai/tool-query` with a **separate key prefix** from `/api/ai/query`.

See [`docs/adr/0002-openclaw-tool-model-lane.md`](../../../../docs/adr/0002-openclaw-tool-model-lane.md).
