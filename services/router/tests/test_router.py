"""Tests for the router service."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check_success(
        self, test_client: TestClient, setup_clients, mock_mcp_client
    ):
        """Test successful health check."""
        with patch("src.router.MCPClient") as mock_mcp_class:
            mock_mcp_class.return_value.__aenter__.return_value = mock_mcp_client

            response = test_client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] in ["healthy", "degraded"]
            assert "timestamp" in data
            assert data["version"] == "0.1.0"
            assert "services" in data
            assert "mcp_servers" in data

    def test_health_check_with_redis_failure(
        self, test_client: TestClient, mock_api_client: AsyncMock, mock_mcp_client
    ):
        """Test health check when Redis is unavailable."""
        import src.router

        # Mock Redis failure
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Connection failed")

        with patch.object(src.router, "redis_client", mock_redis):
            with patch.object(src.router, "api_client", mock_api_client):
                with patch("src.router.MCPClient") as mock_mcp_class:
                    mock_mcp_class.return_value.__aenter__.return_value = (
                        mock_mcp_client
                    )

                    response = test_client.get("/health")

                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == "degraded"
                    assert data["services"]["redis"] == "unhealthy"


class TestMCPEndpoints:
    """Test MCP-related endpoints."""

    def test_list_mcp_servers(self, test_client: TestClient, mock_mcp_client):
        """Test listing MCP servers."""
        with patch("src.router.MCPClient") as mock_mcp_class:
            mock_mcp_class.return_value.__aenter__.return_value = mock_mcp_client

            response = test_client.get("/mcp/servers")

            assert response.status_code == 200
            data = response.json()
            assert "servers" in data
            assert len(data["servers"]) == 1
            assert data["servers"][0]["name"] == "test-server"

    def test_get_server_tools(self, test_client: TestClient, mock_mcp_client):
        """Test getting tools from an MCP server."""
        with patch("src.router.MCPClient") as mock_mcp_class:
            mock_mcp_class.return_value.__aenter__.return_value = mock_mcp_client

            response = test_client.get("/mcp/servers/test-server/tools")

            assert response.status_code == 200
            data = response.json()
            assert data["server"] == "test-server"
            assert "tools" in data
            assert len(data["tools"]) == 1
            assert data["tools"][0]["name"] == "test-tool"

    def test_get_server_tools_not_found(self, test_client: TestClient, mock_mcp_client):
        """Test getting tools from a non-existent MCP server."""
        mock_mcp_client.get_server_tools.side_effect = ValueError(
            "Server 'nonexistent' not found"
        )

        with patch("src.router.MCPClient") as mock_mcp_class:
            mock_mcp_class.return_value.__aenter__.return_value = mock_mcp_client

            response = test_client.get("/mcp/servers/nonexistent/tools")

            assert response.status_code == 404
            assert "Server 'nonexistent' not found" in response.json()["detail"]

    def test_call_mcp_tool(self, test_client: TestClient, mock_mcp_client):
        """Test calling an MCP tool."""
        with patch("src.router.MCPClient") as mock_mcp_class:
            mock_mcp_class.return_value.__aenter__.return_value = mock_mcp_client

            response = test_client.post(
                "/mcp/servers/test-server/call",
                params={"tool_name": "test-tool"},
                json={"arg1": "value1"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["server"] == "test-server"
            assert data["tool"] == "test-tool"
            assert data["arguments"] == {"arg1": "value1"}
            assert data["result"] == {"result": "test result"}

    def test_call_mcp_tool_not_found(self, test_client: TestClient, mock_mcp_client):
        """Test calling a tool on a non-existent MCP server."""
        mock_mcp_client.call_tool.side_effect = ValueError(
            "Server 'nonexistent' not found"
        )

        with patch("src.router.MCPClient") as mock_mcp_class:
            mock_mcp_class.return_value.__aenter__.return_value = mock_mcp_client

            response = test_client.post(
                "/mcp/servers/nonexistent/call", params={"tool_name": "test-tool"}
            )

            assert response.status_code == 404
            assert "Server 'nonexistent' not found" in response.json()["detail"]


class TestRouteEndpoint:
    """Test task routing endpoint."""

    def test_route_task_success(
        self,
        test_client: TestClient,
        setup_clients,
        sample_task_request: dict,
        mock_mcp_client,
        mock_api_client: AsyncMock,
    ):
        """Test successful task routing."""
        import src.router

        # Ensure api_client is available (avoid race with startup)
        src.router.api_client = mock_api_client
        with patch("src.router.MCPClient") as mock_mcp_class:
            mock_mcp_class.return_value.__aenter__.return_value = mock_mcp_client

            response = test_client.post("/route", json=sample_task_request)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert data["task_id"].startswith("task_")
            assert data["result"]["id"] == "chatcmpl-test"
            assert "test-server:test-tool" in data["tools_used"]
            assert data["execution_time"] >= 0

    def test_route_task_no_api_client(
        self, test_client: TestClient, mock_redis: AsyncMock
    ):
        """Test task routing when API client is not available."""
        import src.router

        with patch.object(src.router, "redis_client", mock_redis):
            with patch.object(src.router, "api_client", None):
                response = test_client.post(
                    "/route", json={"prompt": "test", "model": "test-model"}
                )

                assert response.status_code == 503
                assert "API client not available" in response.json()["detail"]

    def test_route_task_without_tools(
        self, test_client: TestClient, setup_clients, mock_mcp_client
    ):
        """Test task routing without MCP tools."""

        request = {
            "prompt": "Hello, world!",
            "model": "test-model",
        }

        with patch("src.router.MCPClient") as mock_mcp_class:
            mock_mcp_class.return_value.__aenter__.return_value = mock_mcp_client

            response = test_client.post("/route", json=request)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert data["tools_used"] == []

    def test_route_task_tool_failure(
        self, test_client: TestClient, setup_clients, mock_mcp_client
    ):
        """Test task routing when MCP tool fails."""

        # Mock tool failure
        mock_mcp_client.call_tool.side_effect = Exception("Tool failed")

        request = {
            "prompt": "Hello, world!",
            "model": "test-model",
            "tools": ["test-server:test-tool"],
        }

        with patch("src.router.MCPClient") as mock_mcp_class:
            mock_mcp_class.return_value.__aenter__.return_value = mock_mcp_client

            response = test_client.post("/route", json=request)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"  # Should still complete without tools
            assert data["tools_used"] == []  # No tools used due to failure

    def test_route_task_api_error(
        self, test_client: TestClient, setup_clients, mock_mcp_client
    ):
        """Test task routing when API call fails."""
        # Mock API failure
        from httpx import HTTPError

        import src.router

        src.router.api_client.post.side_effect = HTTPError("API Error")

        request = {
            "prompt": "Hello, world!",
            "model": "test-model",
        }

        with patch("src.router.MCPClient") as mock_mcp_class:
            mock_mcp_class.return_value.__aenter__.return_value = mock_mcp_client

            response = test_client.post("/route", json=request)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "failed"
            assert "API request failed" in data["error"]


class TestRootEndpoint:
    """Test root endpoint."""

    def test_root_endpoint(self, test_client: TestClient):
        """Test root endpoint returns router information."""
        response = test_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Agent Router"
        assert data["version"] == "0.1.0"
        assert data["description"] == "Router service with MCP tool integration"
        assert data["docs"] == "/docs"
        assert data["health"] == "/health"
