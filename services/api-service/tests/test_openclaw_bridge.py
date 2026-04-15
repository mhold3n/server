"""Unit tests for OpenClaw bridge envelope validation and idempotency helpers."""

from __future__ import annotations

import base64
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.openclaw_bridge import (
    OpenClawBridgeValidationError,
    idempotency_payload_hash,
    resolve_idempotency_lookup,
    validate_openclaw_bridge_in_context,
)
from src.routes.ai import QueryRequest


def _minimal_bridge(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "bridge": {"proto": "birtha.openclaw", "version": "1.0.0"},
        "session_key": "sess-1",
        "channel": "test",
        "sender": "user-1",
        "idempotency_key": "idem-key-12345678",
        "attachments": [],
        "client_capabilities": {},
    }
    base.update(overrides)
    return base


def test_validate_openclaw_bridge_ok() -> None:
    ctx = {"openclaw_bridge": _minimal_bridge()}
    out = validate_openclaw_bridge_in_context(ctx)
    assert out["session_key"] == "sess-1"


def test_validate_openclaw_bridge_rejects_wrong_proto() -> None:
    ctx = {"openclaw_bridge": _minimal_bridge(bridge={"proto": "wrong", "version": "1.0.0"})}
    with pytest.raises(OpenClawBridgeValidationError) as ei:
        validate_openclaw_bridge_in_context(ctx)
    assert ei.value.code == "openclaw_bridge_schema"


def test_validate_openclaw_bridge_inline_size_cap() -> None:
    big = base64.b64encode(b"x" * 70000).decode("ascii")
    ctx = {
        "openclaw_bridge": _minimal_bridge(
            attachments=[
                {
                    "kind": "inline_base64",
                    "media_type": "text/plain",
                    "data": big,
                }
            ]
        )
    }
    with pytest.raises(OpenClawBridgeValidationError) as ei:
        validate_openclaw_bridge_in_context(ctx)
    assert ei.value.code == "attachment_inline_too_large"


def test_idempotency_payload_hash_stable() -> None:
    req = QueryRequest(
        prompt="hi",
        context={"openclaw_bridge": _minimal_bridge()},
    )
    a = idempotency_payload_hash(req)
    b = idempotency_payload_hash(req)
    assert a == b and len(a) == 64


def test_resolve_idempotency_lookup_conflict() -> None:
    assert resolve_idempotency_lookup({"payload_hash": "a", "response": {}}, "b") == "conflict"


def test_resolve_idempotency_lookup_hit() -> None:
    r = {"ok": True}
    out = resolve_idempotency_lookup({"payload_hash": "x", "response": r}, "x")
    assert out == r


class _FakeRedis:
    """Minimal async Redis stub for idempotency tests."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def setex(self, key: str, _ttl: int, value: str) -> None:
        self.store[key] = value


@pytest.fixture
def fake_redis() -> _FakeRedis:
    return _FakeRedis()


def test_ai_query_openclaw_bridge_idempotency_hit(fake_redis: _FakeRedis) -> None:
    bridge = _minimal_bridge(idempotency_key="idem-integration-123456")
    cached = {"result": {"final_response": "cached"}}
    payload_hash = idempotency_payload_hash(
        QueryRequest(prompt="same", context={"openclaw_bridge": bridge})
    )
    key = f"birtha:openclaw-bridge:v1:idempotency:{bridge['idempotency_key']}"
    fake_redis.store[key] = json.dumps({"payload_hash": payload_hash, "response": cached})

    execute = AsyncMock(return_value={"result": {"final_response": "fresh"}})
    inner = MagicMock()
    inner.execute_workflow = execute
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=inner)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("src.routes.ai.OrchestratorClient", return_value=mock_cm):
        with patch("src.app.redis_client", fake_redis):
            client = TestClient(app)
            r = client.post(
                "/api/ai/query",
                json={
                    "prompt": "same",
                    "context": {"openclaw_bridge": bridge},
                },
            )
    assert r.status_code == 200
    assert r.json() == cached
    execute.assert_not_called()


def test_ai_query_openclaw_bridge_idempotency_conflict(fake_redis: _FakeRedis) -> None:
    bridge = _minimal_bridge(idempotency_key="idem-conflict-12345678")
    payload_hash = idempotency_payload_hash(
        QueryRequest(prompt="original", context={"openclaw_bridge": bridge})
    )
    key = f"birtha:openclaw-bridge:v1:idempotency:{bridge['idempotency_key']}"
    fake_redis.store[key] = json.dumps({"payload_hash": payload_hash, "response": {}})

    execute = AsyncMock(return_value={"result": {"final_response": "x"}})
    inner = MagicMock()
    inner.execute_workflow = execute
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=inner)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("src.routes.ai.OrchestratorClient", return_value=mock_cm):
        with patch("src.app.redis_client", fake_redis):
            client = TestClient(app)
            r = client.post(
                "/api/ai/query",
                json={
                    "prompt": "changed-payload",
                    "context": {"openclaw_bridge": bridge},
                },
            )
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "idempotency_key_conflict"
    execute.assert_not_called()
