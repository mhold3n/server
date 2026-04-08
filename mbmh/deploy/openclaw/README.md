# OpenClaw + MBMH local runtime

This repo exposes an **OpenAI Chat Completions** surface on the runtime server (`serve_local.py`). OpenClaw’s **Control UI does not talk to that URL directly** for chat: it uses the **Gateway WebSocket** (`chat.send`, `chat` events). To drive MBMH inference from OpenClaw, register this server as a **custom model provider** in `~/.openclaw/openclaw.json` and point your **agent’s primary model** at `provider/<model-id>`.

Official references:

- [Local models / OpenAI-compatible proxies](https://docs.openclaw.ai/gateway/local-models) — same pattern as `baseUrl: …/v1` + provider block.
- [Control UI](https://docs.openclaw.ai/web/control-ui) — WS on the Gateway port (default `18789`), not the runtime port (`8000`).
- [Gateway logging](https://docs.openclaw.ai/gateway/logging) — file logs, CLI tail, Control UI **Logs** tab.
- [OpenAI HTTP API on the Gateway](https://docs.openclaw.ai/gateway/openai-http-api) — **different** surface: that is OpenClaw serving `/v1/*` with `model: "openclaw/default"`, not your Python server.

## 1. Start the MBMH OpenAI-compatible server

From the `mbmh` directory (with the repo conda env `server` activated):

```bash
python scripts/serve_local.py --config configs/runtime/openai-compatible.yaml
```

Defaults: `http://127.0.0.1:8000`, agents from `configs/agents/`, keys from `configs/auth/api_keys.yaml`.

Smoke-test:

```bash
curl -sS http://127.0.0.1:8000/v1/models \
  -H "Authorization: Bearer sk-local-dev-001"
```

Use a **model id** returned there (YAML stem, e.g. `openclaw-agent`) as the OpenAI `model` field when calling this server; that is also the id you register under `models.providers.*.models[].id` in OpenClaw.

## 2. Obtain (1) provider config and (2) active model — reproducible methods

OpenClaw reads **`~/.openclaw/openclaw.json`** (or the path from `openclaw config file`). Below is how to **generate** the MBMH fragment and **inspect** what the Gateway actually uses.

### (1) Provider block: `models.providers`, `baseUrl`, `api`, `apiKey`

**Generate from this repo** (matches `configs/agents/*.yaml` and `configs/auth/api_keys.yaml`):

```bash
cd mbmh

# List model ids OpenClaw must register (same as GET /v1/models)
python scripts/emit_openclaw_provider_config.py --list-agent-ids

# With serve_local.py running: verify HTTP then print JSON
python scripts/emit_openclaw_provider_config.py --check

# Safer merge: only the models.* subtree (avoids clobbering unrelated agents.defaults)
python scripts/emit_openclaw_provider_config.py --models-only > mbmh-openclaw-models.json
```

Merge `mbmh-openclaw-models.json` into your OpenClaw config under the top-level `models` key (Control UI → Config → raw editor, or your editor), **or** paste the full output of the script without `--models-only` if you intend to set `agents.defaults.model.primary` in the same file.

**Read what OpenClaw already has** ([`openclaw config` CLI](https://docs.openclaw.ai/cli/config)):

```bash
openclaw config file
openclaw config get models.mode
openclaw config get models.providers
openclaw config validate
```

Confirm your MBMH provider includes **`"api": "openai-completions"`** and **`baseUrl`** ending in **`/v1`**.

### (2) Which model Chat uses: default + UI selection

**CLI:**

```bash
openclaw config get agents.defaults.model
openclaw models list
```

**Control UI:** In Chat, note the **model / agent** selector label (e.g. must resolve to `mbmh-local/openclaw-agent` if your provider slug is `mbmh-local`).

**Set only the default primary model** after merging `models.providers`. The value is always **`{providerKey}/{modelId}`** where **`providerKey` is the exact key** under `models.providers` in your JSON (OpenClaw does not use a fixed name like `mbmh-local`).

```bash
# Example if your provider key is mbmh-local (from emit script defaults):
openclaw config set agents.defaults.model.primary '"mbmh-local/openclaw-agent"' --strict-json

# Example if you created the provider in the UI as openclaw-agent:
openclaw config set agents.defaults.model.primary '"openclaw-agent/openclaw-agent"' --strict-json
```

If `primary` references a missing provider key, chat will fail silently or error in logs. Run `openclaw config get models.providers` and match the **top-level key** inside that object. Restart the Gateway after config changes.

**Shell tip:** Do not paste comment lines starting with `#` into zsh in one block; zsh may treat `#` oddly. Run commands one at a time, or use a here-doc / script file for copy-paste blocks.

## 3. Register MBMH as an OpenClaw provider (required)

OpenClaw must call **Chat Completions**, not the Responses API, for this runtime. Use:

- `baseUrl`: `http://127.0.0.1:8000/v1` (include `/v1`).
- `api`: **`"openai-completions"`** — not `"openai-responses"` (this server does not implement `/v1/responses`).
- `apiKey`: a bearer token OpenClaw will send as `Authorization: Bearer …`; must match a `key` in `configs/auth/api_keys.yaml` (e.g. `sk-local-dev-001`).

See the checked-in example: [`openclaw-mbmh-provider.json5`](./openclaw-mbmh-provider.json5).

Merge into your real config (or use `openclaw config set` / raw JSON editor in Control UI). Set the agent default model to your provider slug, e.g.:

```json5
{
  agents: {
    defaults: {
      model: { primary: "mbmh-local/openclaw-agent" },
    },
  },
}
```

Adjust `mbmh-local` and `openclaw-agent` to match the `providers` key and `models[].id` you define.

## 4. Gateway must be running for Control UI

```bash
openclaw gateway
```

Open the Control UI at `http://127.0.0.1:18789/` (or your configured port). Chat runs via Gateway RPC/events; MBMH is only used when the **configured model** resolves to this provider.

## 5. Events and log output (debugging)

| Surface | What it is |
|--------|------------|
| **Control UI → Logs** | Tails gateway file logs via `logs.tail`. |
| **CLI** | `openclaw logs --follow` |
| **Default log file** | `/tmp/openclaw/openclaw-YYYY-MM-DD.log` (JSON lines); tune `logging.level`, `logging.file` in config. |
| **Verbose console** | `openclaw gateway --verbose`; WebSocket traffic: `--ws-log compact` or `full`. |
| **Chat streaming in UI** | Documented as `chat.send` + streaming via **`chat` events** ([Control UI](https://docs.openclaw.ai/web/control-ui)). |

For **this** Python server, use terminal output / add app logging if you need request-level traces; OpenClaw’s logs show Gateway↔provider behavior once the provider is wired.

## 6. Common mistakes

- **Pointing only the Control UI “OpenAI base URL” at `:8000`** without a `models.providers` entry: the UI still chats through the Gateway; the LLM backend comes from **model routing**, not from pasting 8000 into the wrong field.
- **`api: "openai-responses"`** against MBMH: wrong adapter; use **`openai-completions`** ([config reference](https://docs.openclaw.ai/gateway/configuration-reference): `models.providers.*.api`).
- **Wrong OpenAI `model` id**: must match `/v1/models` from MBMH (e.g. `openclaw-agent`), not OpenClaw’s `openclaw/default` id (that is for OpenClaw’s **own** HTTP API, not this server).

### “low context window … ctx=16000 (warn if below 32000)”

OpenClaw reads **`contextWindow`** from **`models.providers.<slug>.models[]`** in `openclaw.json`. If it is below **32000**, the gateway logs a warning (`source=modelsConfig`). It does not read MBMH’s YAML; you must align the catalog with your real base model (e.g. Qwen2.5 is typically **32k** tokens).

**Fix:** set `contextWindow` to at least **32768** (and adjust `maxTokens` if you like), then restart the gateway. Example if your provider key is `openclaw-agent` and the model is the first row in that provider’s `models` array:

```bash
# Quote the path in zsh — unquoted [0] is treated as a glob.
openclaw config set 'models.providers.openclaw-agent.models[0].contextWindow' 32768 --strict-json
openclaw config set 'models.providers.openclaw-agent.models[0].maxTokens' 8192 --strict-json
```

Or re-merge output from `scripts/emit_openclaw_provider_config.py` (defaults use **32768**). Match the real model’s context from the model card if you use something other than Qwen2.5.

## 7. Bundled skills (“42 missing requirements”)

That message is from **`openclaw skills check`**: most bundled skills need extra CLIs or API keys. You do not have to enable all of them. See **[SKILLS-SETUP.md](./SKILLS-SETUP.md)** for strategies, **Bitwarden Secrets Manager** + ClawHub/marketplace notes, and **[openclaw-limited-agents-bitwarden.json5](./openclaw-limited-agents-bitwarden.json5)** for a gateway/tool allowlist example.

## 8. Adapter YAML in this folder

`adapters/test_adapter.yaml` is a placeholder bridge metadata file; live wiring is **OpenClaw `openclaw.json` + MBMH `serve_local.py`** as above.

## 9. Development-plane control API

OpenClaw can also act as the **operator shell** for the new development plane, using the control-plane API exposed by `services/api`:

- `POST /api/dev/projects` — register an external project checkout (must be outside the control-plane repo)
- `GET /api/dev/projects` — list registered projects
- `POST /api/dev/tasks` — submit a code task against a registered project
- `POST /api/dev/tasks/{task_id}/answer` — answer clarification questions
- `POST /api/dev/tasks/{task_id}/resume` — provision an isolated task worktree and dispatch an internal `agent-platform` run by default
- `GET /api/dev/runs/{run_id}` — inspect the current control-plane view of an internal or external run
- `POST /api/dev/runs/{run_id}/events` — legacy/manual callback surface for external operator sessions
- `POST /api/dev/runs/{run_id}/complete` — legacy/manual completion surface for external operator sessions
- `POST /api/dev/tasks/{task_id}/publish` — commit the task branch and optionally push / create a PR
- `GET /api/dev/tasks/{task_id}/dossier` — fetch the final branch/test/verification dossier

The intended flow is:

1. OpenClaw submits a task to the control plane.
2. The control plane either returns clarification questions or a ready task plan.
3. When resumed, the control plane provisions an isolated git worktree, writes `.birtha/task-packet.json`, and dispatches the internal `agent-platform` task-agent runtime.
4. The internal task-agent runtime performs implementation work inside the isolated workspace only, runs deterministic verification, and reports progress back into the dossier.
5. OpenClaw stays in the operator lane: it inspects task/run state, answers clarifications, reviews dossiers, inspects workspaces, retries runs, and publishes approved work.

This keeps OpenClaw as the primary internal interface while preserving a strict separation between:

- the **control plane** (this repository),
- the **development plane** (registered external project workspaces), and
- the **host system**.

## 10. Native OpenClaw operator plugin

A native OpenClaw plugin package now lives at [`birtha-devplane-plugin`](./birtha-devplane-plugin). It is intentionally a **thin control plugin**:

- manifest: `openclaw.plugin.json`
- runtime entry: `index.ts`
- operator skill root: `skills/`
- API client helpers and tests: `src/operator-client.js`, `tests/operator-client.test.mjs`

This plugin exposes operator-facing `devplane_*` tools for:

- listing and registering projects
- submitting tasks
- answering clarifications
- checking task and run state
- fetching dossiers
- inspecting the active workspace
- retrying or cancelling runs
- publishing approved task branches

It does **not** edit code itself. Code changes remain the responsibility of the internal Birtha task-agent runtime running under `services/agent-platform`.
