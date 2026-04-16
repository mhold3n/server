# Server ↔ Xlotyl boundary — final report (server repo)

## Summary

`server` is repositioned as the **infrastructure mothership**: Docker/compose orchestration, CI wiring, MCP host packages, observability base, and **deployment of the `xlotyl` submodule** (build contexts, bind mounts, submodule pin). **AI control plane** Python services and the WrkHrs stack live under **`xlotyl/`** only; the server root Python workspace no longer lists those packages as editable members.

## What moved (conceptually)

| Area | From | To |
|------|------|-----|
| API, router, worker, media | `services/*` on server | `xlotyl/services/*` |
| Wiki / RCF helper scripts | `server/scripts/` | `xlotyl/scripts/` |
| Agent platform npm scope | `@server/...` | `@xlotyl/...` (workspace packages) |

## What was deleted from server

- In-tree copies of `services/api-service`, `services/router-service`, `services/worker-service`, `services/media-service` (sources of truth in **xlotyl**).

## What stayed in server

- `docker-compose.yml` and `docker/compose-profiles/*` (with `./xlotyl` build contexts).
- `mcp-servers/` (Phase 6 may still relocate agent-specific MCP).
- Root `pyproject.toml` trimmed to MCP-focused workspace (as implemented on the migration branch).
- `package.json` as `@server/infra-workspace` without mounting xlotyl Node packages.
- `.github/workflows/ci.yml` delegating Python/Node AI checks into `xlotyl/`.

## Remaining boundary debt

- Some **docs** still describe paths like `services/ai-gateway-service` at the server repo root (`docs/migration-wrkhrs-path.md`, parts of `README.md`, legacy ADRs). Prefer **`xlotyl/services/...`** or “see submodule”.
- **`services/topology-viewer`** is listed as an npm workspace but has no `package.json` yet — clean up or add a package.
- **Submodule pointer**: after merging xlotyl branch, bump `xlotyl` in server to that commit and document the tag/ref in release notes.

## Bootstrap commands

### Server (infra + CI parity)

```bash
git submodule update --init --recursive
npm run deps:external   # optional external submodules
uv sync --python 3.11   # MCP / host Python env
# Optional full local CI (needs Docker):
scripts/run_ci_local.sh
```

### Xlotyl (standalone AI product)

```bash
cd xlotyl   # or clone github.com/mhold3n/xlotyl
uv sync --python 3.11
npm ci
npm run build
make lint   # if Makefile targets exist on branch
make test   # per-branch Makefile
```

---

_See also [`server-xlotyl-boundary-manifest.md`](./server-xlotyl-boundary-manifest.md)._
