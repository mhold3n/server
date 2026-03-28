import httpx
import respx
from fastapi.testclient import TestClient

from src.app import app
from src.config import settings


def test_ai_query_via_router():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{settings.router_url}/route").mock(
            return_value=httpx.Response(
                200,
                json={"task_id": "t1", "status": "completed", "result": {"ok": True}},
            )
        )
        resp = client.post("/api/ai/query", json={"prompt": "hi", "use_router": True})
        assert resp.status_code == 200
        assert resp.json()["status"] in ("completed", "failed") or resp.json().get("ok")


def test_ai_query_via_ai_stack():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{settings.ai_stack_url}/llm/prompt").mock(
            return_value=httpx.Response(200, json={"model": "test", "output": "ok"})
        )
        resp = client.post("/api/ai/query", json={"prompt": "hi", "use_router": False})
        assert resp.status_code == 200
        assert resp.json()["output"] == "ok"


def test_workflows_code_rag_calls_router():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{settings.router_url}/route").mock(
            return_value=httpx.Response(
                200, json={"task_id": "t2", "status": "completed"}
            )
        )
        resp = client.post(
            "/api/ai/workflows/run",
            json={"name": "code-rag", "input": {"query": "test"}},
        )
        assert resp.status_code == 200


def test_workflows_media_fixups_calls_router():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{settings.router_url}/route").mock(
            return_value=httpx.Response(
                200, json={"task_id": "t3", "status": "completed"}
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


def test_workflows_sysadmin_ops_calls_router():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{settings.router_url}/route").mock(
            return_value=httpx.Response(
                200, json={"task_id": "t4", "status": "completed"}
            )
        )
        resp = client.post(
            "/api/ai/workflows/run",
            json={"name": "sysadmin-ops", "input": {"task": "describe netplan"}},
        )
        assert resp.status_code == 200


def test_simulations_analyze_calls_ai_stack():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{settings.ai_stack_url}/llm/prompt").mock(
            return_value=httpx.Response(200, json={"output": "analysis"})
        )
        resp = client.post(
            "/api/ai/simulations/analyze",
            json={"payload": {"a": 1}, "instructions": "analyze"},
        )
        assert resp.status_code == 200
        assert resp.json()["output"] == "analysis"
