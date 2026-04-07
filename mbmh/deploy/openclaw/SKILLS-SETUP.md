# OpenClaw bundled skills: the “42 blocked” situation

Run this any time:

```bash
openclaw skills check
```

You will see **~50 total**, **~8 eligible**, **~42 missing requirements**. That is **normal**: bundled skills are optional integrations (CLIs, API keys, channels). You do **not** need to “unblock” all 42 unless you intentionally want every integration.

## High priority: `coding-agent` and Whisper

### `coding-agent` (spawn Codex / Claude Code / etc.)

The skill needs **at least one** of these on `PATH`: `claude`, `codex`, `opencode`, `pi`. Install globally with npm (binaries land under Homebrew’s prefix, which the gateway `PATH` already includes):

```bash
npm install -g @anthropic-ai/claude-code
npm install -g @openai/codex
```

Then `openclaw skills info coding-agent` should show **Ready**, and `openclaw gateway restart` ensures the service sees the same `PATH`.

### `openai-whisper-api` vs `openai-whisper`

- **`openai-whisper`** — local/offline transcription (separate skill). It does **not** use `OPENAI_API_KEY`.
- **`openai-whisper-api`** — calls OpenAI’s hosted **Audio Transcriptions** API; it requires **`OPENAI_API_KEY`** (or `skills.entries["openai-whisper-api"].apiKey` in `openclaw.json`).

To hydrate the API skill with the same pipeline as the other env-driven skills, add a **Login** (or Password) item in 1Password named **`openai`** in the vault your map uses (e.g. `Personal`), with a field **`apiKey`** holding your [OpenAI API key](https://platform.openai.com/api-keys). That matches `op://Personal/openai/apiKey` in `~/.openclaw/skill-secrets-map.json`. Run `eval "$(op signin)"`, then `python3 ~/.openclaw/bin/sync-skill-secrets.py`, then `openclaw gateway restart`. Until that item exists, sync will list `env:OPENAI_API_KEY` under `unresolved` in `secret-sync-report.json`.

One-off without 1Password (not recommended for long-term): `openclaw config set skills.entries.openai-whisper-api.apiKey 'sk-…'` then restart the gateway.

## Strategies

### 1. Do nothing (recommended default)

Use the **8 ready** skills (`gh-issues`, `github`, `healthcheck`, `imsg`, `node-connect`, `skill-creator`, `video-frames`, `weather`) and ignore the rest. Built-in OpenClaw tools (chat, exec, browser, etc.) still work; **skills** are extra playbooks.

### 2. Enable only what you need

Pick rows from `openclaw skills check` → **Missing requirements** and fix **only** those:

| Requirement type | What to do |
|------------------|------------|
| `bins: foo` | Install the binary (often `brew install …`; name may differ, e.g. `rg` → `brew install ripgrep`) |
| `env: VAR` | Export `VAR` or set `skills.entries."skill-name".env` / secrets in `~/.openclaw/openclaw.json` ([Skills config](https://docs.openclaw.ai/tools/skills-config)) |
| `config: channels.*` | Configure that channel in `openclaw.json` (Discord, Slack, BlueBubbles, etc.) |
| `anyBins: a, b, c` | Install **at least one** of the listed CLIs |

Docs: [Skills](https://docs.openclaw.ai/tools/skills), [Skills config](https://docs.openclaw.ai/tools/skills-config).

### 3. Turn off skills you will never use

If the UI noise bothers you, disable specific bundled skills:

```json5
{
  skills: {
    entries: {
      "spotify-player": { enabled: false },
      sonoscli: { enabled: false },
    },
  },
}
```

Optional **allowlist** (only these bundled skills can load):

```json5
{
  skills: {
    allowBundled: ["github", "gh-issues", "weather", "healthcheck", "skill-creator"],
  },
}
```

Restart the gateway after edits.

## Hydrating API-key skills (Bitwarden Secrets Manager + `sync-skill-secrets.py`)

This repo is migrating automation secrets from 1Password to **Bitwarden Secrets Manager**.

### 1) Create a machine account + access token

In the Bitwarden web vault:

- Create a **Machine account**
- Create an **Access token**
- Save the access token securely (it can’t be retrieved later)

### 2) Install `bws`

Install the Bitwarden Secrets Manager CLI (`bws`) on the host running OpenClaw.

Docs: `https://bitwarden.com/help/secrets-manager-cli/`

### 3) Provide `BWS_ACCESS_TOKEN` to OpenClaw

Create an env file (outside git) in one of these locations:

- `~/.openclaw/bws.env` (per-user)
- `/mnt/appdata/server/secrets/bitwarden-sm/bws.env` (centralized on Linux deploy host)
- `~/Library/Application Support/server/secrets/bitwarden-sm/bws.env` (centralized on macOS dev)

File contents:

```bash
BWS_ACCESS_TOKEN="REDACTED"
```

Restart the gateway:

```bash
openclaw gateway restart
```

### 4) Use UUID-based references in the OpenClaw secret map

Replace `op://...` entries in `~/.openclaw/skill-secrets-map.json` with:

- `bws://project/<projectUuid>/secret/<secretUuid>`

How to obtain UUIDs:

```bash
bws secret list
bws secret list <PROJECT_ID>
bws secret get <SECRET_ID>
```

### 5) Run sync

```bash
python3 ~/.openclaw/bin/sync-skill-secrets.py
```

Inspect `~/.openclaw/generated/secret-sync-report.json` for unresolved entries.

### 6) ClawHub / marketplace options (inventory)

Run these on your machine to refresh results as the registry changes:

```bash
openclaw skills search bitwarden
openclaw skills search secret-manager
npx clawhub@latest search bitwarden
```

Example `openclaw skills search bitwarden` slugs include: `bitwarden-vault`, `openclaw-bitwarden`, `bitwarden-bw`, `twhidden-bitwarden`, `bitwarden-secrets`, `bitwarden-bwe`, `bitwarden-credential`, `headless-bitwarden`, `bitwarden-integration`, `bitwarden`. **`openclaw skills search bws`** may return no rows — BWS-specific community tooling is often **npm/GitHub** (`openclaw-skill-secret-manager-bws`) rather than a `bws` ClawHub slug.

**Snapshot (CLI, for orientation — not a guarantee ClawHub web search matches):**

| Source | Install / discover | Bitwarden surface | Automation posture |
|--------|--------------------|-------------------|--------------------|
| OpenClaw search `bitwarden*` | `openclaw skills install <slug>` (e.g. `twhidden-bitwarden`, `bitwarden-secrets`, `openclaw-bitwarden`) | Mostly **password vault** via `bw` / `rbw` | **Avoid** for unattended agents unless you accept vault unlock semantics |
| [jamaynor/openclaw-skill-secret-manager-bws](https://github.com/jamaynor/openclaw-skill-secret-manager-bws) | `npm install -g openclaw-skill-secret-manager-bws` (README also mentions `npx clawhub install secret-manager-bws`; confirm slug with `clawhub search`) | **Secrets Manager (BWS)** via bundled SDK | **Optional**: `secrets-bws` + `bws-mcp-wrapper` inject secrets into MCP child processes at startup |
| [Composio OpenClaw plugin](https://composio.dev/toolkits/bitwarden/framework/openclaw) | `openclaw plugins install @composio/openclaw-plugin` | Bitwarden via **Composio-hosted MCP** | Third-party trust boundary; skip if you standardize on **self-hosted `bws.env`** |
| This repo | `secrets-mcp` on Docker + [services/router/config/mcp_servers.yaml](../../../services/router/config/mcp_servers.yaml) | BWS via `bws` + `BWS_ACCESS_TOKEN` | For **Birtha router** / stack; HTTP API is `/tools` + `/call` (not OpenClaw’s MCP-over-SSE client without an adapter) |

**Recommended default for this repo:** keep **`sync-skill-secrets.py` + `bws://` map + `bws.env`** as the primary path. Add **community `openclaw-skill-secret-manager-bws`** only when you need **`bws-mcp-wrapper`** to start an MCP server with secrets in **env at process launch** (without putting them in `openclaw.json`).

### 7) `HAL_BWS_*` vs `BWS_ACCESS_TOKEN` (community BWS skills)

Some community packages expect **`HAL_BWS_ACCESS_TOKEN`** and **`HAL_BWS_ORGANIZATION_ID`**. This repo and `secrets-mcp` use **`BWS_ACCESS_TOKEN`** (and optionally add **`BWS_ORGANIZATION_ID`** to `bws.env`).

After sourcing `bws.env`, source the alias helper (copy into `~/.openclaw/bin/openclaw-gateway-wrapper.sh` if you use one):

```bash
# shellcheck source=scripts/source-bws-hal-aliases.sh
source /path/to/server/mbmh/deploy/openclaw/scripts/source-bws-hal-aliases.sh
```

Optional line in `bws.env`:

```bash
BWS_ORGANIZATION_ID="<your-organization-uuid>"
```

Audit any community skill (`SKILL.md`, npm package) before production use.

### 8) Limited agents (gateway + tool/skill allowlists)

Use OpenClaw config to cap blast radius; Bitwarden **machine accounts** still scope secrets per environment.

- **Gateway:** `gateway.bind: "loopback"` and `gateway.auth.mode: "token"` ([configuration](https://docs.openclaw.ai/gateway/configuration)).
- **Tools:** `tools.allow` whitelists tool bundles (see `openclaw config get tools`).
- **Bundled skills:** `skills.allowBundled` or per-skill `enabled: false` (see [Skills config](https://docs.openclaw.ai/tools/skills-config)).

Checked-in example fragment (merge into `openclaw.json`, then `openclaw config validate`): [openclaw-limited-agents-bitwarden.json5](./openclaw-limited-agents-bitwarden.json5).

**Bitwarden org practice:** separate **machine accounts** (and tokens) per tier (e.g. dev vs prod) with **minimal project** access — credentials stay independent of end-user identity.

### 9) Verification

1. `openclaw skills check` — only intended skills **Ready**.
2. `openclaw config validate` after merging the example fragment.
3. Gateway restart works **without** `bw unlock` / `op signin` when using BWS machine tokens only.

## Hydrating API-key skills (1Password + `sync-skill-secrets.py`)

Bundled skills such as **goplaces**, **notion**, **openai-whisper-api**, **sag**, and **trello** need env vars (and sometimes `skills.entries.*` in config). If you use the local sync pipeline, secrets come from **1Password** into `~/.openclaw/skills.env` and `~/.openclaw/secrets.json` (see `secrets.providers` in `openclaw.json`).

### 1. CLI session (interactive shells)

1. Use the same `op` config as the gateway: `export OP_CONFIG_DIR="$HOME/.config/op"` (already typical in `~/.zshrc` if you set it).
2. Sign in for **this terminal**: `eval "$(op signin)"` then `op whoami`.
3. Optional helper from this repo: [scripts/run-sync-skill-secrets.sh](scripts/run-sync-skill-secrets.sh) — runs the sync only if `op whoami` succeeds.

### 2. Map vault and items

Edit `~/.openclaw/skill-secrets-map.json`:

- Set `"vault"` to a vault name that exists in **`op vault list`** (for example `Personal`). If you use a dedicated vault, create it in 1Password and point all `op://…/` references at that vault name.
- For each skill, ensure a **Login** (or appropriate item) exists in that vault whose **item name** matches the map (e.g. `goplaces`, `notion`, `openai`, `sag`, `trello`), with fields the map expects (commonly `apiKey`, `token`, etc.). Field IDs must match what `op read op://Vault/item/field` resolves.

### 3. Run sync

```bash
eval "$(op signin)"
python3 ~/.openclaw/bin/sync-skill-secrets.py
# or from this repo: mbmh/deploy/openclaw/scripts/run-sync-skill-secrets.sh
```

### 3b. Non-interactive sync (no `op signin`) via 1Password Connect

If you have 1Password Connect running, you can sync without an interactive desktop/app session:

1. Create the centralized artifacts directory on the server host (outside git):

```bash
# Determine the host-specific data root (Linux server vs macOS dev).
SERVER_DATA_ROOT="$(/Users/maxholden/GitHub/server/scripts/server_data_root.sh)"

sudo mkdir -p "${SERVER_DATA_ROOT}/server/secrets/1password-connect"
sudo chmod 700 "${SERVER_DATA_ROOT}/server/secrets/1password-connect"
sudo chown root:root "${SERVER_DATA_ROOT}/server/secrets/1password-connect"
```

2. From 1Password (Secrets Automation), create/deploy a Connect server and download `1password-credentials.json`. Copy it to:
   - `${SERVER_DATA_ROOT}/server/secrets/1password-connect/1password-credentials.json`
   - permissions: `0600` (root-readable only)

3. Create a Connect server access token scoped to the vault(s) that hold your server logins/secrets. Create an env file:
   - `${SERVER_DATA_ROOT}/server/secrets/1password-connect/op-connect.env`

```bash
sudo tee "${SERVER_DATA_ROOT}/server/secrets/1password-connect/op-connect.env" >/dev/null <<'EOF'
# Used by docker-compose (mcp-secrets) and optionally OpenClaw host sync.
OP_CONNECT_TOKEN="REDACTED"
EOF
sudo chmod 600 "${SERVER_DATA_ROOT}/server/secrets/1password-connect/op-connect.env"
sudo chown root:root "${SERVER_DATA_ROOT}/server/secrets/1password-connect/op-connect.env"
```

4. On the OpenClaw host user, either:\n+   - create `~/.openclaw/op-connect.env` with `OP_CONNECT_TOKEN=...`, **or**\n+   - allow the gateway wrapper to source `/mnt/appdata/.../op-connect.env` (current wrapper supports this fallback).\n+\n+`OP_CONNECT_HOST` defaults to `http://127.0.0.1:18080` in the wrapper (loopback-only bind from `docker-compose.server.yml`).
2. Restart the gateway so the wrapper sources the env file:
   - `openclaw gateway restart`
3. Re-run sync:
   - `python3 ~/.openclaw/bin/sync-skill-secrets.py`

Inspect `~/.openclaw/generated/secret-sync-report.json` for any `unresolved` entries.

`OP_TIMEOUT_SECONDS` defaults to **30** in `~/.openclaw/bin/openclaw-gateway-wrapper.sh` before sync so `op read` is less likely to time out under launchd; override in the environment if needed.

### 4. Gateway and launchd

The gateway wrapper runs `sync-skill-secrets.py` then **sources** `~/.openclaw/skills.env`. It does **not** run `op signin`.

With this repo’s 1Password Connect integration, for unattended sync from launchd, put your Connect server access token into `~/.openclaw/op-connect.env` (outside git). The wrapper sources it on startup so `op read op://...` resolves non-interactively.

After changing secrets or the map:

```bash
openclaw gateway restart
```

### 5. Verify

```bash
openclaw skills info goplaces
openclaw skills info notion
openclaw skills info openai-whisper-api
openclaw skills info sag
openclaw skills info trello
openclaw skills check
```

## Self-hosted Whisper and local coding orchestration

### Transcription: local model vs “Whisper API” skill

| Approach | Skill | What it is |
|----------|--------|------------|
| **Local Whisper CLI** | `openai-whisper` | Runs the `whisper` binary (`brew install openai-whisper`). No API key, no cloud. Best match for “self-hosted model on this Mac.” |
| **HTTP client to OpenAI-style endpoint** | `openai-whisper-api` | The bundled script posts **multipart form data** to `{OPENAI_BASE_URL}/audio/transcriptions` with `Authorization: Bearer …`, same shape as OpenAI’s [audio transcriptions](https://platform.openai.com/docs/api-reference/audio/createTranscription) API. |

You **can** point `openai-whisper-api` at a **self-hosted server only if** that server implements a compatible **`POST …/audio/transcriptions`** (multipart `file`, `model`, etc.). Set:

- `OPENAI_BASE_URL` — e.g. `http://127.0.0.1:8080/v1` (must end up with `…/v1/audio/transcriptions` when combined; the script strips a trailing slash and appends `/audio/transcriptions`).
- `OPENAI_API_KEY` — the bundled script **exits if this is empty**, even for localhost. If your gateway ignores auth, use a **non-empty placeholder** (e.g. `local`) in `skills.env` or `skills.entries["openai-whisper-api"].env` so `openclaw skills check` and the script both pass.

**Not compatible out of the box:** this repo’s **wrkhrs ASR** service (`services/wrkhrs/services/asr`) exposes **`/transcribe`** / **`/transcribe/file`** with its **own** JSON/schema, not OpenAI’s multipart route. To use it from OpenClaw you’d add a **small proxy** (translate OpenAI-shaped requests to ASR routes), call ASR with **`exec` + `curl`** from a custom skill, or use an **MCP tool**—not the stock `transcribe.sh` without adaptation.

### Coding agent: bundled skill vs your stack

The bundled **`coding-agent`** skill is wired to **spawn real CLIs** named `claude`, `codex`, `opencode`, or `pi`. It does **not** read a “local orchestrator URL” from config.

Ways to involve **local orchestration** (e.g. this repo’s **agent-platform** in `services/agent-platform/server`, with `POST /v1/tasks/run` or `POST /v1/workflows/execute`):

1. **PATH wrapper (quickest hack)** — Put an executable **earlier on `PATH`** named `codex` (or another satisfied `anyBins` name) that is a shell script: validate args, then `curl`/`fetch` your HTTP API and stream or print the result. The skill stays “eligible” because the binary exists; behavior is yours.
2. **Skip the skill; use tools** — From the agent, use **bash/exec** with explicit `curl` to your gateway, or register an **MCP server** that wraps `tasks/run` / `workflows/execute`.
3. **Custom / ClawHub skill** — Copy the `coding-agent` playbook into a private skill whose `SKILL.md` documents **your** endpoints and payloads (recommended if wrappers feel brittle).

OpenClaw’s **MBMH** OpenAI-compatible server on `:8000` is a **model HTTP front-end**, not a drop-in replacement for the Codex/Claude **process** the `coding-agent` skill describes. Wiring “local orchestration” means either subprocess to a CLI you control or HTTP to a service you run (agent-platform, devplane, etc.).

### MartyMedia Whisper + agent-platform bridge (local-first)

This repo includes a working “attach” for MartyMedia’s conda-backed Whisper and a `codex` shim that forwards to the local agent-platform HTTP API.

#### 1) MartyMedia Whisper (conda) as OpenClaw `whisper`

- Launcher script: `MartyMedia-/bin/martymedia-whisper`
- Install for the gateway: symlink it as `~/.local/bin/whisper` (the gateway PATH includes `~/.local/bin` before Homebrew):

```bash
ln -sf /Users/maxholden/GitHub/server/MartyMedia-/bin/martymedia-whisper ~/.local/bin/whisper
openclaw gateway restart
openclaw skills info openai-whisper
```

Optional default model:

- Set `MARTYMEDIA_WHISPER_MODEL=large` (or `medium`, etc.) in the environment that runs `whisper`. If you pass `--model ...` explicitly, it wins.

#### 2) Local orchestration as `coding-agent` (agent-platform + `codex` shim)

1. Start MBMH (OpenAI-compatible runtime) on `:8000`:

```bash
cd /Users/maxholden/GitHub/server/mbmh
mkdir -p outputs
python scripts/serve_local.py --config configs/runtime/openai-compatible.yaml --bundle latest --agents-dir configs/agents --api-keys configs/auth/api_keys.yaml
```

2. Start agent-platform on `:8001` and point its OpenAI client at MBMH:

```bash
OPENAI_BASE_URL=http://127.0.0.1:8000/v1 \
OPENAI_API_KEY=sk-local-dev-001 \
AGENT_PLATFORM_PORT=8001 \
AGENT_PLATFORM_HOST=127.0.0.1 \
node /Users/maxholden/GitHub/server/services/agent-platform/server/dist/server.js
```

3. Install the `codex` shim (so OpenClaw’s `coding-agent` skill can invoke it):

```bash
ln -sf /Users/maxholden/GitHub/server/mbmh/deploy/openclaw/scripts/codex-agent-platform-bridge.sh ~/.local/bin/codex
openclaw gateway restart
openclaw skills info coding-agent
```

Defaults for the shim come from the gateway wrapper (`~/.openclaw/bin/openclaw-gateway-wrapper.sh`):

- `AGENT_PLATFORM_URL` (default `http://127.0.0.1:8001`)
- `OPENCLAW_ORCH_PROVIDER` (default `openai`)
- `OPENCLAW_ORCH_MODEL` (default `openclaw-agent`)

If you want per-run overrides, set env vars before invoking `codex exec ...`.

## Quick wins (common, low effort)

- **`session-logs` (`bins: rg`)** — install Ripgrep: `brew install ripgrep` (`rg` on PATH).
- **`tmux` (`bins: tmux`)** — `brew install tmux`.
- **`coding-agent` (`anyBins: claude, codex, opencode, pi`)** — install **one** CLI you already use (e.g. Codex or Claude Code).

## What the 42 typically need (reference)

From `openclaw skills check` (your machine may vary slightly):

- **macOS / Apple ecosystem CLIs:** `op`, `memo`, `remindctl`, `grizzly`, `things`, `peekaboo`, `sag`, etc. — install from each tool’s docs or brew taps; many are niche.
- **Third-party CLIs:** `gemini`, `himalaya`, `wacli`, `blogwatcher`, `clawhub`, `mcporter`, … — install only if you use that product.
- **API keys:** `NOTION_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_PLACES_API_KEY`, `TRELLO_*`, `ELEVENLABS_API_KEY`, Sherpa env dirs, etc. — add via env or `skills.entries.*.apiKey` / `env`.
- **Channels:** `channels.discord.token`, `channels.slack`, `channels.bluebubbles`, `plugins.entries.voice-call.enabled` — configure in `openclaw.json` when you use those features.

## Inspect one skill

```bash
openclaw skills info <skill-name>
```

## MBMH runtime

Your local **MBMH** `serve_local.py` setup is unrelated to skill gating. Skills are **OpenClaw gateway + host tools + secrets**, not the OpenAI-compatible server on `:8000`.
