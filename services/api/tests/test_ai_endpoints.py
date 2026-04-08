import httpx
import json
import respx
from fastapi.testclient import TestClient

from src.app import app
from src.config import settings


def test_ai_query_via_router():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "completed",
                    "workflow_id": "w1",
                    "workflow_name": "wrkhrs_chat",
                    "duration": 0.01,
                    "result": {"final_response": "ok"},
                },
            )
        )
        resp = client.post("/api/ai/query", json={"prompt": "hi", "use_router": True})
        assert resp.status_code == 200
        body = resp.json()
        assert body["workflow_name"] == "wrkhrs_chat"
        assert body["status"] in ("completed", "failed")


def test_ai_query_via_ai_stack():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "completed",
                    "workflow_id": "w2",
                    "workflow_name": "wrkhrs_chat",
                    "duration": 0.01,
                    "result": {"final_response": "ok"},
                },
            )
        )
        resp = client.post("/api/ai/query", json={"prompt": "hi", "use_router": False})
        assert resp.status_code == 200
        assert resp.json()["workflow_name"] == "wrkhrs_chat"


def test_ai_query_auto_promotes_complex_engineering_prompt():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "completed",
                    "workflow_id": "weng",
                    "workflow_name": "engineering_workflow",
                    "duration": 0.01,
                    "result": {
                        "final_response": "Engineering clarification required",
                        "clarification_questions": ["What system is in scope?"],
                    },
                },
            )
        )
        resp = client.post(
            "/api/ai/query",
            json={
                "prompt": "Design an engineering workflow that refactors multiple files and adds deterministic verification gates for the orchestrator.",
            },
        )
        assert resp.status_code == 200
        payload = json.loads(route.calls[0].request.content.decode("utf-8"))
        assert payload["workflow_name"] == "engineering_workflow"
        assert payload["workflow_config"]["strict_engineering"] is True


def test_workflows_code_rag_calls_router():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        # required MCP tool calls
        mock.post(f"{settings.router_url}/mcp/servers/github-mcp/call").mock(
            return_value=httpx.Response(200, json={"result": {"ok": True}})
        )
        mock.post(f"{settings.router_url}/mcp/servers/filesystem-mcp/call").mock(
            return_value=httpx.Response(200, json={"result": {"ok": True}})
        )
        mock.post(f"{settings.router_url}/mcp/servers/vector-db-mcp/call").mock(
            return_value=httpx.Response(200, json={"result": {"ok": True}})
        )
        route = mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "completed",
                    "workflow_id": "w3",
                    "workflow_name": "wrkhrs_chat",
                    "duration": 0.01,
                    "result": {"final_response": "ok"},
                },
            )
        )
        resp = client.post(
            "/api/ai/workflows/run",
            json={"name": "code-rag", "input": {"query": "test"}},
        )
        assert resp.status_code == 200
        # Assert prompt assembly contains the task card system prompt.
        payload = json.loads(route.calls[0].request.content.decode("utf-8"))
        assert payload["workflow_name"] == "wrkhrs_chat"
        messages = payload["input_data"]["messages"]
        assert messages[0]["role"] == "system"
        assert "Always cite sources" in messages[0]["content"]


def test_workflows_media_fixups_calls_router():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{settings.router_url}/mcp/servers/filesystem-mcp/call").mock(
            return_value=httpx.Response(200, json={"result": {"ok": True}})
        )
        route = mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "completed",
                    "workflow_id": "w4",
                    "workflow_name": "wrkhrs_chat",
                    "duration": 0.01,
                    "result": {"final_response": "ok"},
                },
            )
        )
        resp = client.post(
            "/api/ai/workflows/run",
            json={
                "name": "media-fixups",
                "input": {"file": "/mnt/appdata/addons/documents_processed/a.pdf"},
            },
        )
        assert resp.status_code == 200
        payload = json.loads(route.calls[0].request.content.decode("utf-8"))
        messages = payload["input_data"]["messages"]
        assert messages[0]["role"] == "system"
        assert "media and document fix-ups" in messages[0]["content"]


def test_workflows_sysadmin_ops_calls_router():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "completed",
                    "workflow_id": "w5",
                    "workflow_name": "wrkhrs_chat",
                    "duration": 0.01,
                    "result": {"final_response": "ok"},
                },
            )
        )
        resp = client.post(
            "/api/ai/workflows/run",
            json={"name": "sysadmin-ops", "input": {"task": "describe netplan"}},
        )
        assert resp.status_code == 200
        payload = json.loads(route.calls[0].request.content.decode("utf-8"))
        messages = payload["input_data"]["messages"]
        assert messages[0]["role"] == "system"
        assert "sysadmin assistant" in messages[0]["content"]


def test_simulations_analyze_calls_ai_stack():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "completed",
                    "workflow_id": "wsim",
                    "workflow_name": "wrkhrs_chat",
                    "duration": 0.01,
                    "result": {"final_response": "analysis"},
                },
            )
        )
        resp = client.post(
            "/api/ai/simulations/analyze",
            json={"payload": {"a": 1}, "instructions": "analyze"},
        )
        assert resp.status_code == 200
        assert resp.json()["workflow_name"] == "wrkhrs_chat"


def test_workflow_prompt_fallback_uses_query_or_prompt_keys():
    from src.routes.ai import _workflow_prompt_from_card

    assert _workflow_prompt_from_card("other-workflow", {"prompt": "p"}) == "p"
    assert _workflow_prompt_from_card("other-workflow", {"query": "q"}) == "q"
    assert _workflow_prompt_from_card("other-workflow", {}) == ""
