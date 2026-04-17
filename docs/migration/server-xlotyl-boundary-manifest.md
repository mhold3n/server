# Server ↔ Xlotyl boundary manifest (server repo)

**Update:** The server repo no longer ships a `xlotyl/` subtree; it pins **GHCR image pulls** via [`config/xlotyl-images.env`](../../config/xlotyl-images.env) (`XLOTYL_IMAGE_PREFIX`, `XLOTYL_VERSION`). Historical rows below describe the pre-decoupling layout.

Inventory of paths relevant to separating **infrastructure (`server`)** from the **AI product (`xlotyl`)**.  
Legend: **owner** = repo that should maintain the code; **action** = intended migration step.

| Source path | Target owner | Action | Reason |
|-------------|--------------|--------|--------|
| `xlotyl/services/api-service` | xlotyl | leave (in xlotyl repo) | Birtha ingress API / control plane |
| `xlotyl/services/router-service` | xlotyl | leave | Agent router |
| `xlotyl/services/worker-service` | xlotyl | leave | Worker / model client |
| `xlotyl/services/media-service` | xlotyl | leave | AI media / `martymedia` + domain-content coupling |
| `xlotyl/services/ai-gateway-service` | xlotyl | leave | WrkHrs gateway, RAG, ASR stacks |
| `xlotyl/services/agent-platform-service` | xlotyl | leave | TS agent platform |
| `xlotyl/services/model-runtime`, `engineering-core`, `domain-*`, `response-control-framework`, `mcp-registry-service`, `ai-shared-service`, `structure-service` | xlotyl | leave | AI domains, RCF, runtime |
| `xlotyl/schemas`, `xlotyl/knowledge` | xlotyl | leave | Schemas + orchestration wiki sources |
| `server/services/api-service` (removed) | xlotyl | delete from server | Duplicate ownership eliminated |
| `server/services/router-service` (removed) | xlotyl | delete from server | Same |
| `server/services/worker-service` (removed) | xlotyl | delete from server | Same |
| `server/services/media-service` (removed) | xlotyl | delete from server | Same |
| `docker-compose.yml`, `docker/compose-profiles/*.yml` | server | done (OCI) | Compose stays in server; AI services use **pulled images** (`XLOTYL_IMAGE_PREFIX` / `XLOTYL_VERSION` in `config/xlotyl-images.env`) |
| `mcp-servers/` (implementations in superproject) | xlotyl owns MCP product; server **tracks** paths, compose, CI | leave (tracked mirror) | Canonical catalog/registry in **xlotyl** (`mcp-servers/mcp/config/`); this tree tracks **build/deploy** on primary hardware; optional future move of sources fully into xlotyl |
| `pyproject.toml` (server root) | server | pruned | Workspace limited to host MCP Python packages; no AI monorepo members |
| `package.json` (server root) | server | pruned | `@server/infra-workspace` only; no xlotyl Node workspaces |
| `.github/workflows/ci.yml` | server | done (OCI) | Live-stack tests pull pinned GHCR images; AI package CI lives in **xlotyl** |
| `Makefile` | server | ongoing | Infra targets here; AI dev targets run in a **xlotyl** clone |
| `scripts/run_ci_local.sh`, `scripts/ci_python_lint_paths.sh`, `scripts/bootstrap_tool_env.sh` | server | ongoing | Some scripts still assume a sibling **`XLOTYL_ROOT`** checkout for paths |
| `dev/containers/post-create.sh` | server | rewrite (debt) | Should describe sibling **xlotyl** clone or image-only dev |
| `docs/dev-environment.md`, `docs/external-orchestration-interfaces.md`, ADRs citing `services/api-service` at repo root | server | ongoing | Docs should describe **GHCR pins** + optional **xlotyl** clone for sources |
| `docs/migration-wrkhrs-path.md` | server | rewrite (debt) | Still references old `services/ai-gateway-service` at server root in places |
| `KNOWLEGE MINUTES EXCLUDED.md` (server root) | server or xlotyl | leave / copy | Policy source; **copy** exists under `xlotyl/` for standalone `xlotyl` tests |

## Node workspace naming (xlotyl)

| Item | Owner | Action |
|------|-------|--------|
| Root workspace name `@xlotyl/root-workspace` | xlotyl | done |
| `@xlotyl/open-multi-agent`, `@xlotyl/agent-platform-server` | xlotyl | done |
| `services/topology-viewer` workspace (no `package.json` yet) | xlotyl | debt — npm may warn until package exists or workspace entry removed |

## Makefile targets (server → xlotyl split)

| Target | Owner after split |
|--------|-------------------|
| `ai-up`, `ai-down`, `logs-ai`, wiki*, smoke*, `eval`, API/router/worker test/lint | xlotyl primary; server may thin-wrap `make -C xlotyl` |
| `platform-up`, observability, `server-up`, networking, security | server |

---

_Doc path sweep (WrkHrs migration + dev-environment + external orchestration links): applied alongside topology-viewer `package.json`._

_Generated during `refactor/remove-ai-ownership-use-xlotyl-only` / xlotyl `refactor/import-ai-control-plane-from-server`._
