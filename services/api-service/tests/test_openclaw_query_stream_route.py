"""HTTP integration for ``POST /api/ai/query/stream`` (bridge + resume headers)."""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from src.main import app


def _parse_sse_data_lines(s: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for block in s.split("\n\n"):
        for line in block.split("\n"):
            if line.startswith("data:"):
                txt = line[5:].strip()
                if txt:
                    out.append(json.loads(txt))
    return out


def test_query_stream_includes_resume_ack_when_last_event_id_header() -> None:
    out = {"result": {"final_response": "m", "referential_state": {}}}
    mock_pipe = AsyncMock(return_value=out)

    with patch("src.routes.ai.execute_ai_query_pipeline", mock_pipe):
        with patch("src.app.redis_client", None):
            client = TestClient(app)
            r = client.post(
                "/api/ai/query/stream",
                json={"prompt": "hello"},
                headers={"Last-Event-ID": "7"},
            )
    assert r.status_code == 200, r.text
    events = _parse_sse_data_lines(r.text)
    assert events[0]["type"] == "resume.ack"
    assert events[0]["payload"].get("last_event_id") == "7"
    assert events[1]["type"] == "run.started"
    mock_pipe.assert_awaited_once()
