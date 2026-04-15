#!/usr/bin/env bash
# Bring up the Birtha + WrkHrs AI Docker stack used for OpenClaw↔Birtha e2e.
# Equivalent compose chain to `make up` from the repo root.
#
# For agents: waits on api-service /health; prints URLs and how to start OpenClaw
# on the host (OpenClaw is not a compose service in this repo).
# On Darwin arm64, e2e_mac_host_ollama.sh runs before compose so LLM_* env targets host Ollama.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export E2E_REPO_ROOT="$ROOT"
# shellcheck source=dev/scripts/lib/e2e_compose.sh
source "$ROOT/dev/scripts/lib/e2e_compose.sh"
# shellcheck source=dev/scripts/lib/e2e_mac_host_ollama.sh
source "$ROOT/dev/scripts/lib/e2e_mac_host_ollama.sh"
# shellcheck source=dev/scripts/lib/e2e_mac_host_memory_governor.sh
source "$ROOT/dev/scripts/lib/e2e_mac_host_memory_governor.sh"

# Preflight for Apple Silicon path: ollama + /api/tags (inside maybe_configure); needs curl on PATH.
require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: missing required command: $1" >&2
    exit 1
  }
}
require_cmd curl
e2e_mac_host_ollama_maybe_configure
e2e_mac_host_memory_governor_maybe_configure

echo "Starting Docker stack (first run may take many minutes to build images)..."
e2e_compose up -d --remove-orphans "$@"

API_PORT="${API_PORT:-8080}"
ROUTER_PORT="${ROUTER_PORT:-8000}"
AGENT_PLATFORM_PORT="${WRKHRS_AGENT_PLATFORM_PORT:-8087}"

echo ""
echo "Waiting for Birtha API http://127.0.0.1:${API_PORT}/health (up to ~4 minutes)..."
for i in $(seq 1 120); do
  if curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
    echo "API is healthy."
    break
  fi
  if [ "$i" -eq 120 ]; then
    echo "Timed out waiting for API health. Check logs: make logs (or docker compose --project-directory \"${ROOT}\" ... logs api)" >&2
    exit 1
  fi
  sleep 2
done

echo ""
echo "Docker stack is up. Key URLs:"
echo "  Birtha api-service:   http://127.0.0.1:${API_PORT}"
echo "  Router:               http://127.0.0.1:${ROUTER_PORT}"
echo "  Agent-platform:       http://127.0.0.1:${AGENT_PLATFORM_PORT}"
echo "  WrkHrs gateway:       http://127.0.0.1:${WRKHRS_GATEWAY_PORT:-8091}"
echo "  Model-runtime:        (internal wrkhrs network; api uses AGENT_PLATFORM_URL)"
echo ""
echo "Logs:  make logs"
echo ""
echo "OpenClaw (run on host — requires Node.js v22.12+):"
echo "  cd \"${ROOT}/openclaw\""
echo "  pnpm install"
echo "  export BIRTHA_API_BASE_URL=http://127.0.0.1:${API_PORT}"
echo "  # configure birtha-bridge in OpenClaw; then e.g.:"
echo "  node openclaw.mjs gateway run"
echo ""
echo "Full orchestration (Docker + checks + optional gateway): make fullstack-e2e"
echo ""
