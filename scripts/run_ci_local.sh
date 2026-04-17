#!/usr/bin/env bash
# Replicate infra checks from .github/workflows/ci.yml locally.
# Full AI matrix runs in https://github.com/XLOTYL/xlotyl (clone ../xlotyl and use its CI or scripts).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
XLOTYL_ROOT="${XLOTYL_ROOT:-$ROOT/../xlotyl}"
CI_COMPOSE="docker/compose-profiles/docker-compose.ci.yml"
XLOTYL_ENV="${ROOT}/config/xlotyl-images.env"

PYTHON="${PYTHON:-python3.11}"
# shellcheck source=/dev/null
source "$ROOT/scripts/workspace_env.sh"

echo "==> Using Python: $($PYTHON --version)"
echo "==> Workspace env: $ROOT/.venv"

uv sync --python "$PYTHON"

echo "==> Lint (MCP Python packages only)"
source scripts/ci_python_lint_paths.sh
uv run ruff check $CI_PYTHON_LINT_PATHS
uv run black --check $CI_PYTHON_LINT_PATHS

echo "==> Mypy (MCP servers)"
(cd mcp-servers/mcp/servers/filesystem-mcp && MYPY_CACHE_DIR="$MYPY_CACHE_ROOT/mcp-filesystem" uv run --package filesystem-mcp-server mypy --strict src)
(cd mcp-servers/mcp/servers/secrets-mcp && MYPY_CACHE_DIR="$MYPY_CACHE_ROOT/mcp-secrets" uv run --package secrets-mcp-server mypy --strict src)
(cd mcp-servers/mcp/servers/vector-db-mcp && MYPY_CACHE_DIR="$MYPY_CACHE_ROOT/mcp-vector-db" uv run --package vector-db-mcp-server mypy --strict src)

echo "==> Pytest (per package; live stack required — pulls ghcr.io/xlotyl/* from ${XLOTYL_ENV})"
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is required for this CI suite (live-stack tests are required)." >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker CLI is present but the daemon is not reachable (start Docker Desktop / dockerd)." >&2
  exit 1
fi

WAIT_HOST="${WAIT_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8080}"
MLFLOW_PORT="${MLFLOW_PORT:-15000}"
TEMPO_PORT="${TEMPO_PORT:-3200}"
MCP_REGISTRY_PORT="${MCP_REGISTRY_PORT:-8001}"
export WAIT_HOST API_PORT MLFLOW_PORT TEMPO_PORT MCP_REGISTRY_PORT

compose_ci() {
  docker compose --project-directory "$ROOT" --env-file "$XLOTYL_ENV" -f "$CI_COMPOSE" "$@"
}

compose_ci down -v >/dev/null 2>&1 || true
docker compose --project-directory "$ROOT" --env-file "$XLOTYL_ENV" pull -q api mcp-registry 2>/dev/null || true
compose_ci up -d
cleanup_ci_stack() {
  compose_ci down -v >/dev/null 2>&1 || true
}
trap cleanup_ci_stack EXIT

wait_http() {
  local name="$1"
  local url="$2"
  local max_attempts="${3:-90}"
  for _i in $(seq 1 "$max_attempts"); do
    if curl -fsS "$url" >/dev/null; then
      echo "OK: $name ($url)"
      return 0
    fi
    sleep 2
  done
  echo "FAIL: $name never became ready ($url)" >&2
  compose_ci ps
  compose_ci logs --no-color --tail=80 tempo || true
  return 1
}

wait_http api "http://${WAIT_HOST}:${API_PORT}/health" 90
wait_http mlflow "http://${WAIT_HOST}:${MLFLOW_PORT}/health" 90
wait_http tempo "http://${WAIT_HOST}:${TEMPO_PORT}/ready" 120
wait_http mcp-registry "http://${WAIT_HOST}:${MCP_REGISTRY_PORT}/health" 90

export API_BASE_URL="http://${WAIT_HOST}:${API_PORT}"
export MLFLOW_BASE_URL="http://${WAIT_HOST}:${MLFLOW_PORT}"
export TEMPO_BASE_URL="http://${WAIT_HOST}:${TEMPO_PORT}"
export MCP_REGISTRY_BASE_URL="http://${WAIT_HOST}:${MCP_REGISTRY_PORT}"
export RUN_LIVE_STACK_TESTS=1

pytest_pkg() {
  local dir="$1"
  local cache_name="$2"
  shift
  shift
  if [[ ! -d "$dir/tests" ]]; then
    echo "==> SKIP pytest: no $dir/tests"
    return 0
  fi
  mkdir -p "$PYTEST_CACHE_ROOT/$cache_name"
  (cd "$dir" && PYTHONPATH="$(pwd)" PYTEST_ADDOPTS="-o cache_dir=$PYTEST_CACHE_ROOT/$cache_name ${PYTEST_ADDOPTS:-}" uv run --extra dev pytest "$@")
}

pytest_pkg mcp-servers/mcp/servers/filesystem-mcp mcp-filesystem tests/ -v --cov=src --cov-report=xml
pytest_pkg mcp-servers/mcp/servers/secrets-mcp mcp-secrets tests/ -v
pytest_pkg mcp-servers/mcp/servers/vector-db-mcp mcp-vector-db tests/ -v --cov=src --cov-report=xml

echo "==> Node (github-mcp)"
if [[ -d "mcp-servers/mcp/servers/github-mcp" ]] && compgen -G "mcp-servers/mcp/servers/github-mcp/package*.json" > /dev/null; then
  if command -v npm >/dev/null 2>&1; then
    (cd mcp-servers/mcp/servers/github-mcp && npm ci && npm run build && npm test)
  else
    echo "SKIP: npm not found"
  fi
else
  echo "SKIP: github-mcp node project files missing (expected package*.json)"
fi

if [[ -d "$XLOTYL_ROOT/.git" ]]; then
  echo "==> Optional: run xlotyl lint/tests from $XLOTYL_ROOT (see XLOTYL repo CI for full matrix)"
else
  echo "==> No sibling xlotyl clone at $XLOTYL_ROOT — skipping AI repo checks."
fi

echo "==> CI local run finished OK"
