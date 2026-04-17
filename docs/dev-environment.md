# Development environment

## Single clone (recommended)

Work from the **[github.com/mhold3n/server](https://github.com/mhold3n/server)** checkout. **Infra**, compose, host **MCP** servers, and deployment glue live here. The **Birtha / WrkHrs AI stack** runs from **published OCI images**; registry prefix and tag are pinned in [`config/xlotyl-images.env`](../config/xlotyl-images.env) (`XLOTYL_IMAGE_PREFIX`, `XLOTYL_VERSION`). This repo **does not** ship a `./xlotyl` product tree.

For **product source** (Python services, wiki, agent-platform, OpenClaw submodules inside xlotyl), clone **[XLOTYL/xlotyl](https://github.com/XLOTYL/xlotyl)** beside this repo (default sibling **`../xlotyl`**, overridable with **`XLOTYL_ROOT`** in scripts). Legacy MBMH materials: `../server-local-archive/2026-04-08/server/`.

Cloning additional “legacy” projects **inside** this repository root increases confusion (two trees, two sets of commands, easy to edit the wrong copy). Prefer:

- **Same machine:** keep **server** and **xlotyl** as sibling directories, e.g. `~/work/server` and `~/work/xlotyl`, not nested.
- **This repo only:** run CI parity with [`scripts/run_ci_local.sh`](../scripts/run_ci_local.sh) from the repository root (Compose pulls pinned images per `config/xlotyl-images.env`).

How **on-premises backups** relate to **GitHub**: [`infrastructure-and-git.md`](infrastructure-and-git.md).

### GitHub Actions: private checkouts (if you add submodules later)

[`actions/checkout`](https://github.com/actions/checkout) can use `secrets.SUBMODULE_CLONE_TOKEN` when the repo has **private submodules** listed in `.gitmodules`. The **server** repo’s default CI path today is a **flat checkout** plus **Docker pulls** for the AI stack; no xlotyl submodule is required. If you reintroduce private submodules, add a PAT with read access to those repositories.

## Workspace bootstrap

- **Standalone package tags:** the root [`pyproject.toml`](../pyproject.toml) pins `response-control-framework`, `ai-shared-service`, and each `domain-*` package with **`git` + `tag`**. For CI and local scripts, override the tag with **`DOMAIN_PACKAGES_TAG`** if needed; otherwise tooling reads the tag from TOML. After bumping a tag, run **`uv lock`** (and **`make vendor-rcf-schemas`** when `response-control-framework` schemas changed).
- Main Python workspace: `uv sync --python 3.11`
- Agent-platform / topology Node workspaces: run **`npm ci`** from your **xlotyl** clone (e.g. `cd "${XLOTYL_ROOT:-../xlotyl}" && npm ci`). Root [`package.json`](../package.json) here is infra-only.
- Focused tool envs: `scripts/bootstrap_tool_env.sh marker-pdf|whisper-asr|qwen-runtime|larrak-audio`
- Full AI Docker dev stack: `make up`
- Docker topology validation: `make docker-validate`
- Shared local caches and model state live under `./.cache/` (see below).

## Standalone package repos (shared CI)

The five libraries pinned in [`pyproject.toml`](../pyproject.toml) (`response-control-framework`, `ai-shared-service`, `domain-engineering`, `domain-research`, `domain-content`) each live in their own GitHub repo. **CI is centralized** in this repo:

- **Reusable workflow:** [`.github/workflows/reusable-python-package-ci.yml`](../.github/workflows/reusable-python-package-ci.yml) (`workflow_call`) runs `pip install -e ".[<extras>]"`, `ruff`, `mypy --strict`, and `pytest` with caller-supplied paths.

**Callers** in each package repo use a thin `.github/workflows/ci.yml` that invokes:

`uses: mhold3n/server/.github/workflows/reusable-python-package-ci.yml@<ref>`

**Pinning `ref`:** Prefer a **commit SHA** or a **tag on `mhold3n/server`** (e.g. `@v2026.04.15`) instead of bare `@main`, so changes on server `main` do not silently break standalone repos. After updating the reusable workflow API (inputs), tag server and bump the `@ref` in each caller.

**Permissions:** For a **public** `mhold3n/server`, `contents: read` on the caller is enough. Cross-repo reusable workflows require the caller repo to be allowed to use workflows from server (default for public repos). **Private** server or private callers may need org settings and/or `GITHUB_TOKEN` scopes documented by GitHub.

**Copy-ready caller snippets** live under [`docs/templates/standalone-repos/`](../docs/templates/standalone-repos/) (one YAML per package). Step-by-step apply and PRs: [apply-standalone-ci-callers.md](runbooks/apply-standalone-ci-callers.md). **Branch protection** and **release/tag workflow** with the super-project: [standalone-branch-protection.md](runbooks/standalone-branch-protection.md), [releases-standalone-packages.md](releases-standalone-packages.md) (root of `docs/`).

## Orchestration wiki (response-control catalogs)

All wiki sources, `make wiki-compile` / `make wiki-check`, and response-control JSON **live in the xlotyl product repo** — not under this server checkout. Use your **xlotyl** clone (`XLOTYL_ROOT`, default `../xlotyl`). Browse on GitHub: [knowledge/wiki](https://github.com/XLOTYL/xlotyl/tree/main/knowledge/wiki), [knowledge/wiki/orchestration](https://github.com/XLOTYL/xlotyl/tree/main/knowledge/wiki/orchestration) (see [SCHEMA.md](https://github.com/XLOTYL/xlotyl/blob/main/knowledge/wiki/SCHEMA.md)), [knowledge/wiki/projects](https://github.com/XLOTYL/xlotyl/tree/main/knowledge/wiki/projects).

- **Domain wiki merge:** orchestration markdown is authored under `services/domain-research/wiki/orchestration/` and `services/domain-content/wiki/orchestration/` **inside xlotyl**; the xlotyl Makefile runs `scripts/sync_domain_orchestration_wiki.py` before compilation.
- **Compile / drift / proposals:** run **`make wiki-compile`**, **`make wiki-check`**, **`make wiki-proposals-check`**, **`make wiki-promote`** from the **xlotyl** repository root (see that repo’s `Makefile`).
- **Bootstrap** (rare): from the **xlotyl** root, `uv run python scripts/wiki_compile_response_control.py --migrate-from-json` as documented there.

See [wiki-editorial-governance.md](runbooks/wiki-editorial-governance.md) for the head-editor workflow (`PROPOSED -> APPROVED -> PROMOTED/REJECTED`) and API control endpoints.

After editing orchestration pages, commit changes **in the xlotyl repo** (wiki sources and regenerated `knowledge/response-control/*.json`). Avoid hand-editing the JSON long-term; treat it as a build artifact of the wiki.

## Local dev caches (`CACHE_ROOT`)

Shell entrypoints (`Makefile`, `scripts/run_ci_local.sh`, `scripts/bootstrap_tool_env.sh`, etc.) use [`scripts/workspace_env.sh`](../scripts/workspace_env.sh), which sources [`scripts/cache_env.sh`](../scripts/cache_env.sh) to export a **single root** and consistent children. Default: **`CACHE_ROOT=<repo>/.cache`**.

**Canonical layout** (do not point `UV_CACHE_DIR` and `NPM_CONFIG_CACHE` at the same directory; each tool owns its subtree):

```text
.cache/
  uv/                 # UV_CACHE_DIR — uv wheel/source cache
  npm/                # NPM_CONFIG_CACHE — npm download cache (node_modules stays at repo root)
  models/
    hf/               # HF_HOME, TRANSFORMERS_CACHE, MODEL_CACHE_DIR
    whisper/          # WHISPER_CACHE_DIR
  envs/               # TOOL_ENV_ROOT (e.g. qwen-runtime venv)
  xdg/                # XDG_CACHE_HOME
  ruff/               # RUFF_CACHE_DIR
  mypy/               # MYPY_CACHE_ROOT
  pytest/             # PYTEST_CACHE_ROOT
```

To move all caches and HF snapshots to a larger disk, set **`CACHE_ROOT`** to an absolute path before sourcing `workspace_env.sh` (or use **`HARNESS_CACHE_ROOT`** for [`scripts/prove_engineering_harness.sh`](../scripts/prove_engineering_harness.sh) only). **`node_modules/`** remains the npm workspace install tree at the repository root.

## Docker persistent data (`COMPOSE_DATA_ROOT`)

Compose stacks store databases, caches, and logs on the host under **`COMPOSE_DATA_ROOT`**. If unset, the default is **`.docker-data/`** at the repository root (ignored by git). Set `COMPOSE_DATA_ROOT` to an absolute path when you want data on a removable drive or a larger disk, for example:

- macOS: `COMPOSE_DATA_ROOT=/Volumes/YourDrive/server-data`
- Linux: `COMPOSE_DATA_ROOT=/mnt/external/server-data` (existing servers that used `/mnt/appdata` can set `COMPOSE_DATA_ROOT=/mnt/appdata` so addon paths stay `.../addons/...` on disk)
- Windows (Docker Desktop): `COMPOSE_DATA_ROOT=D:/server-data` (forward slashes are fine in `.env`)

The [`Makefile`](../Makefile) runs `docker compose --project-directory <repo root>` so relative paths in all compose fragments resolve consistently. Copy-pasted `docker compose -f ...` commands from docs should include **`--project-directory "$(pwd)"`** (from the repo root; quoted form is safe if the path contains spaces) for the same behavior.

Subdirectories under the root are stable (`platform/postgres`, `ai/logs`, `addons/...`, `worker/ollama_data`, etc.); see compose files under [`docker/compose-profiles/`](../docker/compose-profiles/).

### Migrating from old Docker named volumes

After pulling these changes, **named volumes** from earlier compose definitions are no longer used for most services; data is read from host paths under `COMPOSE_DATA_ROOT` instead.

1. Stop the stack: `make down`, or from the repo root use the same `-f` files as for `make up` with `docker compose --project-directory "$(pwd)" ... down`.
2. For each former volume (e.g. `agent-orchestrator_postgres_data`; list with `docker volume ls`), copy data into the new bind path (example for Postgres):

   ```bash
   docker run --rm \
     -v agent-orchestrator_postgres_data:/from:ro \
     -v "$(pwd)/.docker-data/platform/postgres:/to" \
     alpine cp -a /from/. /to/
   ```

   Adjust the **left** volume name and the **right** host path to match [docker-compose.platform.yml](../docker/compose-profiles/docker-compose.platform.yml) and your `COMPOSE_DATA_ROOT`.
3. Bring the stack up again and verify health; only then remove old volumes if you no longer need them.

The standalone WrkHrs compose under **`services/ai-gateway-service/compose/`** in the **xlotyl** repo ([tree](https://github.com/XLOTYL/xlotyl/tree/main/services/ai-gateway-service/compose)) defaults to **`${COMPOSE_DATA_ROOT:-.docker-data}/ai-gateway/`** for its bind-mounted volumes; override with `QDRANT_DATA_PATH`, `RAG_CACHE_PATH`, etc. if you need custom locations.

### Copying large trees to a removable drive (reliable, headless)

**Do not** rely on Finder for multi‑GB trees if the source is under **iCloud Drive** (Desktop/Documents sync, etc.): you can end up with **0‑byte placeholders** on the USB. Ensure files are **fully downloaded** first (e.g. right‑click **Download Now**, or temporarily disable **Optimize Mac Storage**, or copy from a path that is entirely on local disk).

Use **`rsync`** from Terminal for resumable, scriptable copies. This repo includes [`scripts/sync_to_volume.sh`](../scripts/sync_to_volume.sh):

```bash
chmod +x scripts/sync_to_volume.sh
DRY_RUN=1 ./scripts/sync_to_volume.sh /path/to/source /Volumes/ESD-USB/destination   # preview
./scripts/sync_to_volume.sh /path/to/source /Volumes/ESD-USB/destination
```

Then verify sizes match: `du -sh /path/to/source /Volumes/ESD-USB/destination`.

## Root `.gitignore` and sibling folders

Patterns for ignored sibling scratch trees are **safety rails**: they reduce the chance of accidentally `git add`-ing a large unrelated tree that happens to sit next to your clone. They are **not** required checkouts for developing this repo.

If you keep an old mirror inside the ignored path for personal reference, treat it as **read-only scratch space**; do not treat it as a second source of truth for platform code.

## One-shot fullstack e2e (Docker + OpenClaw + checks)

From the repo root, **`make fullstack-e2e`** runs [`dev/scripts/fullstack_e2e_bootstrap.sh`](../dev/scripts/fullstack_e2e_bootstrap.sh): the same compose stack as **`make up`**, ordered **HTTP health waits** (Birtha API, agent-platform, router; optional wrkhrs-gateway with `E2E_WAIT_GATEWAY=1`), a **fast `POST /api/ai/query`** smoke, an optional **strict-engineering** live smoke (`E2E_STRICT_ENGINEERING_SMOKE=1`), optional **SSE** read (`E2E_SSE_SMOKE=1`), a **curated host pytest** subset under **`${XLOTYL_ROOT:-../xlotyl}/services/api-service`** (default on; disable with `E2E_PYTEST=0`), **`pnpm install`** (and **`pnpm build`** if `dist/` is missing) under **`${XLOTYL_ROOT:-../xlotyl}/openclaw`**, then **`pnpm ui:build`** when **`openclaw/dist/control-ui/`** is missing there (so OpenClaw **Control** `/chat` has assets; the gateway’s own auto-build often lacks `pnpm` on PATH), then an optional **managed OpenClaw gateway** (`node openclaw.mjs gateway run --port …`, default on via `E2E_MANAGED_OPENCLAW_GATEWAY=1`). **`make fullstack-e2e-down`** stops the managed gateway PID and, only if `E2E_TEARDOWN_DOCKER=1`, runs **`docker compose down`** with the same `-f` files so your default dev stack is not torn down by mistake.

**Ports (host defaults):** Birtha `API_PORT` (8080), agent-platform `WRKHRS_AGENT_PLATFORM_PORT` (8087), router `ROUTER_PORT` (8000), wrkhrs-gateway `WRKHRS_GATEWAY_PORT` (8091). OpenClaw gateway listen port: `OPENCLAW_GATEWAY_PORT` (default 18789).

**OpenClaw managed gateway (isolated state on Apple Silicon + host Ollama):** the bootstrap writes `${CACHE_ROOT:-.cache}/e2e-bootstrap/openclaw-managed-state/openclaw.json` with **`gateway.auth.mode`** **`token`** and **`gateway.auth.token`** (plaintext dev default). Override with **`E2E_OPENCLAW_GATEWAY_TOKEN`**; default is **`openclaw-dev`** — easiest login on **this Mac’s browser** (not the IDE embedded tab): open **`http://127.0.0.1:${OPENCLAW_GATEWAY_PORT:-18789}/#token=openclaw-dev`** (Control reads the token from the URL fragment). Or use the connect form: **`ws://127.0.0.1:${OPENCLAW_GATEWAY_PORT:-18789}`** and paste the token before Connect (empty token yields “gateway token missing”). The same file sets a **relaxed `gateway.auth.rateLimit`** for local dev; repeated wrong attempts can still trigger **“too many failed authentication attempts”** — **restart the managed gateway** (`make fullstack-e2e-down` then `make fullstack-e2e`) to clear in-memory counters, or wait for the lockout window. With **`OPENCLAW_STATE_DIR`** pointing at that managed-state dir, you can run **`openclaw dashboard`** from **`openclaw/`** for a tokenized URL. Set **`E2E_OPENCLAW_USE_HOME_STATE=1`** to skip isolated state and use **`~/.openclaw`** instead (then set **`gateway.auth.token`** or run **`openclaw config set`** as needed).

**Apple Silicon (Darwin arm64):** [`make fullstack-e2e`](../Makefile) and [`dev/scripts/e2e_stack_up.sh`](../dev/scripts/e2e_stack_up.sh) assume **host-installed [Ollama](https://ollama.com)** (CLI on `PATH`). If the daemon is not listening yet, the script runs **`ollama serve`** in the background and waits for **`/api/tags`** (logs under `${CACHE_ROOT:-.cache}/e2e-bootstrap/ollama-serve.log`; disable with **`E2E_AUTO_START_OLLAMA=0`** if you only use the menu-bar app and want a hard failure when it is not already up). Metal-backed inference is not exposed to generic Linux containers on Docker Desktop the way NVIDIA GPUs are on Linux, so containers call the host via `host.docker.internal` (see `extra_hosts` on **wrkhrs-agent-platform** in [`docker/compose-profiles/docker-compose.ai.yml`](../docker/compose-profiles/docker-compose.ai.yml)). The scripts verify `ollama` is on `PATH`, `http://127.0.0.1:${OLLAMA_HOST_PORT:-11434}/api/tags` responds, and **`qwen3:4b-instruct`** is listed (planned Qwen lane, aligned with **`Qwen/Qwen3-4B`** in [`docker-compose.local-ai.yml`](../docker/compose-profiles/docker-compose.local-ai.yml)); run **`ollama pull qwen3:4b-instruct`** first, or set **`OLLAMA_MODEL`** / **`E2E_SMOKE_MODEL`**, or **`E2E_OLLAMA_SKIP_MODEL_CHECK=1`** to skip the name check only. Then they export `LLM_BACKEND=ollama`, `LLM_RUNNER_URL`, `OLLAMA_MODEL`, and `OPENAI_BASE_URL` …`/v1` for compose. To keep the default **model-runtime** lane instead, set `E2E_USE_HOST_OLLAMA=0`. A shell under Rosetta that reports `uname -m` as `x86_64` does **not** enable this path—use a native arm64 terminal. `E2E_USE_GPU_WORKER` does not attach [`docker-compose.worker.yml`](../docker/compose-profiles/docker-compose.worker.yml) on Apple Silicon unless `E2E_ALLOW_GPU_WORKER_ON_DARWIN_ARM64=1`.

**OpenClaw workspace config** (enable `birtha-bridge`, set `birthaApiBaseUrl`) remains **outside git** unless you explicitly opt into a local JSON merge: `E2E_OPENCLAW_CONFIG_PATCH=1` **and** `--i-accept-local-config-merge` **and** `OPENCLAW_CONFIG_JSON` pointing at a file **`jq`** can rewrite. Otherwise the script prints a small JSON snippet matching [birtha-bridge `openclaw.plugin.json`](https://github.com/XLOTYL/xlotyl/blob/main/openclaw/extensions/birtha-bridge/openclaw.plugin.json) in the **xlotyl** tree.

**Extension hook:** after a successful run, if [`dev/scripts/e2e_hooks/post_up.sh`](../dev/scripts/e2e_hooks/post_up.sh) exists (gitignored), it is **sourced** non-fatally—copy from [`post_up.sh.example`](../dev/scripts/e2e_hooks/post_up.sh.example) to add IDE-specific steps.

**Compose hygiene:** **`make up`**, **`make up-gpu`**, **`make fullstack-e2e`**, and **`e2e_stack_up.sh`** use `docker compose up -d --remove-orphans` for the same full-dev `-f` chain; **`make down`** uses `down --remove-orphans`. That drops containers for services **removed or renamed** in the compose graph instead of leaving orphans. None of these run `down` before `up`: the project stays **`name: agent-orchestrator`** in [`docker-compose.yml`](../docker-compose.yml), so a normal re-run **reconciles** one stack (not duplicate API containers per run). Runaway counts usually mean different **`COMPOSE_PROJECT_NAME`** / working directories, manual **`docker run`**, or **`--scale`**.

**Typical toggles:** `E2E_SKIP_DOCKER=1` (stack already up), `E2E_SKIP_NODE_BOOTSTRAP=1` (Docker-only; skips Node/OpenClaw), `E2E_UV_SYNC=1` (slow; sync Python env at repo root before pytest), `--` then extra args for `docker compose up -d` (e.g. `--build`).

## Strict engineering, DevPlane, and model-runtime (env matrix)

Canonical operational detail for health checks and ports: [runbooks/ai-stack-operations.md](runbooks/ai-stack-operations.md). Hugging Face weights and **`MOCK_INFER`**: [local-hf-models.md](local-hf-models.md) (especially §4).

Use one Docker network profile so hostnames below resolve (for example root [`docker-compose.yml`](../docker-compose.yml) plus [`docker/compose-profiles/docker-compose.platform.yml`](../docker/compose-profiles/docker-compose.platform.yml) and [`docker/compose-profiles/docker-compose.ai.yml`](../docker/compose-profiles/docker-compose.ai.yml)).

| Variable | Service consuming it | Purpose |
|----------|------------------------|---------|
| `AGENT_PLATFORM_URL` or `ORCHESTRATOR_AGENT_PLATFORM_URL` | **`api`** ([Settings](https://github.com/XLOTYL/xlotyl/blob/main/services/api-service/src/config.py)) | Base URL for `POST /v1/workflows/execute` and DevPlane `POST /v1/devplane/runs`. **`AGENT_PLATFORM_URL` wins** if both are set. |
| `ORCHESTRATOR_API_URL` or `DEVPLANE_PUBLIC_BASE_URL` | **`wrkhrs-agent-platform`** ([engineering-graph](https://github.com/XLOTYL/xlotyl/blob/main/services/agent-platform-service/server/src/workflow/engineering-graph.ts)) | Control plane `POST /api/control-plane/engineering/*`, dossier `GET /api/dev/tasks/{id}/dossier`, run events `POST /api/dev/runs/{id}/events`. |
| `DEVPLANE_PUBLIC_BASE_URL` | **`api`** ([Settings](https://github.com/XLOTYL/xlotyl/blob/main/services/api-service/src/config.py)) | Callback URLs embedded in DevPlane run create (`/api/dev/runs/.../events`, `/complete`); must be reachable **from** agent-platform (often `http://api:8080` on the compose network). |
| `MODEL_RUNTIME_URL` | **`wrkhrs-agent-platform`** | Required for strict **`multimodal_model`** (`POST /infer/multimodal` on model-runtime). |
| `MOCK_INFER` | **`model-runtime`** | `1` = stub `/infer/*` (no torch load); `0` = real HF per [`models.yaml`](https://github.com/XLOTYL/xlotyl/blob/main/services/model-runtime/config/models.yaml). |
| `HF_TOKEN` / `HUGGINGFACE_HUB_TOKEN`, `HF_HOME`, cache dirs | **`model-runtime`**, RAG, ASR | Hub auth and shared weight cache; see [Local dev caches](#local-dev-caches-cache_root) above. |
| `LLM_BACKEND` | **`wrkhrs-agent-platform`** | `mock` (default in compose) skips real Claw/OMA/multimodal inside **DevPlane** `executeBackendRun` ([runner](https://github.com/XLOTYL/xlotyl/blob/main/services/agent-platform-service/server/src/devplane/runner.ts)); use a real backend for executor smoke. |
| `OMA_DEFAULT_PROVIDER`, `OMA_DEFAULT_MODEL`, `OMA_DEFAULT_API_KEY`, `OMA_DEFAULT_BASE_URL` | **`wrkhrs-agent-platform`** | Merged OMA route for `local_general_model` / `strategic_reviewer` ([runtime-router](https://github.com/XLOTYL/xlotyl/blob/main/services/agent-platform-service/server/src/orchestration/runtime-router.ts)). |
| `CLAW_CODE_BINARY`, `CLAW_CODE_MODEL`, `CLAW_CODE_TRUSTED_ROOTS`, timeouts | **`wrkhrs-agent-platform`** | `coding_model` → Claw ([config](https://github.com/XLOTYL/xlotyl/blob/main/services/agent-platform-service/server/src/config.ts)). |

## AI stack location

The active WrkHrs-derived gateway stack lives under **`services/ai-gateway-service/`** in the **xlotyl** product repository. Historical links to `WrkHrs/` or `services/wrkhrs/` at the server repo root are obsolete; see [migration-wrkhrs-path.md](migration-wrkhrs-path.md).
