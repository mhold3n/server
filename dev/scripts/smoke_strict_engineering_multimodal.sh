#!/usr/bin/env bash
# Live smoke: POST /api/ai/query with strict_engineering so API delegates engineering_workflow
# to agent-platform (requires API + wrkhrs-agent-platform + control plane reachable from agent-platform).
# For agents: opt-in via RUN_STRICT_ENGINEERING_SMOKE=1 to avoid accidental calls in sandboxes.
# Env: API_BASE_URL (default http://127.0.0.1:${API_PORT:-8080}).

set -euo pipefail

if [[ "${RUN_STRICT_ENGINEERING_SMOKE:-}" != "1" ]]; then
  echo "Skip: set RUN_STRICT_ENGINEERING_SMOKE=1 to run strict-engineering API smoke."
  exit 0
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

API="${API_BASE_URL:-http://127.0.0.1:${API_PORT:-8080}}"

BODY='{
  "prompt": "Strict engineering smoke: summarize required gates for a trivial documentation-only change.",
  "engagement_mode": "strict_engineering",
  "model": "gpt-4o-mini"
}'

echo "POST ${API}/api/ai/query (strict_engineering)"

RESP="$(curl -sS -w "\n%{http_code}" -X POST "${API}/api/ai/query" \
  -H "Content-Type: application/json" \
  -d "$BODY")"

CODE="$(echo "$RESP" | tail -n1)"
JSON="$(echo "$RESP" | sed '$d')"

if [[ "$CODE" != "200" ]]; then
  echo "HTTP $CODE" >&2
  echo "$JSON" >&2
  exit 1
fi

echo "$JSON" | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d.get("result") or d; assert isinstance(r,dict), d; assert ("final_response" in r or "verification_outcome" in r or "referential_state" in r), list(r.keys())[:25]; print("strict_engineering smoke: OK (HTTP 200, orchestrator returned payload)")'

echo "smoke_strict_engineering_multimodal: OK"
