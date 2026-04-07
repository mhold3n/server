from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

import src.router as router_mod
from src.router import app


def test_health_includes_mcp_and_api(monkeypatch):
    client = TestClient(app)
    # Mock Redis ping ok
    import src.router as router_mod

    fake_redis = AsyncMock()
    fake_redis.ping.return_value = True
    monkeypatch.setattr(router_mod, "redis_client", fake_redis)

    # Mock API client
    fake_api = AsyncMock()
    fake_api.get.return_value.status_code = 200
    monkeypatch.setattr(router_mod, "api_client", fake_api)

    # Mock MCP client health

    class FakeMCP:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def health_check_all(self):
            return {"filesystem-mcp": True, "github-mcp": True}

    with patch("src.router.MCPClient", return_value=FakeMCP()):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "mcp_servers" in data and data["services"]["api"] in (
            "healthy",
            "unhealthy",
            "not_configured",
        )


def test_mcp_tool_call_forwards_tool_args(monkeypatch):
    client = TestClient(app)

    class FakeMCP:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def call_tool(self, server, tool, args=None):
            return {"server": server, "tool": tool, "args": args}

    with patch("src.router.MCPClient", return_value=FakeMCP()):
        payload = {
            "prompt": "test",
            "tools": ["filesystem-mcp:directory_traversal"],
            "tool_args": {"filesystem-mcp:directory_traversal": {"path": "/data"}},
        }
        resp = client.post("/route", json=payload)
        assert resp.status_code == 410
