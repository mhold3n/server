#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d ".venv-qwen" ]; then
  echo "ERROR: .venv-qwen not found. Expected at $ROOT_DIR/.venv-qwen" >&2
  exit 1
fi

echo "Using virtualenv: $ROOT_DIR/.venv-qwen"
source ".venv-qwen/bin/activate"

echo "Starting transformers server for Qwen/Qwen3.5-9B on port 8000..."
exec transformers serve --force-model Qwen/Qwen3.5-9B --port 8000 --continuous-batching

