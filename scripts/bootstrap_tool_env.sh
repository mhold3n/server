#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source "$ROOT/scripts/workspace_env.sh"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it from https://docs.astral.sh/uv/" >&2
  exit 1
fi

TOOL_NAME="${1:-}"
if [[ -z "$TOOL_NAME" ]]; then
  cat <<'EOF' >&2
Usage: scripts/bootstrap_tool_env.sh <tool>

Supported tools:
  marker-pdf
  whisper-asr
  qwen-runtime
  mbmh
  larrak-audio
EOF
  exit 1
fi
shift || true

PYTHON_BIN="${PYTHON_BIN:-python3.11}"
ENV_DIR="$TOOL_ENV_ROOT/$TOOL_NAME"

ensure_env() {
  uv venv --python "$PYTHON_BIN" "$ENV_DIR" >/dev/null
}

install_into_env() {
  uv pip install --python "$ENV_DIR/bin/python" "$@"
}

case "$TOOL_NAME" in
  marker-pdf)
    ensure_env
    install_into_env marker-pdf
    ;;
  whisper-asr)
    ensure_env
    install_into_env openai-whisper
    install_into_env -e "$ROOT/services/wrkhrs[asr]" -e "$ROOT/services/martymedia"
    ;;
  qwen-runtime)
    ensure_env
    install_into_env \
      "torch>=2.0.0" \
      "transformers>=4.39" \
      "accelerate>=0.30.0" \
      "huggingface_hub>=0.24.0" \
      "qwen-vl-utils>=0.0.8" \
      "fastapi>=0.115" \
      "uvicorn[standard]>=0.27"
    ;;
  mbmh)
    ensure_env
    install_into_env -e "$ROOT/mbmh[dev,eval]"
    ;;
  larrak-audio)
    ensure_env
    install_into_env -e "$ROOT/services/larrak-audio[dev,api]"
    ;;
  *)
    echo "Unknown tool env: $TOOL_NAME" >&2
    exit 1
    ;;
esac

echo "Bootstrapped $TOOL_NAME at $ENV_DIR"
