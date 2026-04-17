# xlotyl / server split — path inventory

**Status:** Superseded by the executed migration. Canonical inventory: [`docs/migration/server-xlotyl-boundary-manifest.md`](../migration/server-xlotyl-boundary-manifest.md) and [`xlotyl/docs/migration/server-xlotyl-boundary-manifest.md`](../../xlotyl/docs/migration/server-xlotyl-boundary-manifest.md). This draft is kept for historical context only.

This document recorded the **Move / Stay / Split** decision for splitting the AI stack into **`XLOTYL/xlotyl`** (canonical product org) vs the platform **`mhold3n/server`**.

| Path | Decision (historical) | Actual outcome |
|------|----------------------|----------------|
| `services/ai-gateway-service` | **Move** | Lives under **`xlotyl/services/ai-gateway-service/`**; server compose uses `./xlotyl/...` build context |
| `services/agent-platform-service` | **Move** | Under **`xlotyl/services/agent-platform-service/`** |
| `services/structure-service` | **Move** | Under **`xlotyl/services/structure-service/`** |
| `services/model-runtime` | **Move** | Under **`xlotyl/services/model-runtime/`** |
| `services/engineering-core` | **Move** | Under **`xlotyl/services/engineering-core/`** |
| `services/mcp-registry-service` | **Move** | Under **`xlotyl/services/mcp-registry-service/`** |
| `services/domain-*` | **Move** | Under **`xlotyl/services/domain-*`** |
| `services/response-control-framework` | **Move** | Under **`xlotyl/services/response-control-framework/`** (standalone git repo remains for pins) |
| `services/ai-shared-service` | **Move** | Under **`xlotyl/services/ai-shared-service/`** |
| `services/topology-viewer` | **Move** | Under **`xlotyl/services/topology-viewer/`** |
| `services/api-service` | Was **Stay** | **Moved** to **`xlotyl/services/api-service/`** |
| `services/router-service` | Was **Stay** | **Moved** to **`xlotyl/services/router-service/`** |
| `services/worker-service` | Was **Stay** | **Moved** to **`xlotyl/services/worker-service/`** |
| `services/media-service` | Was **Stay** | **Moved** to **`xlotyl/services/media-service/`** |
| `services/queue-service` | **Stay** | Remains on **server** (platform) |
| `services/mock-openai` | **Stay** | Platform compose |
| `services/audio-service` | **Stay** | Platform / audio |
| `services/document-ingest-service` | **Stay** | Addons / ingest |
| `docker/compose-profiles/docker-compose.ai.yml` | Was **Move** | **Stay** on server; references **`./xlotyl/...`** contexts |
| `docker/compose-profiles/docker-compose.platform.yml` | **Stay** | Shared MLflow/Qdrant/observability |
| `docker-compose.yml` | **Stay** | Server root; API/router bind mounts **`./xlotyl/services/...`** |
| `schemas/` (product) | **Move** | Orchestration/OpenClaw schemas under **`xlotyl/schemas/`** |
| `knowledge/wiki`, `knowledge/response-control` | **Move** | Under **`xlotyl/knowledge/`** |
| `mcp-servers/mcp/servers/*` | **Stay** | Host MCP; Phase 6 may relocate agent-only servers |
| Root `pyproject.toml` / `package.json` | **Split** | Server trimmed to infra + MCP; **`xlotyl`** owns AI workspace |

## Dependency direction

- **server** pins **xlotyl** via git submodule at `./xlotyl` and compose build contexts.
- **api-service** (in xlotyl) talks to WrkHrs URLs over the Docker network unchanged.
