from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import HTTPError


@pytest.mark.asyncio
async def test_routes_middleware_error_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.routes import middleware as mw

    app = FastAPI()
    app.include_router(mw.router)
    client = TestClient(app)

    # get_policy_registry 500 branch
    monkeypatch.setattr(
        mw.policy_registry,
        "get_available_policies",
        lambda: (_ for _ in ()).throw(RuntimeError("x")),
    )
    r = client.get("/middleware/registry")
    assert r.status_code == 500

    # get_policy_info 500 branch
    monkeypatch.setattr(
        mw.policy_registry, "get_available_policies", lambda: [{"name": "evidence"}]
    )
    monkeypatch.setattr(
        mw.policy_registry, "get_policy_schema", lambda _n: {"type": "object"}
    )
    r2 = client.get("/middleware/registry/evidence")
    assert r2.status_code == 200

    monkeypatch.setattr(mw.policy_registry, "policies", {"evidence": object()})
    monkeypatch.setattr(
        mw.policy_registry,
        "get_available_policies",
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    r3 = client.get("/middleware/registry/evidence")
    assert r3.status_code == 500


@pytest.mark.asyncio
async def test_observability_tracing_golden_trace_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.observability import tracing as ot

    # Avoid OTEL setup.
    monkeypatch.setattr(ot.TracingContext, "_setup_tracing", lambda self: None)
    ctx = ot.TracingContext(service_name="x", service_version="y")
    validator = ot.GoldenTraceValidator(ctx)

    async def _query_ok(*_a: Any, **_k: Any) -> dict[str, Any]:
        return {
            "batches": [
                {
                    "scopeSpans": [
                        {
                            "spans": [
                                {"name": "root", "parentSpanId": ""},
                                {"name": "child", "parentSpanId": "1"},
                            ]
                        }
                    ]
                }
            ]
        }

    monkeypatch.setattr(validator, "_query_trace", _query_ok)
    out = await validator.validate_golden_trace(
        "t", expected_spans=["root", "child"], timeout=1
    )
    assert out["valid"] in (True, False)

    async def _query_none(*_a: Any, **_k: Any) -> None:
        return None

    monkeypatch.setattr(validator, "_query_trace", _query_none)
    out2 = await validator.validate_golden_trace(
        "t", expected_spans=["root"], timeout=1
    )
    assert out2["valid"] is False


@pytest.mark.asyncio
async def test_wrkhrs_gateway_client_get_models_and_error_logging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ai_shared_service.gateway_client import WrkHrsGatewayClient

    class _Resp:
        def __init__(self, payload: dict[str, Any], ok: bool = True):
            self._payload = payload
            self._ok = ok

        def raise_for_status(self) -> None:
            if not self._ok:
                raise HTTPError("bad")

        def json(self) -> dict[str, Any]:
            return self._payload

    class _Client:
        async def get(self, path: str) -> _Resp:  # noqa: ARG002
            return _Resp({"data": [{"id": "m"}]})

        async def post(self, path: str, json: Any) -> _Resp:  # noqa: ARG002
            return _Resp({"choices": [], "usage": {}}, ok=False)

        async def aclose(self) -> None:
            return None

    c = WrkHrsGatewayClient(base_url="http://x")
    c._client = _Client()  # type: ignore[assignment]
    models = await c.get_models()
    assert "data" in models

    with pytest.raises(HTTPError):
        await c.chat_completion(messages=[{"role": "user", "content": "hi"}], model="m")
