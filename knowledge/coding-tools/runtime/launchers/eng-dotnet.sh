#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
export DOTNET_ROLL_FORWARD="${DOTNET_ROLL_FORWARD:-Major}"
exec dotnet run --project "$ROOT/knowledge/coding-tools/runtime/dotnet/eng-dotnet/KnowledgeDotnetRuntime.csproj" -c Release -- "$@"
