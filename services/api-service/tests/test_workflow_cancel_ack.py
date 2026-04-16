"""``POST /api/ai/workflows/{id}/cancel`` returns typed ``cancel_ack`` (bridge Phase 3.3)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from src.main import app
from test_paths import openclaw_stream_event_schema_path

_SCHEMA_PATH = openclaw_stream_event_schema_path()


def test_cancel_workflow_wraps_upstream_and_cancel_ack() -> None:
    inner = MagicMock()
    inner.cancel_workflow = AsyncMock(return_value={"upstream": "ok"})
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=inner)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("src.routes.ai.OrchestratorClient", return_value=mock_cm):
        client = TestClient(app)
        r = client.post("/api/ai/workflows/wf_cancel_route/cancel")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["orchestrator"] == {"upstream": "ok"}
    ack = body["cancel_ack"]
    assert ack["type"] == "cancel.ack"
    assert ack["payload"]["workflow_id"] == "wf_cancel_route"
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(ack)
