# WrkHrs gateway service decomposition

The Python package under [`services/ai-gateway-service`](../) is organized into **logical services** that map to **Docker images** used by [`docker/compose-profiles/docker-compose.ai.yml`](../../../docker/compose-profiles/docker-compose.ai.yml).

## Container mapping

| Compose service        | Build context / Dockerfile                          | Role |
|------------------------|-----------------------------------------------------|------|
| `wrkhrs-gateway`       | `docker/gateway/Dockerfile`                         | OpenAI-compatible HTTP facade, routing to orchestrator |
| `wrkhrs-rag`           | `docker/rag/Dockerfile`                             | Vector search / retrieval |
| `wrkhrs-asr`           | `docker/asr/Dockerfile`                             | Speech-to-text |
| `wrkhrs-tool-registry` | `docker/tool-registry/Dockerfile`                   | Tool metadata |
| `wrkhrs-mcp`           | `docker/mcp/Dockerfile`                             | MCP bridge |
| `wrkhrs-orchestrator`  | `docker/orchestrator/Dockerfile`                    | LangGraph / legacy orchestrator profile |
| Prompt middleware      | `docker/prompt-middleware/Dockerfile`               | Prompt transforms (when built as its own image) |

Python sources live under `services/gateway/`, `services/rag/`, `services/prompt_middleware/`, etc., with tests scoped in [`pyproject.toml`](../pyproject.toml) (`tool.pytest` / coverage paths).

## Hardening direction

- Keep **image boundaries** aligned with these directories so each Dockerfile copies only the subtree it needs.
- Share **types and HTTP clients** via small internal modules; avoid circular imports between gateway ↔ rag ↔ asr.
- Prefer **content-domain** media helpers from [`domain-content`](../../domain-content) for Whisper/caption alignment when extending ASR-adjacent behavior.

Production orchestration defaults to **TypeScript** `agent-platform`; this decomposition applies to the Python WrkHrs stack and compose profiles that still build these images.
