#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# shellcheck source=/dev/null
source "$ROOT_DIR/scripts/workspace_env.sh"

QWEN_ENV="${TOOL_ENV_ROOT}/qwen-runtime"

if [ ! -d "$QWEN_ENV" ]; then
  echo "ERROR: qwen-runtime env not found. Bootstrap it with: scripts/bootstrap_tool_env.sh qwen-runtime" >&2
  exit 1
fi

echo "Using virtualenv: $QWEN_ENV"
source "$QWEN_ENV/bin/activate"

echo "Starting transformers server for Qwen/Qwen3.5-9B on port 8000..."
exec transformers serve --force-model Qwen/Qwen3.5-9B --port 8000 --continuous-batching
