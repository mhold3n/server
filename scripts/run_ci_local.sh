#!/usr/bin/env bash
# Replicate .github/workflows/ci.yml build-test job locally (no act/Docker required for Python parts).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3.11}"
VENV="${VENV:-$ROOT/.ci-local-venv}"

echo "==> Using Python: $($PYTHON --version)"
echo "==> Venv: $VENV"

if [[ ! -x "$VENV/bin/pip" ]]; then
  "$PYTHON" -m venv "$VENV"
fi
# shellcheck source=/dev/null
source "$VENV/bin/activate"
python -m pip install --upgrade pip

install_editable() {
  local dir="$1"
  echo "==> pip install -e $dir (+ dev)"
  (cd "$dir" && pip install -e . && pip install -e ".[dev]")
}

install_editable services/api
install_editable services/router
install_editable services/worker_client
install_editable services/structure
install_editable mcp/servers/filesystem-mcp
install_editable mcp/servers/secrets-mcp
install_editable mcp/servers/vector-db-mcp
install_editable mbmh
install_editable services/wrkhrs

echo "==> Lint (ruff + black + mbmh ruff)"
ruff check services/ mcp/servers/
black --check services/ mcp/servers/
(cd mbmh && python -m ruff check src/ scripts/ tests/)
(cd services/wrkhrs && ruff check \
  services/gateway/app.py \
  tests/_module_loader.py \
  tests/test_gateway.py \
  scripts/test-llm-backends.py)

echo "==> Mypy (per package)"
(cd services/api && mypy --strict src)
(cd services/router && mypy --strict src)
(cd services/worker_client && mypy --strict src)
(cd services/structure && mypy --strict . || true)
(cd mcp/servers/filesystem-mcp && mypy --strict src)
(cd mcp/servers/secrets-mcp && mypy --strict src)
(cd mcp/servers/vector-db-mcp && mypy --strict src)

# Each package uses a top-level `src/` tree; multiple editable installs share the name `src`
# on sys.path. Prefer this package's tree so imports resolve correctly.
echo "==> Pytest (per package; live stack is required)"
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is required for this CI suite (live-stack tests are required)." >&2
  exit 1
fi

docker compose -f docker-compose.ci.yml down -v >/dev/null 2>&1 || true
docker compose -f docker-compose.ci.yml up -d --build
trap 'docker compose -f docker-compose.ci.yml down -v' EXIT

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
  docker compose -f docker-compose.ci.yml ps
  docker compose -f docker-compose.ci.yml logs --no-color --tail=80 tempo || true
  return 1
}

WAIT_HOST="${WAIT_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8080}"
MLFLOW_PORT="${MLFLOW_PORT:-5000}"
TEMPO_PORT="${TEMPO_PORT:-3200}"
MCP_REGISTRY_PORT="${MCP_REGISTRY_PORT:-8001}"

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
  shift
  if [[ ! -d "$dir/tests" ]]; then
    echo "==> SKIP pytest: no $dir/tests"
    return 0
  fi
  (cd "$dir" && PYTHONPATH="$(pwd)" pytest "$@")
}

pytest_pkg services/api tests/ -v --cov=src --cov-report=xml
pytest_pkg services/router tests/ -v --cov=src --cov-report=xml
pytest_pkg services/worker_client tests/ -v --cov=src --cov-report=xml
pytest_pkg services/structure tests/ -v --cov=. --cov-report=xml
pytest_pkg mcp/servers/filesystem-mcp tests/ -v --cov=src --cov-report=xml
pytest_pkg mcp/servers/secrets-mcp tests/ -v --cov=src --cov-report=xml
pytest_pkg mcp/servers/vector-db-mcp tests/ -v --cov=src --cov-report=xml
pytest_pkg mbmh tests/ -v
WRKHRS_DISABLE_MODEL_LOAD=1 pytest_pkg services/wrkhrs tests/ -v --cov=wrkhrs --cov-report=xml --cov-fail-under=90

echo "==> Node (github-mcp)"
if [[ -d "mcp/servers/github-mcp" ]] && compgen -G "mcp/servers/github-mcp/package*.json" > /dev/null; then
  if command -v npm >/dev/null 2>&1; then
    (cd mcp/servers/github-mcp && npm ci && npm run build && npm test)
  else
    echo "SKIP: npm not found"
  fi
else
  echo "SKIP: github-mcp node project files missing (expected package*.json)"
fi

echo "==> Docker builds"
if command -v docker >/dev/null 2>&1; then
  docker build -t agent-orchestrator-api ./services/api
  docker build -t agent-orchestrator-router ./services/router
  docker build -t agent-orchestrator-worker-client ./services/worker_client
  if [[ -f "mcp/servers/filesystem-mcp/Dockerfile" ]]; then
    docker build -t mcp-filesystem ./mcp/servers/filesystem-mcp
  else
    echo "SKIP: mcp-filesystem docker build (Dockerfile missing)"
  fi
  if [[ -f "mcp/servers/secrets-mcp/Dockerfile" ]]; then
    docker build -t mcp-secrets ./mcp/servers/secrets-mcp
  else
    echo "SKIP: mcp-secrets docker build (Dockerfile missing)"
  fi
  if [[ -f "mcp/servers/vector-db-mcp/Dockerfile" ]]; then
    docker build -t mcp-vector-db ./mcp/servers/vector-db-mcp
  else
    echo "SKIP: mcp-vector-db docker build (Dockerfile missing)"
  fi
  if compgen -G "mcp/servers/github-mcp/package*.json" > /dev/null; then
    docker build -t mcp-github ./mcp/servers/github-mcp
  else
    echo "SKIP: mcp-github docker build (expected package*.json)"
  fi
else
  echo "SKIP: docker not found"
fi

echo "==> CI local run finished OK"
