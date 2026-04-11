#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
exec docker run --rm --platform linux/amd64 -v "$ROOT:$ROOT" -w "$ROOT" birtha/knowledge-eng-code-saturne:1.0.0 "$@"
