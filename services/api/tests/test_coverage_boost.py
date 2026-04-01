from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.clients.search import meili_search
from src.config import Settings, get_worker_settings
from src.observability.context import RequestContextMiddleware
from src.policies.citations import CitationPolicy
from src.policies.middleware import PolicyEnforcer
from src.policies.units import SIUnitPolicy
from src.routes.search import search_files, search_web
from src.routes.torrents import AddTorrentRequest, add_torrents
from src.routes.vms import list_vms, start_vm, stop_vm
from src.workflows import build_tool_args_for_card, list_task_cards


def test_settings_debug_fills_secrets() -> None:
    s = Settings(debug=True, jwt_secret=None, encryption_key=None)
    assert s.jwt_secret == "dev-secret-key"
    assert s.encryption_key == "dev-encryption-key-32-chars"


def test_get_worker_settings_string_profile_fallbacks() -> None:
    # `Settings` validates `orch_profile` strictly; exercise the fallback logic
    # in `get_worker_settings()` with a lightweight object.
    cfg = SimpleNamespace(
        orch_profile="not-a-real-profile", openai_base_url="http://x/v1"
    )
    ws = get_worker_settings(cfg)  # type: ignore[arg-type]
    assert ws.base_url == "http://x/v1"
    assert ws.default_model


def test_get_worker_settings_apple_profile_uses_default_base_url() -> None:
    cfg = SimpleNamespace(orch_profile="apple", openai_base_url="")
    ws = get_worker_settings(cfg)  # type: ignore[arg-type]
    assert ws.base_url.endswith("/v1")
    assert "host.docker.internal" in ws.base_url


def test_get_worker_settings_accepts_string_enum_values() -> None:
    cfg = SimpleNamespace(orch_profile="GPU", openai_base_url="http://x/v1")
    ws = get_worker_settings(cfg)  # type: ignore[arg-type]
    assert ws.base_url == "http://x/v1"


@pytest.mark.asyncio
async def test_meili_search_includes_api_key_header(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class _Resp:
        def raise_for_status(self) -> None:  # noqa: D401
            return None

        def json(self) -> dict[str, Any]:
            return {"hits": []}

    class _Client:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, D401
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
            return None

        async def post(self, url, json, headers):  # noqa: ANN001
            captured["headers"] = headers
            return _Resp()

    import src.clients.search as search_mod  # noqa: WPS433

    monkeypatch.setattr(search_mod.httpx, "AsyncClient", _Client)
    await meili_search("http://meili", api_key="k", index="i", query="q")
    assert captured["headers"]["X-Meili-API-Key"] == "k"


def test_citations_distribution_score_multi_paragraph() -> None:
    policy = CitationPolicy(min_citations=1)
    text = "Para one [1].\n\nPara two [2]."
    analysis = policy._analyze_citations(text)  # noqa: SLF001
    score = policy._calculate_distribution_score(text, analysis)  # noqa: SLF001
    assert 0.0 <= score <= 1.0


def test_citations_distribution_score_zero_when_no_citations() -> None:
    policy = CitationPolicy(min_citations=1)
    text = "No citations here."
    analysis = policy._analyze_citations(text)  # noqa: SLF001
    assert policy._calculate_distribution_score(text, analysis) == 0.0  # noqa: SLF001


def test_citations_claim_supported_by_retrieval() -> None:
    policy = CitationPolicy(min_citations=1)
    claim = "Quantum computing uses qubits for computation."
    retrieval = [
        {"content": "Quantum computing uses qubits and superposition.", "metadata": {}}
    ]
    assert policy._is_claim_supported(claim, retrieval) is True  # noqa: SLF001


def test_units_policy_should_have_unit_context_indicator() -> None:
    policy = SIUnitPolicy()
    text = "The pressure 101.3 is measured at sea level."
    # Value has no unit, and context contains a unit indicator ("pressure"),
    # so the helper should flag it.
    assert policy._should_have_unit(
        101.3, unit="", position=text.index("101.3"), text=text
    )  # noqa: SLF001


def test_units_policy_should_not_require_unit_for_small_ratio() -> None:
    policy = SIUnitPolicy()
    text = "The ratio 0.5 is dimensionless."
    assert (
        policy._should_have_unit(0.5, unit="", position=text.index("0.5"), text=text)
        is False
    )  # noqa: SLF001


def test_units_policy_should_not_require_unit_for_small_count() -> None:
    policy = SIUnitPolicy()
    text = "We observed 42 samples."
    assert (
        policy._should_have_unit(42.0, unit="", position=text.index("42"), text=text)
        is False
    )  # noqa: SLF001


@pytest.mark.asyncio
async def test_search_files_success(monkeypatch) -> None:
    async def _fake_meili_search(**kwargs):  # noqa: ANN003
        return [{"id": "1"}]

    import src.routes.search as search_routes  # noqa: WPS433

    monkeypatch.setattr(search_routes, "meili_search", _fake_meili_search)
    result = await search_files(q="hello", limit=5)
    assert result["items"] == [{"id": "1"}]


@pytest.mark.asyncio
async def test_search_web_success(monkeypatch) -> None:
    async def _fake_searx_search(*args, **kwargs):  # noqa: ANN003
        return [{"url": "https://example.com"}]

    import src.routes.search as search_routes  # noqa: WPS433

    monkeypatch.setattr(search_routes, "searx_search", _fake_searx_search)
    result = await search_web(q="hello", limit=5)
    assert result["items"] == [{"url": "https://example.com"}]


def test_list_task_cards_and_build_tool_args() -> None:
    cards = list_task_cards()
    assert cards
    args = build_tool_args_for_card(
        "code-rag",
        {"query": "x", "path": "/tmp"},
        ai_repos="https://example.com/repo",
        marker_processed_dir="/processed",
    )
    assert "github-mcp:search" in args


@pytest.mark.asyncio
async def test_add_torrents_requires_urls() -> None:
    with pytest.raises(HTTPException) as exc:
        await add_torrents(AddTorrentRequest(urls=[]))
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_vms_endpoints_require_credentials(monkeypatch) -> None:
    import src.routes.vms as vms_routes  # noqa: WPS433

    monkeypatch.setattr(vms_routes.settings, "proxmox_token_id", None, raising=False)
    monkeypatch.setattr(
        vms_routes.settings, "proxmox_token_secret", None, raising=False
    )

    with pytest.raises(HTTPException) as exc1:
        await list_vms()
    assert exc1.value.status_code == 501

    with pytest.raises(HTTPException) as exc2:
        await start_vm(123)
    assert exc2.value.status_code == 501

    with pytest.raises(HTTPException) as exc3:
        await stop_vm(123)
    assert exc3.value.status_code == 501


@pytest.mark.asyncio
async def test_stop_vm_value_error_maps_to_404(monkeypatch) -> None:
    import src.routes.vms as vms_routes  # noqa: WPS433

    monkeypatch.setattr(vms_routes.settings, "proxmox_token_id", "t", raising=False)
    monkeypatch.setattr(vms_routes.settings, "proxmox_token_secret", "s", raising=False)

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
            return None

        async def stop_vm(self, vmid: int):  # noqa: ARG002
            raise ValueError("not found")

    monkeypatch.setattr(vms_routes, "_pmx_client", lambda: _Client())

    with pytest.raises(HTTPException) as exc:
        await stop_vm(999)
    assert exc.value.status_code == 404


def test_request_context_middleware_sets_span_attributes() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"ok": "1"}

    mock_span = Mock()
    mock_span.is_recording.return_value = True

    # Patch the module-level trace getter used by middleware.
    from src.observability import context as ctx  # noqa: WPS433

    ctx.trace.get_current_span = Mock(return_value=mock_span)  # type: ignore[method-assign]

    client = TestClient(app)
    r = client.get(
        "/ping", headers={"x-trace-id": "t", "x-run-id": "r", "x-policy-set": "p"}
    )
    assert r.status_code == 200
    assert r.headers["x-trace-id"] == "t"
    assert r.headers["x-run-id"] == "r"
    assert r.headers["x-policy-set"] == "p"
    mock_span.set_attribute.assert_any_call("app.trace_id", "t")
    mock_span.set_attribute.assert_any_call("app.run_id", "r")
    mock_span.set_attribute.assert_any_call("app.policy_set", "p")


@pytest.mark.asyncio
async def test_policy_enforcer_handles_missing_and_exception_policies(
    monkeypatch,
) -> None:
    enforcer = PolicyEnforcer()

    class BoomPolicy:
        async def validate(
            self, output: str, retrieval_set: list[dict[str, Any]]
        ):  # noqa: ARG002
            raise RuntimeError("boom")

    monkeypatch.setattr(
        enforcer.registry,
        "get_enabled_policies",
        Mock(return_value=["missing", "boom"]),
    )
    monkeypatch.setattr(
        enforcer.registry,
        "get_policy",
        Mock(side_effect=lambda name: None if name == "missing" else BoomPolicy()),
    )

    verdict = await enforcer.validate("ok", retrieval_docs=None)
    assert verdict.overall_passed is False
    assert "boom" in verdict.policy_results
    assert verdict.policy_results["boom"].passed is False
    assert verdict.policy_results["boom"].violations
