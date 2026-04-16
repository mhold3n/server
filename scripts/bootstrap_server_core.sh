#!/usr/bin/env bash
# Clone is assumed done. From repo root: sync submodules, Python (uv), Node (npm), then optional core stack.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> deps:external (git submodules via sync_external_repos.sh)"
npm run deps:external

echo "==> uv sync (workspace + lockfile; no per-dep git clones)"
command -v uv >/dev/null 2>&1 || {
  echo "Install uv: https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
}
uv sync --python 3.11

echo "==> npm install (root workspaces)"
npm install

echo "==> Bootstrap complete."
echo "    Optional: copy .env from .env.example, then start core orchestration:"
echo "      cp -n .env.example .env   # if needed"
echo "      make core-up"
