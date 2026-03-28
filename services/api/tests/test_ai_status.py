import httpx
import respx
from fastapi.testclient import TestClient

from src.app import app
from src.config import settings


def test_ai_status_aggregates_ok(setup_clients):
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{settings.router_url}/health").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "healthy",
                    "services": {"api": "healthy"},
                    "mcp_servers": {"filesystem-mcp": True, "github-mcp": True},
                },
            )
        )
        mock.get(f"{settings.ai_stack_url}/health").mock(
            return_value=httpx.Response(200, json={"status": "ok", "openai_base_url": "http://worker/v1"})
        )

        resp = client.get("/api/ai/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded")
        assert "router" in data and "ai_stack" in data and "worker" in data
        assert "qwen" in data and "rag" in data and "asr" in data
        assert "reachable" in data["qwen"] and "model_name" in data["qwen"] and "latency_ms" in data["qwen"]

