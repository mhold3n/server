#!/usr/bin/env bash
# Run ~/.openclaw/bin/sync-skill-secrets.py after 1Password CLI is ready.
# Usage: from a signed-in shell — eval "$(op signin)" then ./run-sync-skill-secrets.sh
set -euo pipefail

OP_BIN="${OP_BIN:-/opt/homebrew/bin/op}"
SYNC_PY="${OPENCLAW_HOME:-$HOME/.openclaw}/bin/sync-skill-secrets.py"
export OP_CONFIG_DIR="${OP_CONFIG_DIR:-$HOME/.config/op}"
export OP_TIMEOUT_SECONDS="${OP_TIMEOUT_SECONDS:-30}"

if [[ ! -x "$SYNC_PY" ]]; then
  echo "error: missing $SYNC_PY" >&2
  exit 1
fi

if ! "$OP_BIN" whoami &>/dev/null; then
  echo "error: 1Password CLI has no session. In this terminal run:" >&2
  echo "  eval \"\$(op signin)\"" >&2
  echo "  $OP_BIN whoami" >&2
  echo "For launchd/gateway-only automation, use a 1Password service account (OP_SERVICE_ACCOUNT_TOKEN)." >&2
  exit 1
fi

exec python3 "$SYNC_PY"
