#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LEGACY_ARCHIVE_ROOT="${LEGACY_ARCHIVE_ROOT:-$ROOT/../server-local-archive/2026-04-08/server}"
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
  larrak-audio

Archived compatibility alias:
  mbmh
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
    install_into_env -e "$ROOT/services/ai-gateway-service[asr]" -e "$ROOT/services/media-service"
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
    echo "mbmh has been archived out of this repo." >&2
    echo "Legacy files now live under: $LEGACY_ARCHIVE_ROOT/mbmh" >&2
    echo "Use the archived tree directly if you need the historical training/runtime environment." >&2
    exit 1
    ;;
  larrak-audio)
    ensure_env
    install_into_env -e "$ROOT/services/audio-service[dev,api]"
    ;;
  *)
    echo "Unknown tool env: $TOOL_NAME" >&2
    exit 1
    ;;
esac

echo "Bootstrapped $TOOL_NAME at $ENV_DIR"
