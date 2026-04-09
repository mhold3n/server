#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
exec docker run --rm -v "$ROOT:$ROOT" -w "$ROOT" birtha/knowledge-eng-dealii:1.0.0 "$@"
