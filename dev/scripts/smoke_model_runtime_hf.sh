#!/usr/bin/env bash
# Smoke-test model-runtime HTTP: /health and POST /infer/multimodal.
# For agents: no auth; uses MOCK_INFER behavior of the running container (default 1 in compose).
# Env: MODEL_RUNTIME_BASE_URL (default http://127.0.0.1:${MODEL_RUNTIME_PORT:-8765}).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PORT="${MODEL_RUNTIME_PORT:-8765}"
BASE="${MODEL_RUNTIME_BASE_URL:-http://127.0.0.1:${PORT}}"

echo "Probing model-runtime at ${BASE}"

curl -fsS "${BASE}/health" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("status")=="ok", d; print("health ok", d.get("mock_infer"), list(d.get("roles",{}).keys()))'

BODY="$(python3 <<'PY'
import json
import uuid

tid = str(uuid.uuid4())
print(
    json.dumps(
        {
            "task_packet_id": tid,
            "schema_version": "1.0.0",
            "status": "PENDING",
            "task_type": "MULTIMODAL_EXTRACTION",
            "title": "t",
            "objective": "extract",
            "input_artifact_refs": ["artifact://document_extract/x"],
            "required_outputs": [
                {"artifact_type": "DOCUMENT_EXTRACT", "schema_version": "1.0.0"}
            ],
            "acceptance_criteria": ["c1"],
            "budget_policy": {"allow_escalation": False},
            "routing_metadata": {
                "requested_by": "smoke_model_runtime_hf",
                "selected_executor": "multimodal_model",
                "reason": "smoke",
                "router_policy_version": "1",
            },
            "provenance": {"source_stage": "task_generation"},
            "created_at": "2026-04-07T12:00:00Z",
            "updated_at": "2026-04-07T12:00:00Z",
        }
    )
)
PY
)"

curl -fsS -X POST "${BASE}/infer/multimodal" \
  -H "Content-Type: application/json" \
  -d "$BODY" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("model_id_resolved"), d; assert "usage" in d; print("infer/multimodal ok", d.get("model_id_resolved"))'

echo "smoke_model_runtime_hf: OK"
