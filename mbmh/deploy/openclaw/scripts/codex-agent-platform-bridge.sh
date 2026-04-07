#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
codex-agent-platform-bridge.sh

Minimal Codex CLI shim that forwards "codex exec <prompt>" to agent-platform:
  POST /v1/agents/run

Install (example):
  ln -sf /Users/maxholden/GitHub/server/mbmh/deploy/openclaw/scripts/codex-agent-platform-bridge.sh ~/.local/bin/codex

Env:
  AGENT_PLATFORM_URL            Default: http://127.0.0.1:8001
  OPENCLAW_ORCH_AGENT_NAME      Default: local-orchestrator
  OPENCLAW_ORCH_MODEL           Default: claude-sonnet-4-20250514
  OPENCLAW_ORCH_PROVIDER        Default: anthropic
  OPENCLAW_ORCH_SYSTEM_PROMPT   Optional

Only supports:
  codex exec "<prompt>"
EOF
  exit 2
}

if [[ "${1:-}" == "" || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
fi

sub="${1:-}"
shift || true

if [[ "$sub" != "exec" ]]; then
  echo "error: only 'codex exec' is supported by this bridge" >&2
  usage
fi

if [[ "${1:-}" == "" ]]; then
  echo "error: missing prompt" >&2
  usage
fi

prompt="$*"

base="${AGENT_PLATFORM_URL:-http://127.0.0.1:8001}"
base="${base%/}"

agent_name="${OPENCLAW_ORCH_AGENT_NAME:-local-orchestrator}"
# Defaults assume you're targeting the local MBMH OpenAI-compatible runtime.
model="${OPENCLAW_ORCH_MODEL:-openclaw-agent}"
provider="${OPENCLAW_ORCH_PROVIDER:-openai}"
system_prompt="${OPENCLAW_ORCH_SYSTEM_PROMPT:-}"

payload="$(BRIDGE_PROMPT="$prompt" \
  BRIDGE_AGENT_NAME="$agent_name" \
  BRIDGE_MODEL="$model" \
  BRIDGE_PROVIDER="$provider" \
  BRIDGE_SYSTEM_PROMPT="$system_prompt" \
  python3 - <<'PY'
import json, os
prompt = os.environ["BRIDGE_PROMPT"]
agent = {
  "name": os.environ["BRIDGE_AGENT_NAME"],
  "model": os.environ["BRIDGE_MODEL"],
  "provider": os.environ["BRIDGE_PROVIDER"],
}
sp = os.environ.get("BRIDGE_SYSTEM_PROMPT", "")
if sp:
  agent["systemPrompt"] = sp
print(json.dumps({"agent": agent, "prompt": prompt}))
PY
)" || exit 1

resp="$(curl -sS "${base}/v1/agents/run" \
  -H "Content-Type: application/json" \
  -d "$payload")"

ok="$(python3 -c 'import json,sys; data=json.loads(sys.stdin.read() or "{}"); print("1" if data.get("success") else "0")' <<<"$resp")"
out="$(python3 -c 'import json,sys; data=json.loads(sys.stdin.read() or "{}"); print(data.get("output",""))' <<<"$resp")"

if [[ "$ok" != "1" ]]; then
  echo "$resp" >&2
  exit 1
fi

if [[ "${out//$'\n'/}" == "" ]]; then
  echo "error: agent-platform returned success but empty output (likely mock backend)" >&2
  echo "$resp" >&2
  exit 1
fi

printf "%s\n" "$out"

