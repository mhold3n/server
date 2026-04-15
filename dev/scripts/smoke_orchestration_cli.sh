#!/usr/bin/env bash
# CLI smoke-test for backend orchestration without OpenClaw.
# Focus order: agent-platform (/health, /llm/info, /chat) → wrkhrs-gateway (/health, /v1/chat/completions).
#
# Usage:
#   bash dev/scripts/smoke_orchestration_cli.sh
#
# Env overrides:
#   AGENT_PLATFORM_BASE_URL (default http://127.0.0.1:${WRKHRS_AGENT_PLATFORM_PORT:-8087})
#   GATEWAY_BASE_URL        (default http://127.0.0.1:${WRKHRS_GATEWAY_PORT:-8091})
#   SMOKE_TEXT              (default "Say only: ok")
#   REQUIRE_REAL_BACKEND=1  (fail if backend_info.type is mock)
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

AP_PORT="${WRKHRS_AGENT_PLATFORM_PORT:-8087}"
GW_PORT="${WRKHRS_GATEWAY_PORT:-8091}"

AP_BASE="${AGENT_PLATFORM_BASE_URL:-http://127.0.0.1:${AP_PORT}}"
GW_BASE="${GATEWAY_BASE_URL:-http://127.0.0.1:${GW_PORT}}"

SMOKE_TEXT="${SMOKE_TEXT:-Say only: ok}"
REQUIRE_REAL_BACKEND="${REQUIRE_REAL_BACKEND:-0}"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

ok() {
  echo "OK: $*"
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"
}

need_cmd curl
need_cmd python3

echo "Smoke: orchestrator=${AP_BASE} gateway=${GW_BASE}"

echo "→ GET ${AP_BASE}/health"
curl -fsS "${AP_BASE}/health" | python3 - <<'PY'
import json,sys
d=json.load(sys.stdin)
assert d.get("workflow_ready") is True, d
llm=d.get("llm_backend") or {}
assert llm.get("healthy") is True, d
print("health ok", llm.get("backend"))
PY
ok "agent-platform /health"

echo "→ GET ${AP_BASE}/llm/info"
AP_LLM_INFO="$(curl -fsS "${AP_BASE}/llm/info")"
echo "$AP_LLM_INFO" | python3 - <<PY
import json,sys,os
d=json.load(sys.stdin)
backend=(d.get("backend_info") or {}).get("type") or ""
healthy=(d.get("health") or {}).get("healthy")
assert healthy is True, d
require=int(os.environ.get("REQUIRE_REAL_BACKEND","0"))
if require == 1:
  assert backend and backend != "mock", d
print("llm ok", backend)
PY
ok "agent-platform /llm/info"

echo "→ POST ${AP_BASE}/chat"
curl -fsS "${AP_BASE}/chat" \
  -H 'Content-Type: application/json' \
  -d "$(python3 - <<PY
import json,os
print(json.dumps({"messages":[{"role":"user","content":os.environ["SMOKE_TEXT"]}]}))
PY
)" | python3 - <<'PY'
import json,sys
d=json.load(sys.stdin)
choices=d.get("choices") or []
msg=(choices[0].get("message") if choices else {}) or {}
content=msg.get("content")
assert isinstance(content,str) and content.strip(), d
print("chat ok", content[:80])
PY
ok "agent-platform /chat"

echo "→ GET ${GW_BASE}/health"
curl -fsS "${GW_BASE}/health" | python3 - <<'PY'
import json,sys
d=json.load(sys.stdin)
status=d.get("status")
assert status in ("healthy","ok") or d.get("authentication_enabled") in (True, False) or d.get("embedding_model_loaded") in (True, False) or d.get("ok") is True, d
print("gateway health ok")
PY
ok "wrkhrs-gateway /health"

echo "→ POST ${GW_BASE}/v1/chat/completions"
curl -fsS "${GW_BASE}/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d "$(python3 - <<PY
import json,os
print(json.dumps({"messages":[{"role":"user","content":os.environ["SMOKE_TEXT"]}]}))
PY
)" | python3 - <<'PY'
import json,sys
d=json.load(sys.stdin)
choices=d.get("choices") or []
msg=(choices[0].get("message") if choices else {}) or {}
content=msg.get("content")
assert isinstance(content,str) and content.strip(), d
print("gateway chat ok", content[:80])
PY
ok "wrkhrs-gateway /v1/chat/completions"

echo "smoke_orchestration_cli: OK"

