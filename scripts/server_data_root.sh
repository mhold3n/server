#!/usr/bin/env bash
set -euo pipefail

# Discover the host-specific data root for this repo.
#
# Goal: keep "permanent directories" stable as:
#   "${SERVER_DATA_ROOT}/server/..."
#
# Examples:
# - Linux server:   /mnt/appdata/server/...
# - macOS dev:      /Users/<user>/Library/Application Support/server/...
#
# Rules:
# - If SERVER_DATA_ROOT is already set, trust it.
# - Otherwise, scan a small set of known locations for a `server/` directory.
# - If none found, pick a safe default and print it.
#
# Usage:
#   SERVER_DATA_ROOT="$(./scripts/server_data_root.sh)"  # prints only the root

if [[ "${SERVER_DATA_ROOT:-}" != "" ]]; then
  printf "%s\n" "${SERVER_DATA_ROOT}"
  exit 0
fi

uname_s="$(uname -s | tr '[:upper:]' '[:lower:]')"

candidates=()
if [[ "$uname_s" == "darwin" ]]; then
  candidates+=(
    "$HOME/Library/Application Support"
    "$HOME/.local/share"
    "$HOME"
    "/Users/Shared"
  )
else
  candidates+=(
    "/mnt/appdata"
    "/srv"
    "/var/lib"
    "/opt"
    "$HOME/.local/share"
    "$HOME"
  )
fi

for root in "${candidates[@]}"; do
  if [[ -d "$root/server" ]]; then
    printf "%s\n" "$root"
    exit 0
  fi
done

# Default: prefer /mnt/appdata when available, else fall back to per-user storage.
if [[ "$uname_s" != "darwin" && -d "/mnt/appdata" ]]; then
  printf "%s\n" "/mnt/appdata"
  exit 0
fi

if [[ "$uname_s" == "darwin" ]]; then
  printf "%s\n" "$HOME/Library/Application Support"
  exit 0
fi

printf "%s\n" "$HOME/.local/share"

