from unittest.mock import patch

from fastapi.testclient import TestClient

from src.router import app


def test_mcp_tools_server_not_found():
    client = TestClient(app)

    class FakeMCP:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get_server_tools(self, server):
            raise ValueError("not found")

    with patch("src.router.MCPClient", return_value=FakeMCP()):
        resp = client.get("/mcp/servers/missing/tools")
        assert resp.status_code == 404


def test_mcp_call_error_maps_to_500():
    client = TestClient(app)

    class FakeMCP:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def call_tool(self, server, tool, args=None):
            raise RuntimeError("boom")

    with patch("src.router.MCPClient", return_value=FakeMCP()):
        resp = client.post(
            "/mcp/servers/github-mcp/call", params={"tool_name": "search"}
        )
        assert resp.status_code == 500


def test_mcp_tools_generic_error_maps_500():
    client = TestClient(app)

    class FakeMCP:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get_server_tools(self, server):
            raise RuntimeError("boom")

    with patch("src.router.MCPClient", return_value=FakeMCP()):
        resp = client.get("/mcp/servers/test/tools")
        assert resp.status_code == 500
