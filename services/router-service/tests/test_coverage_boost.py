from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from src.context_compaction import compact_tool_result_for_llm
from src.orchestrator_client import WrkHrsOrchestratorClient
from src.prompts import DEFAULT_SYSTEM_PROMPT, qwen_default_params
from src.workflow_engine import WorkflowEngine


def test_compact_tool_result_for_llm_evidence_and_sources() -> None:
    out = compact_tool_result_for_llm(
        "rag",
        "search",
        {
            "evidence": "Some evidence text.",
            "results": [
                {"source": "a.com"},
                {"metadata": {"source": "b.com"}},
                {"metadata": {"source": None}},
                "not-a-dict",
            ],
        },
    )
    assert out.startswith("Retrieved evidence:\n\nSome evidence text.")
    assert "Sources:" in out
    assert "a.com" in out
    assert "b.com" in out


def test_compact_tool_result_for_llm_dict_fallback_and_non_dict() -> None:
    out = compact_tool_result_for_llm("srv", "tool", {"k1": "v1", "k2": "v2"})
    assert out.startswith("Tool result from srv:tool:")
    out2 = compact_tool_result_for_llm("srv", "tool", ["x", "y"])
    assert out2.startswith("Tool result from srv:tool:")


def test_compact_tool_result_for_llm_summary_handles_non_jsonable() -> None:
    class _X:
        pass

    out = compact_tool_result_for_llm("srv", "tool", {"x": _X()})
    assert out.startswith("Tool result from srv:tool:")


def test_prompts_defaults_and_presets() -> None:
    assert "tools" in DEFAULT_SYSTEM_PROMPT.lower()

    general = qwen_default_params()
    coding = qwen_default_params("coding")
    unknown = qwen_default_params("does-not-exist")

    assert general["temperature"] == 1.0
    assert coding["temperature"] == 0.6
    assert unknown["temperature"] == 1.0

    # Ensure it is a copy (callers can mutate without global side effects)
    general["temperature"] = 0.0
    assert qwen_default_params()["temperature"] == 1.0


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = "error"

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "status error",
                request=httpx.Request("GET", "http://example"),
                response=httpx.Response(self.status_code, text=self.text),
            )

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeAsyncClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any]] = []

    async def get(self, path: str) -> _FakeResponse:
        self.calls.append(("GET", path, None))
        return _FakeResponse(200, {"status": "ok"})

    async def post(self, path: str, json: Any) -> _FakeResponse:
        self.calls.append(("POST", path, json))
        return _FakeResponse(200, {"status": "ok", "echo": json})

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_orchestrator_client_requires_context_manager() -> None:
    client = WrkHrsOrchestratorClient(base_url="http://example")
    with pytest.raises(RuntimeError):
        await client.health_check()


@pytest.mark.asyncio
async def test_orchestrator_client_health_and_execute_workflow_success() -> None:
    c = WrkHrsOrchestratorClient(base_url="http://example")
    c._client = _FakeAsyncClient()  # type: ignore[assignment]

    health = await c.health_check()
    assert health["status"] == "ok"

    result = await c.execute_workflow("w", {"a": 1}, workflow_config={"x": "y"})
    assert result["status"] == "ok"
    assert result["echo"]["workflow_name"] == "w"
    assert result["echo"]["input_data"] == {"a": 1}
    assert result["echo"]["workflow_config"] == {"x": "y"}


@pytest.mark.asyncio
async def test_orchestrator_client_http_error_is_raised() -> None:
    class _ErrClient(_FakeAsyncClient):
        async def get(self, path: str) -> _FakeResponse:  # type: ignore[override]
            return _FakeResponse(503)

    c = WrkHrsOrchestratorClient(base_url="http://example")
    c._client = _ErrClient()  # type: ignore[assignment]
    with pytest.raises(httpx.HTTPStatusError):
        await c.health_check()


@pytest.mark.asyncio
async def test_orchestrator_client_other_endpoints_and_wrappers() -> None:
    class _Client(_FakeAsyncClient):
        async def get(self, path: str) -> _FakeResponse:  # type: ignore[override]
            self.calls.append(("GET", path, None))
            if path == "/v1/workflows":
                return _FakeResponse(200, {"workflows": ["a", "b"]})
            if path == "/v1/workflows/w/schema":
                return _FakeResponse(200, {"name": "w"})
            if path == "/v1/workflows/abc/status":
                return _FakeResponse(200, {"id": "abc", "status": "running"})
            return _FakeResponse(404)

        async def post(  # type: ignore[override]
            self, path: str, json: Any | None = None
        ) -> _FakeResponse:
            self.calls.append(("POST", path, json))
            if path == "/v1/workflows/abc/cancel":
                return _FakeResponse(200, {"id": "abc", "status": "cancelled"})
            return _FakeResponse(200, {"ok": True, "path": path, "payload": json})

    c = WrkHrsOrchestratorClient(base_url="http://example")
    c._client = _Client()  # type: ignore[assignment]

    assert (await c.get_available_workflows())["workflows"] == ["a", "b"]
    assert (await c.get_workflow_schema("w"))["name"] == "w"

    # Wrapper helpers (exercise payload shaping)
    rag = await c.execute_rag_workflow(
        "q", domain_weights={"chem": 0.5}, top_k=1, min_score=0.1
    )
    assert rag["payload"]["workflow_name"] == "rag_retrieval"
    assert rag["payload"]["input_data"]["query"] == "q"
    assert rag["payload"]["input_data"]["domain_weights"] == {"chem": 0.5}

    tool = await c.execute_tool_workflow("t", ["a"], tool_args={"a": {"x": 1}})
    assert tool["payload"]["workflow_name"] == "tool_execution"
    assert tool["payload"]["input_data"]["tool_args"] == {"a": {"x": 1}}

    gh = await c.execute_github_workflow("p", repository="r", project="p1")
    assert gh["payload"]["workflow_name"] == "github_integration"
    assert gh["payload"]["input_data"]["repository"] == "r"

    pol = await c.execute_policy_workflow("c", ["units"], policy_config={"x": 1})
    assert pol["payload"]["workflow_name"] == "policy_validation"
    assert pol["payload"]["input_data"]["policy_config"] == {"x": 1}

    status = await c.get_workflow_status("abc")
    assert status["status"] == "running"
    cancelled = await c.cancel_workflow("abc")
    assert cancelled["status"] == "cancelled"


@pytest.mark.asyncio
async def test_orchestrator_client_execute_workflow_http_status_error_path() -> None:
    class _BadClient(_FakeAsyncClient):
        async def post(self, path: str, json: Any) -> _FakeResponse:  # type: ignore[override]
            self.calls.append(("POST", path, json))
            return _FakeResponse(500)

    c = WrkHrsOrchestratorClient(base_url="http://example")
    c._client = _BadClient()  # type: ignore[assignment]
    with pytest.raises(httpx.HTTPStatusError):
        await c.execute_workflow("w", {"a": 1})


@pytest.mark.asyncio
async def test_orchestrator_client_aenter_aexit_uses_httpx_async_client(
    monkeypatch,
) -> None:
    class _CtxClient(_FakeAsyncClient):
        def __init__(self, base_url: str, timeout: float) -> None:  # noqa: ARG002
            super().__init__()

    monkeypatch.setattr("src.orchestrator_client.AsyncClient", _CtxClient)
    async with WrkHrsOrchestratorClient(base_url="http://example") as c:
        assert c._client is not None
    assert c._client is not None


class _Workflow:
    def __init__(
        self, result: Any | None = None, raises: Exception | None = None
    ) -> None:
        self._result = result
        self._raises = raises
        self.nodes = {"a": object()}
        self.edges = {"a->b": object()}

    async def ainvoke(
        self, input_data: dict[str, Any], config: dict[str, Any] | None = None
    ) -> Any:
        if self._raises:
            raise self._raises
        return {"input": input_data, "config": config, "result": self._result}


class _Chain:
    input_keys = ["x"]
    output_keys = ["y"]

    def __init__(self, raises: Exception | None = None) -> None:
        self._raises = raises

    async def ainvoke(self, input_data: dict[str, Any]) -> Any:
        if self._raises:
            raise self._raises
        return {"ok": True, "input": input_data}


@pytest.mark.asyncio
async def test_workflow_engine_workflow_and_chain_execution_paths() -> None:
    eng = WorkflowEngine()

    with pytest.raises(ValueError):
        await eng.execute_workflow("missing", {})

    eng.register_workflow("w", _Workflow(result=123))
    ok = await eng.execute_workflow("w", {"q": "x"}, config={"cfg": 1})
    assert ok["status"] == "completed"
    assert ok["workflow"] == "w"

    eng.register_workflow("boom", _Workflow(raises=RuntimeError("nope")))
    failed = await eng.execute_workflow("boom", {"q": "x"})
    assert failed["status"] == "failed"
    assert failed["workflow"] == "boom"

    with pytest.raises(ValueError):
        await eng.execute_chain("missing", {})

    eng.register_chain("c", _Chain())
    c_ok = await eng.execute_chain("c", {"x": 1})
    assert c_ok["status"] == "completed"

    eng.register_chain("c_boom", _Chain(raises=ValueError("bad")))
    c_failed = await eng.execute_chain("c_boom", {"x": 1})
    assert c_failed["status"] == "failed"


@pytest.mark.asyncio
async def test_workflow_engine_tool_execution_sync_and_async() -> None:
    eng = WorkflowEngine()

    with pytest.raises(ValueError):
        await eng.execute_tool("missing", "x")

    def sync_func(inp: Any) -> Any:
        return {"sync": True, "inp": inp}

    async def async_func(inp: Any) -> Any:
        return {"async": True, "inp": inp}

    sync_tool = SimpleNamespace(func=sync_func, description="d", args_schema=None)
    async_tool = SimpleNamespace(func=async_func, description="d", args_schema=None)

    eng.register_tool("t_sync", sync_tool)
    eng.register_tool("t_async", async_tool)

    r1 = await eng.execute_tool("t_sync", {"a": 1})
    assert r1["status"] == "completed"
    assert r1["result"]["sync"] is True

    r2 = await eng.execute_tool("t_async", "hi")
    assert r2["status"] == "completed"
    assert r2["result"]["async"] is True

    def boom(_: Any) -> Any:
        raise RuntimeError("nope")

    eng.register_tool(
        "t_boom", SimpleNamespace(func=boom, description="d", args_schema=None)
    )
    r3 = await eng.execute_tool("t_boom", "x")
    assert r3["status"] == "failed"


def test_workflow_engine_introspection_helpers() -> None:
    eng = WorkflowEngine()
    eng.register_workflow("w", _Workflow(result=1))
    eng.register_chain("c", _Chain())
    eng.register_tool(
        "t", SimpleNamespace(func=lambda x: x, description="d", args_schema=None)
    )

    assert eng.get_available_workflows() == ["w"]
    assert eng.get_available_chains() == ["c"]
    assert eng.get_available_tools() == ["t"]

    info_w = eng.get_workflow_info("w")
    assert info_w["nodes"] == ["a"]
    assert info_w["edges"] == ["a->b"]

    info_c = eng.get_chain_info("c")
    assert info_c["name"] == "c"
    assert info_c["input_keys"] == ["x"]
    assert info_c["output_keys"] == ["y"]

    info_t = eng.get_tool_info("t")
    assert info_t["name"] == "t"
    assert info_t["description"] == "d"
