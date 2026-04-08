#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT_DIR"

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required. Install from https://brew.sh" >&2
  exit 1
fi

brew install ffmpeg meilisearch ollama

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install from https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

scripts/bootstrap_tool_env.sh marker-pdf
scripts/bootstrap_tool_env.sh larrak-audio

echo "Bootstrap complete."
echo "1) source .cache/envs/larrak-audio/bin/activate"
echo "2) export MARKER_BIN=\"$ROOT_DIR/.cache/envs/marker-pdf/bin/marker_single\""
echo "3) larrak-audio doctor"
echo "4) larrak-audio ingest --source <file.pdf> --type pdf"
