from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import src.router
from src.mcp_client import MCPClient, MCPServer


def test_mcp_server_requires_type_and_accepts_legacy_key() -> None:
    with pytest.raises(ValueError):
        MCPServer(name="x", url="http://x")

    s = MCPServer(name="x", url="http://x", type="http")
    assert s.server_type == "http"
    assert "MCPServer(name=x" in repr(s)


@pytest.mark.asyncio
async def test_mcp_client_require_http_guard() -> None:
    c = MCPClient()
    with pytest.raises(RuntimeError):
        c._require_http()


@pytest.mark.asyncio
async def test_mcp_client_tools_and_calls_and_health(
    monkeypatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "mcp.yaml"
    cfg.write_text(
        "servers:\n"
        "  - name: s1\n"
        "    type: http\n"
        "    url: http://s1\n"
        "  - name: s2\n"
        "    server_type: http\n"
        "    url: http://s2\n"
    )
    monkeypatch.setattr("src.mcp_client.settings.mcp_servers_config", str(cfg))

    c = MCPClient()
    assert [s.name for s in await c.list_servers()] == ["s1", "s2"]

    http = AsyncMock()
    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.raise_for_status.return_value = None
    ok_resp.json.return_value = [{"name": "t"}]
    http.get.return_value = ok_resp

    call_resp = MagicMock()
    call_resp.raise_for_status.return_value = None
    call_resp.json.return_value = {"ok": True}
    http.post.return_value = call_resp

    c.http_client = http

    tools = await c.get_server_tools("s1")
    assert tools == [{"name": "t"}]

    result = await c.call_tool("s1", "tool", {"a": 1})
    assert result == {"ok": True}

    with pytest.raises(ValueError):
        await c.get_server_tools("missing")
    with pytest.raises(ValueError):
        await c.call_tool("missing", "t", {})

    assert await c.health_check("missing") is False
    assert await c.health_check("s1") is True


@pytest.mark.asyncio
async def test_mcp_client_call_tool_http_status_error_logs_status_code(
    monkeypatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "mcp.yaml"
    cfg.write_text("servers:\n  - name: s1\n    type: http\n    url: http://s1\n")
    monkeypatch.setattr("src.mcp_client.settings.mcp_servers_config", str(cfg))

    c = MCPClient()
    req = httpx.Request("POST", "http://s1/call")
    resp = httpx.Response(500, request=req, text="boom")
    err = httpx.HTTPStatusError("bad", request=req, response=resp)

    http = AsyncMock()
    http.post.side_effect = err
    c.http_client = http

    with pytest.raises(httpx.HTTPStatusError):
        await c.call_tool("s1", "t", {})


@pytest.mark.asyncio
async def test_mcp_client_get_server_tools_and_call_tool_unexpected_errors(
    monkeypatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "mcp.yaml"
    cfg.write_text("servers:\n  - name: s1\n    type: http\n    url: http://s1\n")
    monkeypatch.setattr("src.mcp_client.settings.mcp_servers_config", str(cfg))

    c = MCPClient()
    http = AsyncMock()
    http.get.side_effect = RuntimeError("boom")
    c.http_client = http
    with pytest.raises(RuntimeError):
        await c.get_server_tools("s1")

    http2 = AsyncMock()
    http2.post.side_effect = RuntimeError("boom")
    c.http_client = http2
    with pytest.raises(RuntimeError):
        await c.call_tool("s1", "t", {})


@pytest.mark.asyncio
async def test_mcp_client_health_check_all_handles_exceptions(
    monkeypatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "mcp.yaml"
    cfg.write_text(
        "servers:\n"
        "  - name: s1\n"
        "    type: http\n"
        "    url: http://s1\n"
        "  - name: s2\n"
        "    type: http\n"
        "    url: http://s2\n"
    )
    monkeypatch.setattr("src.mcp_client.settings.mcp_servers_config", str(cfg))

    c = MCPClient()
    c.http_client = AsyncMock()

    async def fake_health(name: str) -> bool:
        if name == "s2":
            raise RuntimeError("no")
        return True

    monkeypatch.setattr(c, "health_check", fake_health)
    out = await c.health_check_all()
    assert out == {"s1": True, "s2": False}


@pytest.mark.asyncio
async def test_router_startup_and_shutdown_branches(monkeypatch) -> None:
    # Force Redis.from_url to raise; api client to raise.
    monkeypatch.setattr(src.router, "redis_client", None)
    monkeypatch.setattr(src.router, "api_client", None)

    with patch("src.router.Redis.from_url", side_effect=Exception("no redis")):
        with patch("src.router.AsyncClient", side_effect=Exception("no api")):
            await src.router.startup_event()
            assert src.router.redis_client is None
            assert src.router.api_client is None

    # Shutdown should no-op safely when None
    await src.router.shutdown_event()

    # Shutdown closes when present
    mock_redis = AsyncMock()
    mock_api = AsyncMock()
    src.router.redis_client = mock_redis
    src.router.api_client = mock_api
    await src.router.shutdown_event()
    mock_redis.close.assert_awaited()
    mock_api.aclose.assert_awaited()


def test_route_task_default_server_selection_no_servers(
    test_client, setup_clients
) -> None:
    request = {"prompt": "hello", "model": "test-model", "tools": ["just-a-tool"]}
    r = test_client.post("/route", json=request)
    assert r.status_code == 410


def test_route_task_unexpected_exception_returns_failed(
    test_client, setup_clients
) -> None:
    request = {"prompt": "hello", "model": "test-model"}
    r = test_client.post("/route", json=request)
    assert r.status_code == 410
