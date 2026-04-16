#!/usr/bin/env bash
# prove_engineering_harness.sh — run the probative local engineering harness in one shot.
#
# Intended behavior:
# - Apply canonical cache paths via scripts/workspace_env.sh → scripts/cache_env.sh
#   (HARNESS_CACHE_ROOT overrides CACHE_ROOT for this run when set).
# - Execute the matrix documented under `schemas/control-plane/v1/README.md`:
#   control-plane + model-runtime schema gates, engineering-core + model-runtime pytest,
#   root npm workspace tests (open-multi-agent + agent-platform server + topology-viewer).
#
# Prerequisites: `uv` on PATH; `npm install` at repo root for Node workspaces.
# Optional: root `uv sync` (see `make sync`) so `uv run python` resolves workspace deps.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -n "${HARNESS_CACHE_ROOT:-}" ]]; then
  export CACHE_ROOT="$HARNESS_CACHE_ROOT"
fi

# shellcheck source=/dev/null
source "$ROOT/scripts/workspace_env.sh"

mkdir -p \
  "$CACHE_ROOT/pytest/engineering-core" \
  "$CACHE_ROOT/pytest/model-runtime"

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv is required (https://docs.astral.sh/uv/)." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: npm is required for the workspace test step." >&2
  exit 1
fi

echo "==> Engineering harness (CACHE_ROOT=$CACHE_ROOT)"

echo "==> validate_control_plane_schemas.py"
uv run python "$ROOT/scripts/validate_control_plane_schemas.py"

echo "==> validate_model_runtime_schemas.py"
uv run python "$ROOT/scripts/validate_model_runtime_schemas.py"

echo "==> pytest xlotyl/services/engineering-core/tests"
(
  cd "$ROOT/xlotyl/services/engineering-core"
  PYTEST_ADDOPTS="-o cache_dir=$CACHE_ROOT/pytest/engineering-core ${PYTEST_ADDOPTS:-}" \
    uv run pytest tests -q
)

echo "==> pytest xlotyl/services/model-runtime/tests"
(
  cd "$ROOT/xlotyl/services/model-runtime"
  PYTEST_ADDOPTS="-o cache_dir=$CACHE_ROOT/pytest/model-runtime ${PYTEST_ADDOPTS:-}" \
    uv run pytest tests -q
)

echo "==> npm test (root workspaces)"
npm test

echo "==> Engineering harness: OK"
