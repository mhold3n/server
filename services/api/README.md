Agent Orchestrator API

Scaffolded control plane endpoints added:

- VMs: `GET /api/vms`, `POST /api/vms/{vmid}/start`, `POST /api/vms/{vmid}/stop`
- Torrents (qBittorrent): `GET /api/torrents`, `POST /api/torrents/add`, `POST /api/torrents/pause`, `POST /api/torrents/resume`
- Search (Spotlight): `GET /api/search?q=...&kind=all|files|web`, `GET /api/search/files`, `GET /api/search/web`
- Apps: `GET /api/apps` (reachability), `POST /api/apps/{id}/restart` (501 placeholder)
- AI: `POST /api/ai/query` (router or AI stack), `POST /api/ai/workflows/run` (code-rag/media-fixups/sysadmin-ops), `POST /api/ai/simulations/analyze`
  - Status: `GET /api/ai/status` (aggregated: worker, router, ai-stack, MCPs)
  - MCP: `GET /api/ai/mcp/servers`, `POST /api/ai/mcp/servers/{name}/enable`, `GET /api/ai/mcp/servers/{name}/tools`, `POST /api/ai/mcp/call`

Configuration (env):

- Proxmox: `PROXMOX_BASE_URL`, `PROXMOX_TOKEN_ID`, `PROXMOX_TOKEN_SECRET`, `PROXMOX_VERIFY_SSL=false`
- qBittorrent: `QB_BASE_URL`, `QB_USERNAME`, `QB_PASSWORD`
- Meilisearch: `MEILI_URL`, `MEILI_API_KEY`, `MEILI_INDEX=files`
- SearXNG: `SEARX_URL`
- Router/AI stack: `ROUTER_URL=http://router:8000`, `AI_STACK_URL=http://ai-stack:8090`
- AI Repos for workflows: `AI_REPOS` (comma-separated), defaults include this monorepo (`server`) and marker
- Marker paths (optional): `MARKER_DOCS_DIR`, `MARKER_PROCESSED_DIR`
- Hosted API brain (optional escalation): `API_BRAIN_ENABLED=false`, `API_BRAIN_BASE_URL`, `API_BRAIN_API_KEY`, `API_BRAIN_MODEL`
  - Controls: `API_BRAIN_MAX_ESCALATIONS_PER_TASK=1`, `API_BRAIN_TEXT_ONLY=true`
  - Safeties: `API_BRAIN_ALLOW_RAW_SCREENSHOTS=false`, `API_BRAIN_ALLOW_RAW_PDFS=false`, `API_BRAIN_ALLOW_FULL_LOGS=false`, `API_BRAIN_ALLOW_FULL_REPO_CONTEXT=false`

Notes

- Restart is intentionally stubbed (Docker socket is not mounted in `api`).
- Endpoints return graceful 5xx/501 when backing services are not configured.

Server override

- `docker-compose.server.yml` mounts `/var/run/docker.sock` into `api` so `/api/apps/{id}/restart` can actually restart compose-managed containers by service name.
UI

- VMs panel: `/ui/vms/` (start/stop VMs)
- AI & Agents panel: `/ui/ai/` (status, chat, workflows, simulations, MCP server toggles, agents roster)
