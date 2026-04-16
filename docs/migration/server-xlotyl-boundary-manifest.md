# Server ↔ Xlotyl boundary manifest (server repo)

Inventory of paths relevant to separating **infrastructure (`server`)** from the **AI product (`xlotyl`)**.  
Legend: **owner** = repo that should maintain the code; **action** = intended migration step.

| Source path | Target owner | Action | Reason |
|-------------|--------------|--------|--------|
| `xlotyl/services/api-service` | xlotyl | leave (in submodule) | Birtha ingress API / control plane |
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
| `docker-compose.yml`, `docker/compose-profiles/*.yml` | server | rewrite | Compose stays in server; **build contexts** point at `./xlotyl/...` for AI images |
| `mcp-servers/` | server | leave (for now) | Host-adjacent MCP; Phase 6 may move agent-only servers into xlotyl |
| `pyproject.toml` (server root) | server | pruned | Workspace limited to host MCP Python packages; no AI monorepo members |
| `package.json` (server root) | server | pruned | `@server/infra-workspace` only; no xlotyl Node workspaces |
| `.github/workflows/ci.yml` | server | rewrite | CI runs Python/Node checks under `xlotyl/` where AI code lives |
| `Makefile` | server | rewrite | Infra + delegate AI dev targets to `$(MAKE) -C xlotyl` where applicable |
| `scripts/run_ci_local.sh`, `scripts/ci_python_lint_paths.sh`, `scripts/bootstrap_tool_env.sh` | server | rewrite | Paths under `xlotyl/services/...` |
| `dev/containers/post-create.sh` | server | rewrite | Editable installs from `/workspace/xlotyl/services/...` |
| `docs/dev-environment.md`, `docs/external-orchestration-interfaces.md`, ADRs citing `services/api-service` at repo root | server | rewrite (debt) | Docs should say AI services live under **submodule** `xlotyl/` |
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
