# xlotyl / server split — path inventory

This document records the **Move / Stay / Split** decision for splitting the AI stack into **`mhold3n/xlotyl`** vs the platform **`mhold3n/server`**.

| Path | Decision | Notes |
|------|----------|--------|
| `services/ai-gateway-service` | **Move** | WrkHrs gateway, RAG, ASR, MCP, tool-registry Dockerfiles |
| `services/agent-platform-service` | **Move** | TS agent platform + open-multi-agent; needs root `package.json` / lock in xlotyl |
| `services/structure-service` | **Move** | structure-gateway in `docker-compose.ai.yml` |
| `services/model-runtime` | **Move** | Dockerfile copies `schemas/`, `engineering-core/` |
| `services/engineering-core` | **Move** | Required by model-runtime editable install |
| `services/mcp-registry-service` | **Move** | Declared in `docker-compose.ai.yml`; mounts `mcp-servers/mcp/config` |
| `services/domain-engineering` | **Move** | Domain packages + optional wiki shards |
| `services/domain-research` | **Move** | |
| `services/domain-content` | **Move** | |
| `services/response-control-framework` | **Move** | In-tree workspace package; standalone git repo remains source for pins |
| `services/ai-shared-service` | **Move** | In-tree; aligns with GHCR image story |
| `services/topology-viewer` | **Move** | AI dev tooling in root `package.json` workspaces |
| `services/api-service` | **Stay** | Birtha control plane; integrates with xlotyl over HTTP |
| `services/router-service` | **Stay** | |
| `services/worker-service` | **Stay** | Worker client |
| `services/queue-service` | **Stay** | |
| `services/mock-openai` | **Stay** | Core compose |
| `services/media-service` | **Stay** | Platform media |
| `services/audio-service` | **Stay** | |
| `services/document-ingest-service` | **Stay** | Addons / ingest; confirm if AI-only later |
| `services/martymedia` | **TBD** | If present as workspace member; default **Stay** with media |
| `docker/compose-profiles/docker-compose.ai.yml` | **Move** | Canonical AI stack |
| `docker/compose-profiles/docker-compose.local-ai.yml` | **Move** | Local overrides |
| `docker/compose-profiles/docker-compose.platform.yml` | **Stay** | Shared MLflow/Qdrant/observability (default) |
| `docker/compose-profiles/docker-compose.server.yml` | **Stay** | Caddy, Pi-hole, WireGuard |
| `docker/compose-profiles/docker-compose.addons.yml` | **Stay** | Homelab profiles |
| `docker/ai-shared-service/Dockerfile` | **Move** | Optional monorepo build of ai-shared-service |
| `docker-compose.yml` | **Stay** | api, router, queue, mock-openai |
| `schemas/` | **Move** (copy) | model-runtime Docker `COPY schemas`; server may keep subset for api if needed |
| `knowledge/wiki` | **Move** | Orchestration sources |
| `knowledge/response-control/*.json` | **Move** | Compiled artifacts; regenerate from wiki in xlotyl CI |
| `mcp-servers/mcp/config` | **Move** (copy) | Read-only mount for `mcp-registry` in AI compose |
| `mcp-servers/mcp/servers/*` (global MCP) | **Stay** | Often used from `docker-compose.server.yml` |
| `scripts/wiki_compile_response_control.py` | **Split** | Prefer live in xlotyl; server CI may call xlotyl or consume vendored JSON |
| `scripts/sync_domain_orchestration_wiki.py` | **Split** | Same |
| Root `pyproject.toml` workspace members | **Split** | Trim server; xlotyl lists AI members + git pins for standalone libs |
| Root `package.json` workspaces | **Split** | xlotyl keeps agent-platform + topology-viewer only |
| `.github/workflows/reusable-python-package-ci.yml` | **Stay** (canonical) | xlotyl may `workflow_call` this repo at a SHA |

## Dependency direction

- **server** pins **xlotyl** via git submodule path `./xlotyl`, git tag in `pyproject.toml`, and/or GHCR images for AI services.
- **api-service** talks to WrkHrs URLs (`wrkhrs-agent-platform`, etc.) already via Docker network; no change to call pattern after split.

## Extraction

See [`scripts/extract_xlotyl_repo.sh`](../../scripts/extract_xlotyl_repo.sh) for automated history-preserving export using `git filter-repo`.
