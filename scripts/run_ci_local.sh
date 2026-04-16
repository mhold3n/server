#!/usr/bin/env bash
# Replicate .github/workflows/ci.yml build-test job locally (no act/Docker required for Python parts).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
WRKHRS_ROOT="$ROOT/xlotyl/services/ai-gateway-service"
WRKHRS_GATEWAY_APP="$WRKHRS_ROOT/services/gateway/app.py"
WRKHRS_GATEWAY_TEST="$WRKHRS_ROOT/tests/test_gateway.py"
WRKHRS_MODULE_LOADER_TEST="$WRKHRS_ROOT/tests/_module_loader.py"
CI_COMPOSE="docker/compose-profiles/docker-compose.ci.yml"
# Optional: COMPOSE_DATA_ROOT for bind-mounted CI state (defaults to .docker-data/ under repo).

PYTHON="${PYTHON:-python3.11}"
# shellcheck source=/dev/null
source "$ROOT/scripts/workspace_env.sh"

echo "==> Using Python: $($PYTHON --version)"
echo "==> Workspace env: $ROOT/.venv"

if [[ ! -f "$WRKHRS_GATEWAY_APP" ]]; then
  echo "ERROR: expected WrkHrs gateway app at $WRKHRS_GATEWAY_APP" >&2
  exit 1
fi
if [[ ! -f "$WRKHRS_GATEWAY_TEST" ]]; then
  echo "ERROR: expected WrkHrs gateway test at $WRKHRS_GATEWAY_TEST" >&2
  exit 1
fi

uv sync --python "$PYTHON"

echo "==> Wiki compile drift check (orchestration markdown vs response-control JSON)"
(cd xlotyl && uv sync --python "$PYTHON" && uv run python scripts/sync_domain_orchestration_wiki.py && uv run python scripts/wiki_compile_response_control.py --check)
echo "==> Wiki proposal queue validation"
(cd xlotyl && uv run python scripts/check_wiki_proposal_queue.py)

echo "==> Lint (ruff + black: xlotyl + MCP)"
(cd xlotyl && uv sync --python "$PYTHON" && uv run ruff check services/api-service services/router-service services/worker-service services/model-runtime services/engineering-core services/mcp-registry-service services/response-control-framework services/domain-engineering services/domain-research services/domain-content services/ai-shared-service services/structure-service services/media-service && uv run black --check services/api-service services/router-service services/worker-service services/model-runtime services/engineering-core services/mcp-registry-service services/response-control-framework services/domain-engineering services/domain-research services/domain-content services/ai-shared-service services/structure-service services/media-service)
uv run ruff check mcp-servers/mcp/servers/
uv run black --check mcp-servers/mcp/servers/
# WrkHrs uses its own package root. These paths are relative to services/ai-gateway-service/,
# not the repo-level services/ tree.
(cd xlotyl/services/ai-gateway-service && uv run --package ai-gateway-service ruff check \
  services/gateway/app.py \
  tests/_module_loader.py \
  tests/test_gateway.py \
  scripts/test-llm-backends.py)

echo "==> Mypy (per package)"
(cd xlotyl/services/api-service && MYPY_CACHE_DIR="$MYPY_CACHE_ROOT/services-api" uv run --package agent-orchestrator-api mypy --strict src)
(cd xlotyl/services/router-service && MYPY_CACHE_DIR="$MYPY_CACHE_ROOT/services-router" uv run --package agent-orchestrator-router mypy --strict src)
(cd xlotyl/services/worker-service && MYPY_CACHE_DIR="$MYPY_CACHE_ROOT/services-worker-client" uv run --package agent-orchestrator-worker-client mypy --strict src)
(cd xlotyl/services/structure-service && MYPY_CACHE_DIR="$MYPY_CACHE_ROOT/services-structure" uv run --package structure mypy --strict .)
(cd mcp-servers/mcp/servers/filesystem-mcp && MYPY_CACHE_DIR="$MYPY_CACHE_ROOT/mcp-filesystem" uv run --package filesystem-mcp-server mypy --strict src)
(cd mcp-servers/mcp/servers/secrets-mcp && MYPY_CACHE_DIR="$MYPY_CACHE_ROOT/mcp-secrets" uv run --package secrets-mcp-server mypy --strict src)
(cd mcp-servers/mcp/servers/vector-db-mcp && MYPY_CACHE_DIR="$MYPY_CACHE_ROOT/mcp-vector-db" uv run --package vector-db-mcp-server mypy --strict src)

# Each package uses a top-level `src/` tree; multiple editable installs share the name `src`
# on sys.path. Prefer this package's tree so imports resolve correctly.
echo "==> Pytest (per package; live stack is required)"
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is required for this CI suite (live-stack tests are required)." >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker CLI is present but the daemon is not reachable (start Docker Desktop / dockerd)." >&2
  exit 1
fi

docker compose --project-directory "$ROOT" -f "$CI_COMPOSE" down -v >/dev/null 2>&1 || true
docker compose --project-directory "$ROOT" -f "$CI_COMPOSE" up -d --build
trap 'docker compose --project-directory "$ROOT" -f "$CI_COMPOSE" down -v' EXIT

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
  docker compose --project-directory "$ROOT" -f "$CI_COMPOSE" ps
  docker compose --project-directory "$ROOT" -f "$CI_COMPOSE" logs --no-color --tail=80 tempo || true
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
  local cache_name="$2"
  shift
  shift
  if [[ ! -d "$dir/tests" ]]; then
    echo "==> SKIP pytest: no $dir/tests"
    return 0
  fi
  mkdir -p "$PYTEST_CACHE_ROOT/$cache_name"
  (cd "$dir" && PYTHONPATH="$(pwd)" PYTEST_ADDOPTS="-o cache_dir=$PYTEST_CACHE_ROOT/$cache_name ${PYTEST_ADDOPTS:-}" uv run pytest "$@")
}

pytest_pkg xlotyl/services/api-service services-api tests/ -v --cov=src --cov-report=xml
pytest_pkg xlotyl/services/router-service services-router tests/ -v --cov=src --cov-report=xml
pytest_pkg xlotyl/services/worker-service services-worker-client tests/ -v --cov=src --cov-report=xml
pytest_pkg xlotyl/services/structure-service services-structure tests/ -v --cov=. --cov-report=xml
pytest_pkg mcp-servers/mcp/servers/filesystem-mcp mcp-filesystem tests/ -v --cov=src --cov-report=xml
pytest_pkg mcp-servers/mcp/servers/secrets-mcp mcp-secrets tests/ -v --cov=src --cov-report=xml
pytest_pkg mcp-servers/mcp/servers/vector-db-mcp mcp-vector-db tests/ -v --cov=src --cov-report=xml
WRKHRS_DISABLE_MODEL_LOAD=1 pytest_pkg xlotyl/services/ai-gateway-service services-ai-gateway tests/ -v --cov=services/gateway --cov=services/prompt_middleware --cov=services/rag --cov-report=xml --cov-fail-under=90

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

echo "==> Docker builds"
if command -v docker >/dev/null 2>&1; then
  docker build -f xlotyl/services/api-service/Dockerfile -t agent-orchestrator-api ./xlotyl
  docker build -t agent-orchestrator-router ./xlotyl/services/router-service
  docker build -t agent-orchestrator-worker-client ./xlotyl/services/worker-service
  if [[ -f "mcp-servers/mcp/servers/filesystem-mcp/Dockerfile" ]]; then
    docker build -t mcp-filesystem ./mcp-servers/mcp/servers/filesystem-mcp
  else
    echo "SKIP: mcp-filesystem docker build (Dockerfile missing)"
  fi
  if [[ -f "mcp-servers/mcp/servers/secrets-mcp/Dockerfile" ]]; then
    docker build -t mcp-secrets ./mcp-servers/mcp/servers/secrets-mcp
  else
    echo "SKIP: mcp-secrets docker build (Dockerfile missing)"
  fi
  if [[ -f "mcp-servers/mcp/servers/vector-db-mcp/Dockerfile" ]]; then
    docker build -t mcp-vector-db ./mcp-servers/mcp/servers/vector-db-mcp
  else
    echo "SKIP: mcp-vector-db docker build (Dockerfile missing)"
  fi
  if compgen -G "mcp-servers/mcp/servers/github-mcp/package*.json" > /dev/null; then
    docker build -t mcp-github ./mcp-servers/mcp/servers/github-mcp
  else
    echo "SKIP: mcp-github docker build (expected package*.json)"
  fi
else
  echo "SKIP: docker not found"
fi

echo "==> CI local run finished OK"
