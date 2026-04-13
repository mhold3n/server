import httpx
import respx
from fastapi.testclient import TestClient

from src.app import app
from src.config import settings


def test_ai_query_requires_prompt_or_messages():
    client = TestClient(app)
    resp = client.post("/api/ai/query", json={})
    assert resp.status_code == 400


def test_ai_query_router_500_propagates():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(500, text="orchestrator error")
        )
        resp = client.post("/api/ai/query", json={"prompt": "fail", "use_router": True})
        assert resp.status_code == 502


def test_ai_query_ai_stack_500_propagates_when_not_using_router():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(500, text="orchestrator error")
        )
        resp = client.post(
            "/api/ai/query",
            json={"prompt": "fail", "use_router": False},
        )
        assert resp.status_code == 502


def test_workflows_unknown_fails():
    client = TestClient(app)
    resp = client.post("/api/ai/workflows/run", json={"name": "unknown", "input": {}})
    assert resp.status_code == 400


def test_simulations_ai_stack_500_propagates():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(500, text="orchestrator error")
        )
        resp = client.post("/api/ai/simulations/analyze", json={"payload": {}})
        assert resp.status_code == 502


def test_ai_query_required_tool_spec_must_include_server_prefix():
    client = TestClient(app)
    resp = client.post(
        "/api/ai/query",
        json={
            "prompt": "hi",
            "tools": ["not-a-tool-spec"],
        },
    )
    assert resp.status_code == 502


def test_ai_query_required_tool_non_dict_response_fails_closed():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{settings.router_url}/mcp/servers/github-mcp/call").mock(
            return_value=httpx.Response(200, json=[1, 2, 3]),
        )
        resp = client.post(
            "/api/ai/query",
            json={
                "prompt": "hi",
                "tools": ["github-mcp:search"],
            },
        )
    assert resp.status_code == 502


def test_ai_query_required_tool_args_override_is_applied():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mcp = mock.post(f"{settings.router_url}/mcp/servers/github-mcp/call").mock(
            return_value=httpx.Response(200, json={"result": {"ok": True}}),
        )
        mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "completed",
                    "workflow_id": "wq",
                    "workflow_name": "wrkhrs_chat",
                    "duration": 0.01,
                    "result": {"final_response": "ok"},
                },
            )
        )
        resp = client.post(
            "/api/ai/query",
            json={
                "prompt": "hi",
                "tools": ["github-mcp:search"],
                "tool_args": {"github-mcp:search": {"query": "override"}},
            },
        )
        assert resp.status_code == 200
        import json as _json

        sent = _json.loads(mcp.calls[0].request.content.decode("utf-8"))
        assert sent["arguments"]["query"] == "override"
