import asyncio
from pathlib import Path

import httpx
import respx

from src.config import settings
from src.mcp_client import MCPClient

_MCP_SERVERS_YAML = str(
    Path(__file__).resolve().parent.parent / "config" / "mcp_servers.yaml"
)


def test_mcp_client_loads_servers(monkeypatch):
    monkeypatch.setattr(settings, "mcp_servers_config", _MCP_SERVERS_YAML)
    client = MCPClient()
    servers = asyncio.get_event_loop().run_until_complete(client.list_servers())
    assert any(s.name == "github-mcp" for s in servers)


def test_mcp_client_get_tools(monkeypatch):
    monkeypatch.setattr(settings, "mcp_servers_config", _MCP_SERVERS_YAML)
    with respx.mock(assert_all_called=True) as mock:
        mock.get("http://mcp-github:7000/tools").mock(
            return_value=httpx.Response(200, json=[{"name": "search"}])
        )

        async def run():
            async with MCPClient() as client:
                tools = await client.get_server_tools("github-mcp")
                return tools

        tools = asyncio.get_event_loop().run_until_complete(run())
        assert tools[0]["name"] == "search"


def test_mcp_client_call_tool(monkeypatch):
    monkeypatch.setattr(settings, "mcp_servers_config", _MCP_SERVERS_YAML)
    with respx.mock(assert_all_called=True) as mock:
        mock.post("http://mcp-github:7000/call").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )

        async def run():
            async with MCPClient() as client:
                res = await client.call_tool("github-mcp", "search", {"q": "test"})
                return res

        res = asyncio.get_event_loop().run_until_complete(run())
        assert res["ok"] is True


def test_mcp_client_health(monkeypatch):
    monkeypatch.setattr(settings, "mcp_servers_config", _MCP_SERVERS_YAML)
    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://mcp-github:7000/health").mock(return_value=httpx.Response(200))

        async def run():
            async with MCPClient() as client:
                return await client.health_check_all()

        res = asyncio.get_event_loop().run_until_complete(run())
        assert isinstance(res, dict)
