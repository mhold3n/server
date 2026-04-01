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
        mock.post(f"{settings.router_url}/route").mock(
            return_value=httpx.Response(500, text="router error")
        )
        resp = client.post("/api/ai/query", json={"prompt": "fail", "use_router": True})
        assert resp.status_code == 500


def test_ai_query_ai_stack_500_propagates_when_not_using_router():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{settings.ai_stack_url}/llm/prompt").mock(
            return_value=httpx.Response(500, text="stack err")
        )
        resp = client.post(
            "/api/ai/query",
            json={"prompt": "fail", "use_router": False},
        )
        assert resp.status_code == 500


def test_workflows_unknown_fails():
    client = TestClient(app)
    resp = client.post("/api/ai/workflows/run", json={"name": "unknown", "input": {}})
    assert resp.status_code == 400


def test_simulations_ai_stack_500_propagates():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{settings.ai_stack_url}/llm/prompt").mock(
            return_value=httpx.Response(500, text="stack error")
        )
        resp = client.post("/api/ai/simulations/analyze", json={"payload": {}})
        assert resp.status_code == 500
