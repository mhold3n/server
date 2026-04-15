#!/usr/bin/env bash
set -euo pipefail

# Quick redeploy for agent caddy (8443) after fixing mount/import errors.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "[INFO] Redeploying caddy (agent) with server override..."
docker compose --project-directory "$ROOT_DIR" \
  -f docker-compose.yml \
  -f docker/compose-profiles/docker-compose.platform.yml \
  -f docker/compose-profiles/docker-compose.ai.yml \
  -f docker/compose-profiles/docker-compose.server.yml \
  up -d caddy

echo "[INFO] Recent caddy logs (last 50 lines):"
docker compose --project-directory "$ROOT_DIR" \
  -f docker-compose.yml \
  -f docker/compose-profiles/docker-compose.platform.yml \
  -f docker/compose-profiles/docker-compose.ai.yml \
  -f docker/compose-profiles/docker-compose.server.yml \
  logs --tail 50 caddy || true

echo "[INFO] Probing caddy on localhost:8443 (expect 403 from localhost)"
set +e
code=$(curl -sk -o /dev/null -w '%{http_code}' -H 'Host: api.lan' https://127.0.0.1:8443/ || true)
echo "caddy:8443 api.lan / -> ${code}"
set -e

echo "[DONE] If running from the Docker VM, test from a LAN client:"
echo "       curl -sk https://api.lan:8443/health"
