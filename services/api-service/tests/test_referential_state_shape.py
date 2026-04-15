"""Contract tests: ``result.referential_state`` is always a JSON object when present (bridge Phase 2.6).

For agents: the OpenClaw mirror and engineering clients assume ``referential_state`` is a
mapping, never a scalar or array at the top level of ``result``.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from src.main import app


def _assert_referential_state_object_if_present(payload: dict[str, Any]) -> None:
    inner = payload.get("result", payload)
    if not isinstance(inner, dict):
        return
    if "referential_state" in inner:
        assert isinstance(inner["referential_state"], dict), inner


def test_contract_samples_referential_state_must_be_dict_when_key_present() -> None:
    """Sanity: contract helper rejects invalid shapes (documents expected API behavior)."""
    _assert_referential_state_object_if_present({"result": {"referential_state": {}, "final_response": "ok"}})
    _assert_referential_state_object_if_present(
        {"result": {"referential_state": {"engineering_session_id": "s1"}, "final_response": "ok"}}
    )
    with pytest.raises(AssertionError):
        _assert_referential_state_object_if_present({"result": {"referential_state": "not-a-dict"}})


def test_ai_query_response_when_pipeline_returns_referential_state_dict() -> None:
    """When the pipeline returns ``result.referential_state`` as a dict, ``/api/ai/query`` preserves it."""
    out = {
        "result": {
            "final_response": "mocked",
            "referential_state": {"task_id": "t-1", "run_id": "r-1"},
        }
    }
    mock_pipe = AsyncMock(return_value=out)
    inner = MagicMock()
    inner.execute_workflow = AsyncMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=inner)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("src.routes.ai.execute_ai_query_pipeline", mock_pipe):
        with patch("src.app.redis_client", None):
            client = TestClient(app)
            r = client.post("/api/ai/query", json={"prompt": "hello"})
    assert r.status_code == 200, r.text
    _assert_referential_state_object_if_present(r.json())
