#!/usr/bin/env bash
# Bundle a minimal, shareable debugging snapshot for orchestration issues.
# Produces a timestamped folder with:
# - curl snapshots: agent-platform (/health, /llm/info) and gateway (/health)
# - docker compose logs for key services
# - a short environment capture (sanitized)
#
# Usage:
#   bash dev/scripts/bundle_orchestration_logs.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${OUT_DIR:-${ROOT}/.cache/orchestration-bundles/${STAMP}}"
mkdir -p "$OUT_DIR"

AP_PORT="${WRKHRS_AGENT_PLATFORM_PORT:-8087}"
GW_PORT="${WRKHRS_GATEWAY_PORT:-8091}"
AP_BASE="${AGENT_PLATFORM_BASE_URL:-http://127.0.0.1:${AP_PORT}}"
GW_BASE="${GATEWAY_BASE_URL:-http://127.0.0.1:${GW_PORT}}"

echo "Writing bundle to: ${OUT_DIR}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing $1" >&2; exit 1; }; }
need curl

{
  echo "timestamp_utc=${STAMP}"
  echo "agent_platform_base=${AP_BASE}"
  echo "gateway_base=${GW_BASE}"
  echo "pwd=$(pwd)"
} >"${OUT_DIR}/meta.txt"

# Basic HTTP snapshots (best-effort)
curl -sS -D - "${AP_BASE}/health" -o "${OUT_DIR}/agent-platform.health.body" \
  >"${OUT_DIR}/agent-platform.health.headers" || true
curl -sS -D - "${AP_BASE}/llm/info" -o "${OUT_DIR}/agent-platform.llm-info.body" \
  >"${OUT_DIR}/agent-platform.llm-info.headers" || true
curl -sS -D - "${GW_BASE}/health" -o "${OUT_DIR}/gateway.health.body" \
  >"${OUT_DIR}/gateway.health.headers" || true

# Compose logs (best-effort; do not fail bundle creation on log errors)
DOCKER_COMPOSE="docker compose --project-directory ${ROOT}"
COMPOSE_FILES=(-f docker-compose.yml -f docker/compose-profiles/docker-compose.platform.yml -f docker/compose-profiles/docker-compose.ai.yml -f docker/compose-profiles/docker-compose.local-ai.yml)

${DOCKER_COMPOSE} "${COMPOSE_FILES[@]}" ps >"${OUT_DIR}/compose.ps.txt" 2>&1 || true
${DOCKER_COMPOSE} "${COMPOSE_FILES[@]}" logs --no-color --timestamps --tail 200 wrkhrs-agent-platform >"${OUT_DIR}/logs.wrkhrs-agent-platform.txt" 2>&1 || true
${DOCKER_COMPOSE} "${COMPOSE_FILES[@]}" logs --no-color --timestamps --tail 200 wrkhrs-gateway >"${OUT_DIR}/logs.wrkhrs-gateway.txt" 2>&1 || true
${DOCKER_COMPOSE} "${COMPOSE_FILES[@]}" logs --no-color --timestamps --tail 200 api >"${OUT_DIR}/logs.api.txt" 2>&1 || true

# Sanitize and capture a small env subset that commonly drives routing.
{
  for k in \
    LLM_BACKEND LLM_RUNNER_URL OPENAI_BASE_URL OPENAI_API_KEY OLLAMA_MODEL VLLM_MODEL \
    ORCHESTRATOR_URL AGENT_PLATFORM_URL WRKHRS_AGENT_PLATFORM_PORT WRKHRS_GATEWAY_PORT; do
    v="${!k-}"
    case "$k" in
      *KEY*|*TOKEN*|*PASSWORD*) v="<redacted>" ;;
    esac
    echo "${k}=${v}"
  done
} >"${OUT_DIR}/env.selected.txt"

echo "Bundle complete."
echo "Path: ${OUT_DIR}"

