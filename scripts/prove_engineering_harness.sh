#!/usr/bin/env bash
# prove_engineering_harness.sh — run the probative local engineering harness in one shot.
#
# Prerequisites: `uv` on PATH; sibling clone of https://github.com/XLOTYL/xlotyl at ../xlotyl
# (override with XLOTYL_ROOT).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
XLOTYL_ROOT="${XLOTYL_ROOT:-$ROOT/../xlotyl}"
cd "$ROOT"

if [[ ! -d "$XLOTYL_ROOT/services/engineering-core" ]]; then
  echo "ERROR: engineering-core not found under XLOTYL_ROOT=$XLOTYL_ROOT" >&2
  exit 1
fi

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

echo "==> Engineering harness (CACHE_ROOT=$CACHE_ROOT, XLOTYL_ROOT=$XLOTYL_ROOT)"

echo "==> validate_control_plane_schemas.py"
uv run python "$ROOT/scripts/validate_control_plane_schemas.py"

echo "==> validate_model_runtime_schemas.py"
uv run python "$ROOT/scripts/validate_model_runtime_schemas.py"

echo "==> pytest engineering-core"
(
  cd "$XLOTYL_ROOT/services/engineering-core"
  PYTEST_ADDOPTS="-o cache_dir=$CACHE_ROOT/pytest/engineering-core ${PYTEST_ADDOPTS:-}" \
    uv run pytest tests -q
)

echo "==> pytest model-runtime"
(
  cd "$XLOTYL_ROOT/services/model-runtime"
  PYTEST_ADDOPTS="-o cache_dir=$CACHE_ROOT/pytest/model-runtime ${PYTEST_ADDOPTS:-}" \
    uv run pytest tests -q
)

echo "==> npm (xlotyl agent platform smoke)"
(
  cd "$XLOTYL_ROOT"
  npm ci
  npm run build -w @xlotyl/open-multi-agent
  npm run build -w @xlotyl/agent-platform-server
  LLM_BACKEND=mock npm run test -w @xlotyl/agent-platform-server
)

echo "==> Engineering harness: OK"
