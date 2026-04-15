#!/usr/bin/env bash
# Tear down managed OpenClaw gateway started by fullstack_e2e_bootstrap.sh; optionally docker compose down.
#
# For agents: reads PID from CACHE_ROOT/e2e-bootstrap/openclaw-gateway.pid (same layout as bootstrap).
# Env:
#   E2E_TEARDOWN_DOCKER=1 — run docker compose down with the same -f chain as make up (default off).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export E2E_REPO_ROOT="$ROOT"

# shellcheck source=scripts/workspace_env.sh
# shellcheck disable=SC1091
source "$ROOT/scripts/workspace_env.sh"

STATE_DIR="${CACHE_ROOT:-$ROOT/.cache}/e2e-bootstrap"
PID_FILE="$STATE_DIR/openclaw-gateway.pid"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" || true)"
  if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
    log "Stopping OpenClaw gateway PID ${pid}..."
    kill -TERM "$pid" 2>/dev/null || true
    for _ in $(seq 1 30); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 1
    done
    if kill -0 "$pid" 2>/dev/null; then
      log "Gateway still running; SIGKILL ${pid}"
      kill -KILL "$pid" 2>/dev/null || true
    fi
  else
    log "No live process for PID file ${PID_FILE} (stale or empty)."
  fi
  rm -f "$PID_FILE"
else
  log "No gateway PID file at ${PID_FILE} (nothing to stop)."
fi

if [[ "${E2E_TEARDOWN_DOCKER:-0}" == "1" ]]; then
  # shellcheck source=dev/scripts/lib/e2e_compose.sh
  source "$ROOT/dev/scripts/lib/e2e_compose.sh"
  log "docker compose down (E2E_TEARDOWN_DOCKER=1)"
  e2e_compose down --remove-orphans
fi

log "Teardown complete."
