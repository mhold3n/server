#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
ENV_DIR="$ROOT/.cache/knowledge-envs/eng-geometry"
exec "$ENV_DIR/bin/python" "$@"
