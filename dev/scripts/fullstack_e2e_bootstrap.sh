#!/usr/bin/env bash
# Fullstack E2E bootstrap: Docker (Birtha + WrkHrs AI compose), layered health waits,
# fast API smoke, optional pytest subset, OpenClaw host install, optional managed gateway, hooks.
#
# For agents: strict bash; idempotent-ish skips (node_modules, pnpm) unless --force-bootstrap.
# Compose argv matches Makefile FULL_DEV_COMPOSE via dev/scripts/lib/e2e_compose.sh.
#
# Env (documented for operators):
#   E2E_SKIP_DOCKER=1           — skip docker compose up (assume stack already running).
#   E2E_SKIP_NODE_BOOTSTRAP=1   — skip npm/pnpm/OpenClaw phases (Docker-only CI smoke).
#   E2E_UV_SYNC=1               — run `uv sync` at repo root (slow; off by default).
#   E2E_WAIT_GATEWAY=1         — wait on wrkhrs-gateway :8091/health (default off).
#   E2E_STRICT_ENGINEERING_SMOKE=1 — delegate to dev/scripts/smoke_strict_engineering_multimodal.sh.
#   E2E_SSE_SMOKE=1            — read first SSE line from POST /api/ai/query/stream.
#   E2E_PYTEST=1               — run curated api-service tests on host (default on).
#   E2E_MANAGED_OPENCLAW_GATEWAY=1 — start OpenClaw gateway in background if port free (default on).
#   E2E_OPENCLAW_CONFIG_PATCH=1 — merge birtha-bridge snippet into OPENCLAW_CONFIG_JSON (requires --i-accept-local-config-merge).
#   OPENCLAW_GATEWAY_PORT       — gateway listen port (default 18789).
#   OPENCLAW_CONFIG_JSON        — path to OpenClaw JSON config for optional jq merge.
#   API_PORT, WRKHRS_AGENT_PLATFORM_PORT, ROUTER_PORT, WRKHRS_GATEWAY_PORT — host ports for waits.
#   E2E_USE_HOST_OLLAMA=0      — on Darwin arm64 only: skip host Ollama preflight and LLM_* exports (default: enabled).
#   OLLAMA_HOST_PORT — host Ollama port (default 11434).
#   OLLAMA_MODEL               — Ollama tag for agent-platform / smoke (default qwen3:4b-instruct when Mac path active).
#   E2E_OLLAMA_SKIP_MODEL_CHECK=1 — skip verifying OLLAMA_MODEL is present in ollama /api/tags.
#   E2E_AUTO_START_OLLAMA=0 — on Darwin arm64: do not start `ollama serve` if the API is down (default: auto-start).
#   E2E_OLLAMA_START_WAIT — seconds to wait for Ollama after auto-start (default 90).
#   E2E_SMOKE_MODEL            — override model name in POST /api/ai/query smoke (defaults to OLLAMA_MODEL on Mac path).
#   E2E_ALLOW_GPU_WORKER_ON_DARWIN_ARM64=1 — allow docker-compose.worker.yml on Apple Silicon (see e2e_compose.sh).
#   E2E_SKIP_OPENCLAW_UI_BUILD=1 — skip pnpm ui:build before managed gateway (breaks Control /chat if dist missing).
#   E2E_OPENCLAW_USE_HOME_STATE=1 — on Darwin arm64 with host Ollama: do not use isolated OPENCLAW_STATE_DIR for the
#     managed gateway (default writes e2e-bootstrap/openclaw-managed-state so Control /chat targets host Ollama
#     instead of a broken ~/.openclaw agent model such as openclaw-agent/openclaw-agent).
#   E2E_OPENCLAW_GATEWAY_TOKEN — gateway shared token for isolated managed state / Control UI settings (default: openclaw-dev).
#     (If unset, E2E_OPENCLAW_GATEWAY_PASSWORD is still accepted as a legacy alias for the same value.)
#   Isolated openclaw.json (Darwin host Ollama, not E2E_OPENCLAW_USE_HOME_STATE): sets gateway.auth.rateLimit for local dev —
#     higher maxAttempts (50), 2m window, 30s lockout — so Control UI wrong-token retries lock out less aggressively than
#     OpenClaw defaults (browser path still rate-limited; restart gateway to clear in-memory counters).
#
# Args:
#   --force-bootstrap           — re-run npm install / pnpm install even if node_modules exist.
#   --i-accept-local-config-merge — required with E2E_OPENCLAW_CONFIG_PATCH=1 (writes local JSON).
#   --                          — remaining args forwarded to `docker compose up -d`.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export E2E_REPO_ROOT="$ROOT"

FORCE_BOOTSTRAP=0
ACCEPT_CONFIG_MERGE=0
COMPOSE_EXTRA=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force-bootstrap)
      FORCE_BOOTSTRAP=1
      shift
      ;;
    --i-accept-local-config-merge)
      ACCEPT_CONFIG_MERGE=1
      shift
      ;;
    --)
      shift
      COMPOSE_EXTRA=("$@")
      break
      ;;
    *)
      echo "Unknown argument: $1 (use -- before docker compose passthrough args)" >&2
      exit 2
      ;;
  esac
done

# shellcheck source=dev/scripts/lib/e2e_compose.sh
source "$ROOT/dev/scripts/lib/e2e_compose.sh"
# shellcheck source=scripts/workspace_env.sh
# shellcheck disable=SC1091
source "$ROOT/scripts/workspace_env.sh"

STATE_DIR="${CACHE_ROOT:-$ROOT/.cache}/e2e-bootstrap"
mkdir -p "$STATE_DIR"
LOG_GATEWAY="$STATE_DIR/openclaw-gateway.log"
PID_GATEWAY="$STATE_DIR/openclaw-gateway.pid"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { log "ERROR: $*"; exit 1; }

# shellcheck source=dev/scripts/lib/e2e_mac_host_ollama.sh
source "$ROOT/dev/scripts/lib/e2e_mac_host_ollama.sh"
source "$ROOT/dev/scripts/lib/e2e_mac_host_memory_governor.sh"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

# For agents: run pnpm for OpenClaw; conda/Homebrew Node often has no global pnpm. Order: PATH pnpm →
# corepack → npx-downloaded pnpm (no permanent install).
_PNPM_COREPACK_TRIED=0
pnpm_run() {
  if command -v pnpm >/dev/null 2>&1; then
    pnpm "$@"
    return
  fi
  if [[ "$_PNPM_COREPACK_TRIED" -eq 0 ]] && command -v corepack >/dev/null 2>&1; then
    _PNPM_COREPACK_TRIED=1
    log "pnpm not on PATH; trying corepack enable && corepack prepare pnpm@latest --activate"
    if corepack enable && corepack prepare pnpm@latest --activate && command -v pnpm >/dev/null 2>&1; then
      pnpm "$@"
      return
    fi
    log "corepack did not yield a usable pnpm; falling back to npx"
  fi
  require_cmd npx
  log "running: npx --yes pnpm@10 $*"
  npx --yes pnpm@10 "$@"
}

wait_http() {
  # wait_http URL NAME MAX_ATTEMPTS SLEEP_SEC
  local url="$1" name="$2" max="${3:-90}" sleep_s="${4:-2}"
  local i
  log "Waiting for ${name} (${url}) up to $((max * sleep_s))s..."
  for ((i = 1; i <= max; i++)); do
    if curl -sf "$url" >/dev/null 2>&1; then
      log "${name} is healthy."
      return 0
    fi
    if [[ "$i" -eq "$max" ]]; then
      die "${name} not ready after ${max} attempts (${url}). Hint: make logs | docker compose --project-directory \"${ROOT}\" ... logs <service>"
    fi
    sleep "$sleep_s"
  done
}

port_open() {
  local host="${1:-127.0.0.1}" port="$2"
  if command -v nc >/dev/null 2>&1; then
    nc -z "$host" "$port" >/dev/null 2>&1
    return $?
  fi
  (echo >/dev/tcp/"$host"/"$port") >/dev/null 2>&1
}

# --- Preflight ---
log "Phase: preflight (tools)"
require_cmd docker
docker info >/dev/null 2>&1 || die "docker daemon not reachable"
require_cmd curl
require_cmd python3

e2e_mac_host_ollama_maybe_configure
e2e_mac_host_memory_governor_maybe_configure

API_PORT="${API_PORT:-8080}"
ROUTER_PORT="${ROUTER_PORT:-8000}"
AGENT_PLATFORM_PORT="${WRKHRS_AGENT_PLATFORM_PORT:-8087}"
GATEWAY_PORT="${WRKHRS_GATEWAY_PORT:-8091}"
OPENCLAW_GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
API_BASE="http://127.0.0.1:${API_PORT}"

if [[ "${E2E_SKIP_NODE_BOOTSTRAP:-0}" != "1" ]]; then
  require_cmd node
  require_cmd npx
  node -e '
    const v = process.versions.node.split(".").map(Number);
    const ok = v[0] > 22 || (v[0] === 22 && v[1] >= 12);
    if (!ok) { console.error("Node.js v22.12+ required for OpenClaw; got " + process.versions.node); process.exit(1); }
  ' || die "Node.js v22.12+ required (see openclaw/openclaw.mjs)"
fi

# --- Workspace bootstrap ---
log "Phase: workspace bootstrap (CACHE_ROOT=${CACHE_ROOT:-})"
if [[ "${E2E_UV_SYNC:-0}" == "1" ]]; then
  log "Running uv sync (E2E_UV_SYNC=1)..."
  uv sync --python 3.11
fi

if [[ -f "$ROOT/package.json" ]] && [[ "${E2E_SKIP_NODE_BOOTSTRAP:-0}" != "1" ]]; then
  if [[ "$FORCE_BOOTSTRAP" -eq 1 ]] || [[ ! -d "$ROOT/node_modules" ]]; then
    log "npm install at repo root..."
    npm install
  else
    log "Skipping npm install (node_modules present; use --force-bootstrap to reinstall)."
  fi
fi

# --- Docker ---
if [[ "${E2E_SKIP_DOCKER:-0}" != "1" ]]; then
  log "Phase: docker compose up -d"
  # With `set -u`, an empty COMPOSE_EXTRA is still "unset" for [@] on older bash — use ${arr[@]+…}.
  e2e_compose up -d --remove-orphans ${COMPOSE_EXTRA[@]+"${COMPOSE_EXTRA[@]}"}
else
  log "Skipping docker compose (E2E_SKIP_DOCKER=1)."
fi

# --- Layered health waits ---
log "Phase: layered health waits"
wait_http "${API_BASE}/health" "Birtha api-service" 120 2
wait_http "http://127.0.0.1:${AGENT_PLATFORM_PORT}/health" "wrkhrs-agent-platform" 90 2
wait_http "http://127.0.0.1:${ROUTER_PORT}/health" "router" 90 2

if [[ "${E2E_WAIT_GATEWAY:-0}" == "1" ]]; then
  wait_http "http://127.0.0.1:${GATEWAY_PORT}/health" "wrkhrs-gateway" 90 2
fi

# --- Fast API smoke ---
log "Phase: interconnectivity smoke (POST /api/ai/query)"
if [[ "${E2E_MAC_HOST_OLLAMA_ACTIVE:-0}" == "1" ]]; then
  _E2E_SMOKE_MODEL="${E2E_SMOKE_MODEL:-$OLLAMA_MODEL}"
  QUERY_SMOKE_BODY="$(
    SMOKE_MODEL="$_E2E_SMOKE_MODEL" python3 -c \
      'import json,os; print(json.dumps({"prompt":"e2e bootstrap ping","model":os.environ["SMOKE_MODEL"],"provider":"local_worker"}))'
  )"
else
  QUERY_SMOKE_BODY='{"prompt":"e2e bootstrap ping","model":"gpt-4o-mini"}'
fi
RESP="$(curl -sS -w "\n%{http_code}" -X POST "${API_BASE}/api/ai/query" \
  -H "Content-Type: application/json" \
  -d "$QUERY_SMOKE_BODY" || true)"
HTTP_CODE="$(printf '%s\n' "$RESP" | tail -n 1)"
HTTP_BODY="$(printf '%s\n' "$RESP" | sed '$d')"
[[ "$HTTP_CODE" == "200" ]] || die "POST ${API_BASE}/api/ai/query expected HTTP 200, got ${HTTP_CODE}. Body (truncated): ${HTTP_BODY:0:400}"
python3 -c "import json,sys; json.loads(sys.argv[1])" "$HTTP_BODY" >/dev/null 2>&1 || die "POST /api/ai/query returned non-JSON (truncated): ${HTTP_BODY:0:400}"

if [[ "${E2E_STRICT_ENGINEERING_SMOKE:-0}" == "1" ]]; then
  log "Phase: strict engineering smoke (opt-in)"
  RUN_STRICT_ENGINEERING_SMOKE=1 API_BASE_URL="$API_BASE" bash "$ROOT/dev/scripts/smoke_strict_engineering_multimodal.sh"
fi

if [[ "${E2E_SSE_SMOKE:-0}" == "1" ]]; then
  log "Phase: SSE smoke (first data line)"
  # Read a bounded prefix of the stream; first data: line is enough.
  if [[ "${E2E_MAC_HOST_OLLAMA_ACTIVE:-0}" == "1" ]]; then
    _E2E_SSE_MODEL="${E2E_SMOKE_MODEL:-$OLLAMA_MODEL}"
    SSE_SMOKE_BODY="$(
      SMOKE_MODEL="$_E2E_SSE_MODEL" python3 -c \
        'import json,os; print(json.dumps({"prompt":"e2e sse ping","model":os.environ["SMOKE_MODEL"],"provider":"local_worker"}))'
    )"
  else
    SSE_SMOKE_BODY='{"prompt":"e2e sse ping","model":"gpt-4o-mini"}'
  fi
  SSE_HEAD="$(curl -sS -N -m 25 -X POST "${API_BASE}/api/ai/query/stream" \
    -H "Content-Type: application/json" \
    -H "Accept: text/event-stream" \
    -d "$SSE_SMOKE_BODY" | head -n 20 || true)"
  printf '%s\n' "$SSE_HEAD" | grep -q '^data:' || die "SSE smoke: no data: line in first 20 lines. Output (truncated): ${SSE_HEAD:0:500}"
fi

# --- Pytest subset (host) ---
if [[ "${E2E_PYTEST:-1}" == "1" ]]; then
  log "Phase: curated pytest (xlotyl/services/api-service)"
  PY_TESTS=(
    tests/test_openclaw_bridge.py
    tests/test_openclaw_stream_adapter.py
    tests/test_openclaw_query_stream_route.py
    tests/test_workflow_cancel_ack.py
  )
  (
    cd "$ROOT/xlotyl/services/api-service"
    if command -v uv >/dev/null 2>&1; then
      uv run python -m pytest "${PY_TESTS[@]}" -q
    else
      python3 -m pytest "${PY_TESTS[@]}" -q
    fi
  ) || die "pytest subset failed. Install deps (e.g. E2E_UV_SYNC=1 and uv sync) or run tests inside the api container."
fi

# --- OpenClaw install (host) ---
export BIRTHA_API_BASE_URL="$API_BASE"
log "Exported BIRTHA_API_BASE_URL=${BIRTHA_API_BASE_URL}"

if [[ "${E2E_SKIP_NODE_BOOTSTRAP:-0}" != "1" ]]; then
  log "Phase: OpenClaw pnpm install"
  if [[ "$FORCE_BOOTSTRAP" -eq 1 ]] || [[ ! -d "$ROOT/openclaw/node_modules" ]]; then
    (cd "$ROOT/openclaw" && pnpm_run install)
  else
    log "Skipping pnpm install (openclaw/node_modules present; use --force-bootstrap to reinstall)."
  fi
  if [[ ! -f "$ROOT/openclaw/dist/entry.mjs" && ! -f "$ROOT/openclaw/dist/entry.js" ]]; then
    log "OpenClaw dist missing; running pnpm build (first time can take several minutes)..."
    (cd "$ROOT/openclaw" && pnpm_run build)
  fi
fi

# --- Optional dangerous config merge ---
if [[ "${E2E_OPENCLAW_CONFIG_PATCH:-0}" == "1" ]]; then
  if [[ "$ACCEPT_CONFIG_MERGE" -ne 1 ]]; then
    die "E2E_OPENCLAW_CONFIG_PATCH=1 requires --i-accept-local-config-merge (refuses accidental local writes)."
  fi
  CFG="${OPENCLAW_CONFIG_JSON:-}"
  [[ -n "$CFG" ]] || die "E2E_OPENCLAW_CONFIG_PATCH=1 requires OPENCLAW_CONFIG_JSON to an existing JSON file path."
  [[ -f "$CFG" ]] || die "OPENCLAW_CONFIG_JSON not a file: $CFG"
  command -v jq >/dev/null 2>&1 || die "jq required for E2E_OPENCLAW_CONFIG_PATCH"
  TMP="${CFG}.e2e-bootstrap.$$"
  jq --arg url "$API_BASE" '
    .plugins = (.plugins // {}) |
    .plugins["birtha-bridge"] = ((.plugins["birtha-bridge"] // {}) | . + {"birthaApiBaseUrl": $url})
  ' "$CFG" >"$TMP"
  mv "$TMP" "$CFG"
  log "Merged birthaApiBaseUrl into plugins[\"birtha-bridge\"] in $CFG"
fi

# --- OpenClaw Control UI assets ---
# Gateway may try to auto-build the Control UI on first boot, but that spawn often lacks `pnpm` on PATH
# (openclaw-gateway.log: "Control UI build failed: Missing UI runner"). Prebuild with pnpm_run so /chat loads.
if [[ "${E2E_SKIP_NODE_BOOTSTRAP:-0}" != "1" ]] && [[ "${E2E_MANAGED_OPENCLAW_GATEWAY:-1}" == "1" ]] &&
  [[ "${E2E_SKIP_OPENCLAW_UI_BUILD:-0}" != "1" ]]; then
  OPENCLAW_CONTROL_UI_INDEX="$ROOT/openclaw/dist/control-ui/index.html"
  if [[ "$FORCE_BOOTSTRAP" -eq 1 ]] || [[ ! -f "$OPENCLAW_CONTROL_UI_INDEX" ]]; then
    log "Phase: OpenClaw Control UI (pnpm ui:build — required for Control /chat)"
    (cd "$ROOT/openclaw" && pnpm_run ui:build) || die "openclaw pnpm ui:build failed. Install pnpm (or corepack) so assets exist under openclaw/dist/control-ui/."
  else
    log "Skipping OpenClaw ui:build (${OPENCLAW_CONTROL_UI_INDEX} present; use --force-bootstrap to rebuild)."
  fi
fi

# --- Managed OpenClaw gateway ---
if [[ "${E2E_SKIP_NODE_BOOTSTRAP:-0}" != "1" ]]; then
  if [[ "${E2E_MANAGED_OPENCLAW_GATEWAY:-1}" == "1" ]]; then
    if port_open 127.0.0.1 "$OPENCLAW_GATEWAY_PORT"; then
      log "OpenClaw gateway port ${OPENCLAW_GATEWAY_PORT} in use — stopping prior listener so managed gateway can restart."
      [[ -f "$PID_GATEWAY" ]] && { kill -TERM "$(cat "$PID_GATEWAY" 2>/dev/null)" 2>/dev/null || true; rm -f "$PID_GATEWAY"; }
      for _ in $(seq 1 15); do port_open 127.0.0.1 "$OPENCLAW_GATEWAY_PORT" || break; sleep 1; done
      if port_open 127.0.0.1 "$OPENCLAW_GATEWAY_PORT" && command -v lsof >/dev/null 2>&1; then
        lsof -ti ":${OPENCLAW_GATEWAY_PORT}" | xargs kill -TERM 2>/dev/null || true
        sleep 2
      fi
      port_open 127.0.0.1 "$OPENCLAW_GATEWAY_PORT" && die "Could not free OpenClaw gateway port ${OPENCLAW_GATEWAY_PORT} (stop the other process or pick OPENCLAW_GATEWAY_PORT)."
    fi
    log "Starting managed OpenClaw gateway on port ${OPENCLAW_GATEWAY_PORT} (logs: ${LOG_GATEWAY})"
    : >"$LOG_GATEWAY"
    # When host Ollama is active, the managed gateway must not inherit ~/.openclaw if it pins a non-working embedded
    # model (Control /chat then shows no assistant text while logs show embedded_run_agent_end 422/500). Use a
    # dedicated OPENCLAW_STATE_DIR with gateway.mode=local (required or gateway run exits) and ollama/<OLLAMA_MODEL>.
    E2E_OC_STATE_DIR="${STATE_DIR}/openclaw-managed-state"
    # Prefix words for `gateway run` (empty unless we inject OPENCLAW_STATE_DIR for isolated config).
    OPENCLAW_GATEWAY_PREFIX=()
    # Set when isolated managed-state JSON is written; used for post-start Control UI connection hints.
    E2E_OC_ISOLATED_GATEWAY=0
    E2E_OC_GATEWAY_TOKEN_EFFECTIVE=""
    if [[ "${E2E_MAC_HOST_OLLAMA_ACTIVE:-0}" == "1" && "${E2E_OPENCLAW_USE_HOME_STATE:-0}" != "1" ]]; then
      mkdir -p "$E2E_OC_STATE_DIR"
      E2E_OC_JSON="${E2E_OC_STATE_DIR}/openclaw.json"
      OC_MODEL="${OLLAMA_MODEL:-qwen3:4b-instruct}"
      OC_PORT="${OLLAMA_HOST_PORT:-11434}"
      # Token auth: Control UI settings expect gateway.auth.token (see openclaw/ui i18n "paste token").
      E2E_OC_GATEWAY_TOKEN="${E2E_OPENCLAW_GATEWAY_TOKEN:-${E2E_OPENCLAW_GATEWAY_PASSWORD:-openclaw-dev}}"
      E2E_OC_ISOLATED_GATEWAY=1
      E2E_OC_GATEWAY_TOKEN_EFFECTIVE="$E2E_OC_GATEWAY_TOKEN"
      E2E_OC_STATE_DIR="$E2E_OC_STATE_DIR" OC_MODEL="$OC_MODEL" E2E_OC_GATEWAY_TOKEN="$E2E_OC_GATEWAY_TOKEN" python3 <<'PY'
import json
import os
from pathlib import Path

# Agents: minimal OpenClaw JSON so Control webchat uses host Ollama (ollama/<tag>).
# Do not set models.providers.ollama with only baseUrl — schema requires providers.*.models as an array
# (see openclaw/src/config/types.models.ts ModelProviderConfig). Omit models.*; extension defaults to 127.0.0.1:11434.
# Gateway: explicit token mode so Control UI "Gateway Token" matches server (password-only confused token-first UX).
# rateLimit: dev-friendly; browser WS still uses a non-exempt limiter in openclaw server.impl.ts — these numbers still apply.
state = os.environ["E2E_OC_STATE_DIR"]
model = os.environ["OC_MODEL"]
token = os.environ["E2E_OC_GATEWAY_TOKEN"]
cfg = {
    "gateway": {
        "mode": "local",
        "auth": {
            "mode": "token",
            "token": token,
            "rateLimit": {
                "maxAttempts": 50,
                "windowMs": 120000,
                "lockoutMs": 30000,
            },
        },
    },
    "agents": {
        "defaults": {
            "model": {"primary": f"ollama/{model}"},
            # Ollama can have long first-token latency (model load / cold start).
            # Avoid aborting the run just because no streaming token arrived within the default window.
            "llm": {"idleTimeoutSeconds": 600},
        }
    },
}
path = Path(state) / "openclaw.json"
path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

# The managed gateway uses an isolated state dir, so it won't inherit ~/.openclaw auth profiles.
# Ollama typically does not require an API key, but OpenClaw's auth resolver still expects a
# provider profile entry. Write a harmless placeholder so Control /chat works out of the box.
agent_dir = Path(state) / "agents" / "main" / "agent"
agent_dir.mkdir(parents=True, exist_ok=True)
auth_store = agent_dir / "auth-profiles.json"
if not auth_store.exists():
    auth_store.write_text(
        json.dumps(
            {
                "version": 1,
                "profiles": {
                    "ollama:local": {
                        "type": "api_key",
                        "provider": "ollama",
                        "key": "ollama",
                        "displayName": "Local Ollama (no-auth placeholder)",
                    }
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
PY
      OPENCLAW_GATEWAY_PREFIX=(env "OPENCLAW_STATE_DIR=${E2E_OC_STATE_DIR}")
      log "OpenClaw managed gateway: OPENCLAW_STATE_DIR=${E2E_OC_STATE_DIR} (agent model ollama/${OC_MODEL}; Ollama default http://127.0.0.1:${OC_PORT}; gateway auth=token — paste E2E_OPENCLAW_GATEWAY_TOKEN or default openclaw-dev in Control UI settings). Use E2E_OPENCLAW_USE_HOME_STATE=1 to keep ~/.openclaw."
    elif [[ "${E2E_MAC_HOST_OLLAMA_ACTIVE:-0}" == "1" && "${E2E_OPENCLAW_USE_HOME_STATE:-0}" == "1" ]]; then
      log "E2E_OPENCLAW_USE_HOME_STATE=1 — managed gateway uses your default OpenClaw state dir (ensure agent model reaches a working provider for Control /chat)."
    fi
    cd "$ROOT/openclaw"
    "${OPENCLAW_GATEWAY_PREFIX[@]}" nohup node openclaw.mjs gateway run --port "$OPENCLAW_GATEWAY_PORT" >>"$LOG_GATEWAY" 2>&1 &
    echo $! >"$PID_GATEWAY"
    cd "$ROOT"
    sleep 2
    if [[ -f "$PID_GATEWAY" ]]; then
      GPID="$(cat "$PID_GATEWAY")"
      if kill -0 "$GPID" 2>/dev/null; then
        log "OpenClaw gateway PID ${GPID} running."
        _oc_listen=0
        for _ in $(seq 1 25); do
          if ! kill -0 "$GPID" 2>/dev/null; then
            die "OpenClaw gateway process ${GPID} exited during startup. Tail log: tail -n 80 \"${LOG_GATEWAY}\""
          fi
          if port_open 127.0.0.1 "$OPENCLAW_GATEWAY_PORT"; then
            _oc_listen=1
            break
          fi
          sleep 1
        done
        [[ "$_oc_listen" -eq 1 ]] ||
          die "OpenClaw gateway never accepted TCP on 127.0.0.1:${OPENCLAW_GATEWAY_PORT} (process still alive?). Tail log: tail -n 80 \"${LOG_GATEWAY}\""
        log "UI hint: Cursor's embedded Browser tab cannot reach host localhost — open http://127.0.0.1:${OPENCLAW_GATEWAY_PORT}/chat (and http://127.0.0.1:${OLLAMA_HOST_PORT:-11434}/ for Ollama) in Safari/Chrome on this Mac."
        if [[ "${E2E_OC_ISOLATED_GATEWAY:-0}" == "1" ]]; then
          log "OpenClaw Control (isolated state) — use a browser on THIS Mac (not Cursor’s embedded tab); credentials:"
          if [[ "${E2E_OC_GATEWAY_TOKEN_EFFECTIVE:-}" == "openclaw-dev" ]]; then
            log "  One-shot login URL (token in URL fragment): http://127.0.0.1:${OPENCLAW_GATEWAY_PORT}/#token=openclaw-dev"
            log "  Gateway token (if connecting manually): openclaw-dev"
          else
            log "  Gateway token: (custom — not printed; set E2E_OPENCLAW_GATEWAY_TOKEN in this shell)"
            log "  Build a login URL: run from repo: env OPENCLAW_STATE_DIR=\"${E2E_OC_STATE_DIR}\" bash -lc 'cd \"${ROOT}/openclaw\" && node openclaw.mjs dashboard --no-open'"
          fi
          log "  WebSocket URL (manual connect form): ws://127.0.0.1:${OPENCLAW_GATEWAY_PORT}"
          log "  Dashboard base: http://127.0.0.1:${OPENCLAW_GATEWAY_PORT}/"
          log "If you see \"too many failed authentication attempts\", restart the managed gateway (e.g. make fullstack-e2e-down then make fullstack-e2e) to clear in-memory rate limits."
        fi
      else
        die "OpenClaw gateway exited immediately. Tail log: tail -n 80 \"${LOG_GATEWAY}\""
      fi
    fi
  else
    log "E2E_MANAGED_OPENCLAW_GATEWAY=0 — start manually, e.g.:"
    log "  cd \"${ROOT}/openclaw\" && node openclaw.mjs gateway run --port ${OPENCLAW_GATEWAY_PORT}"
    if [[ "${E2E_MAC_HOST_OLLAMA_ACTIVE:-0}" == "1" ]]; then
      log "  (Darwin host Ollama: if Control /chat is silent, run the managed-gateway block in dev/scripts/fullstack_e2e_bootstrap.sh or set agents.defaults.model to ollama/\${OLLAMA_MODEL} in your OpenClaw config.)"
    fi
  fi
fi

# --- birtha-bridge config snippet (OpenClaw workspace is user-local) ---
log "OpenClaw birtha-bridge plugin config snippet (merge into your workspace plugin config):"
cat <<EOF
{
  "birthaApiBaseUrl": "${API_BASE}",
  "birthaApiBearerToken": "<optional>"
}
EOF

# --- Optional post-up hook (IDE / future surfaces) ---
HOOK="$ROOT/dev/scripts/e2e_hooks/post_up.sh"
if [[ -f "$HOOK" ]]; then
  log "Sourcing optional hook: ${HOOK}"
  # shellcheck disable=SC1090
  source "$HOOK" || log "Hook returned non-zero (ignored)."
fi

log "Fullstack E2E bootstrap complete."
log "Teardown: make fullstack-e2e-down (set E2E_TEARDOWN_DOCKER=1 to also compose down)"
