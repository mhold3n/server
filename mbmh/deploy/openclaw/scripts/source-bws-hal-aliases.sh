#!/usr/bin/env bash
# Map Birtha/OpenClaw standard BWS env names to HAL_* names expected by some
# community tooling (e.g. jamaynor/openclaw-skill-secret-manager-bws: secrets-bws,
# bws-mcp-wrapper). Intended to be sourced after bws.env is loaded.
#
# Usage (e.g. from ~/.openclaw/bin/openclaw-gateway-wrapper.sh after sourcing bws.env):
#   # shellcheck source=source-bws-hal-aliases.sh
#   source /path/to/server/mbmh/deploy/openclaw/scripts/source-bws-hal-aliases.sh
#
# Optional in bws.env for HAL_BWS_ORGANIZATION_ID:
#   BWS_ORGANIZATION_ID="<org-uuid>"
#
# Do not use `set -euo pipefail` here: this file is sourced into the caller's shell
# and must not persistently change shell options.

if [[ -n "${BWS_ACCESS_TOKEN:-}" && -z "${HAL_BWS_ACCESS_TOKEN:-}" ]]; then
  export HAL_BWS_ACCESS_TOKEN="$BWS_ACCESS_TOKEN"
fi

if [[ -n "${BWS_ORGANIZATION_ID:-}" && -z "${HAL_BWS_ORGANIZATION_ID:-}" ]]; then
  export HAL_BWS_ORGANIZATION_ID="$BWS_ORGANIZATION_ID"
fi
