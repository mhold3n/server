#!/usr/bin/env bash
# download_qwen_engineering_models.sh — populate HF_HOME with weights for the
# three model-runtime roles (general, coding, multimodal) used by the governed
# engineering path (orchestrator + coding worker + multimodal extractor).
#
# Source of truth for IDs: services/model-runtime/config/models.yaml
# Compose mounts ./.cache/models/hf at /.cache/models/hf inside model-runtime.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source "$ROOT/scripts/workspace_env.sh"

QWEN_ENV="${TOOL_ENV_ROOT}/qwen-runtime"
if [[ ! -x "${QWEN_ENV}/bin/python" ]]; then
  "$ROOT/scripts/bootstrap_tool_env.sh" qwen-runtime
fi

# Prefer the CLI from the qwen-runtime venv; fall back to PATH (e.g. uv tool).
HF_BIN=""
if [[ -x "${QWEN_ENV}/bin/hf" ]]; then
  HF_BIN="${QWEN_ENV}/bin/hf"
elif command -v hf >/dev/null 2>&1; then
  HF_BIN="$(command -v hf)"
else
  echo "ERROR: 'hf' CLI not found. Install huggingface_hub in qwen-runtime or add hf to PATH." >&2
  exit 1
fi

MODEL_IDS=(
  "Qwen/Qwen3-4B"
  "Qwen/Qwen2.5-Coder-7B-Instruct"
  "Qwen/Qwen2.5-VL-3B-Instruct"
)

echo "Using HF_HOME=$HF_HOME (snapshots land here; docker compose ai profile mounts this tree)"
for id in "${MODEL_IDS[@]}"; do
  echo "==> hf download $id"
  "$HF_BIN" download "$id"
done

echo "Downloads finished."
echo "Next: run model-runtime with MOCK_INFER=0, or keep MOCK_INFER=1 for CI and use these weights only for local HF smoke."
