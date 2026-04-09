#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
exec docker run --rm -v "$ROOT:$ROOT" -w "$ROOT" birtha/knowledge-eng-system:1.0.0 "$@"
