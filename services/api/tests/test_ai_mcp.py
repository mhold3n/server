from unittest.mock import AsyncMock

import httpx
import respx
from fastapi.testclient import TestClient

import src.app as app_mod
from src.app import app


def test_mcp_servers_list_uses_toggle(setup_clients):
    client = TestClient(app)
    # Startup may overwrite redis_client; ensure we set it to a mock now
    app_mod.redis_client = AsyncMock()
    app_mod.redis_client.smembers.return_value = {"filesystem-mcp"}

    with respx.mock(assert_all_called=True) as mock:
        mock.get("http://router:8000/mcp/servers").mock(
            return_value=httpx.Response(
                200,
                json={
                    "servers": [
                        {"name": "filesystem-mcp", "type": "http", "url": "http://mcp-filesystem:7001"},
                        {"name": "github-mcp", "type": "http", "url": "http://mcp-github:7000"},
                    ]
                },
            )
        )
        resp = client.get("/api/ai/mcp/servers")
        assert resp.status_code == 200
        items = resp.json()["servers"]
        by_name = {s["name"]: s for s in items}
        assert by_name["filesystem-mcp"]["enabled"] is False
        assert by_name["github-mcp"]["enabled"] is True


def test_mcp_toggle_enable_disable(setup_clients):
    client = TestClient(app)
    assert isinstance(app_mod.redis_client, AsyncMock)

    resp = client.post("/api/ai/mcp/servers/github-mcp/enable", json={"enabled": False})
    assert resp.status_code == 200
    app_mod.redis_client.sadd.assert_awaited_with("mcp:disabled", "github-mcp")

    resp = client.post("/api/ai/mcp/servers/github-mcp/enable", json={"enabled": True})
    assert resp.status_code == 200
    app_mod.redis_client.srem.assert_awaited_with("mcp:disabled", "github-mcp")


def test_mcp_tools_and_call_respects_toggle(setup_clients):
    client = TestClient(app)
    assert isinstance(app_mod.redis_client, AsyncMock)
    # Disable filesystem-mcp
    app_mod.redis_client.smembers.return_value = {"filesystem-mcp"}

    # Tools pass-through
    with respx.mock() as mock:
        mock.get("http://router:8000/mcp/servers/github-mcp/tools").mock(
            return_value=httpx.Response(200, json={"tools": [{"name": "search"}]})
        )
        resp = client.get("/api/ai/mcp/servers/github-mcp/tools")
        assert resp.status_code == 200
        assert resp.json()["tools"][0]["name"] == "search"

    # Call blocked for disabled server
    resp = client.post(
        "/api/ai/mcp/call",
        json={"server": "filesystem-mcp", "tool": "directory_traversal", "arguments": {"path": "/"}},
    )
    assert resp.status_code == 403

    # Call allowed for enabled server
    app_mod.redis_client.smembers.return_value = set()
    with respx.mock(assert_all_called=True) as mock:
        mock.post("http://router:8000/mcp/servers/github-mcp/call").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        resp = client.post(
            "/api/ai/mcp/call",
            json={"server": "github-mcp", "tool": "search", "arguments": {"query": "test"}},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


def test_mcp_servers_no_redis_marks_enabled(monkeypatch):
    from src import app as app_mod
    # Simulate no redis
    monkeypatch.setattr(app_mod, "redis_client", None)
    client = TestClient(app_mod.app)
    with respx.mock(assert_all_called=True) as mock:
        mock.get("http://router:8000/mcp/servers").mock(
            return_value=httpx.Response(
                200,
                json={"servers": [{"name": "filesystem-mcp", "type": "http", "url": "http://mcp-filesystem:7001"}]},
            )
        )
        resp = client.get("/api/ai/mcp/servers")
        assert resp.status_code == 200
        servers = resp.json()["servers"]
        assert servers[0]["enabled"] is True
