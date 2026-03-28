"""Integration tests for MCP registry auto-registration."""

import httpx
import pytest


class TestMCPRegistryIntegration:
    """Test MCP registry integration."""

    @pytest.fixture
    def mcp_registry_url(self):
        """Get MCP registry URL."""
        return "http://localhost:8001"

    @pytest.fixture
    def sample_mcp_server(self):
        """Sample MCP server for testing."""
        return {
            "name": "test-mcp-server",
            "type": "tool",
            "description": "Test MCP server for integration testing",
            "version": "1.0.0",
            "url": "http://test-mcp:7000",
            "health_url": "http://test-mcp:7000/health",
            "tools": [
                {
                    "name": "test_tool",
                    "description": "A test tool",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "input": {"type": "string"}
                        }
                    }
                }
            ],
            "resources": [],
            "metadata": {
                "env": {
                    "TEST_VAR": "test_value"
                }
            }
        }

    @pytest.mark.asyncio
    async def test_mcp_server_registration(self, mcp_registry_url, sample_mcp_server):
        """Test MCP server registration."""
        async with httpx.AsyncClient() as client:
            # Register server
            response = await client.post(
                f"{mcp_registry_url}/mcp/registry/register",
                json=sample_mcp_server
            )

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == sample_mcp_server["name"]
            assert data["type"] == sample_mcp_server["type"]
            assert data["url"] == sample_mcp_server["url"]

    @pytest.mark.asyncio
    async def test_mcp_server_retrieval(self, mcp_registry_url, sample_mcp_server):
        """Test MCP server retrieval after registration."""
        async with httpx.AsyncClient() as client:
            # Register server first
            await client.post(
                f"{mcp_registry_url}/mcp/registry/register",
                json=sample_mcp_server
            )

            # Get all servers
            response = await client.get(f"{mcp_registry_url}/mcp/registry")
            assert response.status_code == 200

            servers = response.json()
            assert len(servers) > 0

            # Find our test server
            test_server = next(
                (s for s in servers if s["name"] == sample_mcp_server["name"]),
                None
            )
            assert test_server is not None
            assert test_server["type"] == "tool"
            assert test_server["url"] == "http://test-mcp:7000"

    @pytest.mark.asyncio
    async def test_mcp_server_by_name(self, mcp_registry_url, sample_mcp_server):
        """Test getting MCP server by name."""
        async with httpx.AsyncClient() as client:
            # Register server first
            await client.post(
                f"{mcp_registry_url}/mcp/registry/register",
                json=sample_mcp_server
            )

            # Get specific server
            response = await client.get(
                f"{mcp_registry_url}/mcp/registry/{sample_mcp_server['name']}"
            )
            assert response.status_code == 200

            server = response.json()
            assert server["name"] == sample_mcp_server["name"]
            assert server["type"] == sample_mcp_server["type"]

    @pytest.mark.asyncio
    async def test_mcp_server_not_found(self, mcp_registry_url):
        """Test getting non-existent MCP server."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{mcp_registry_url}/mcp/registry/non-existent")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_mcp_tools_retrieval(self, mcp_registry_url, sample_mcp_server):
        """Test retrieving tools from registered servers."""
        async with httpx.AsyncClient() as client:
            # Register server first
            await client.post(
                f"{mcp_registry_url}/mcp/registry/register",
                json=sample_mcp_server
            )

            # Get all tools
            response = await client.get(f"{mcp_registry_url}/mcp/registry/tools")
            assert response.status_code == 200

            tools = response.json()
            assert len(tools) > 0

            # Find our test tool
            test_tool = next(
                (t for t in tools if t["name"] == "test_tool"),
                None
            )
            assert test_tool is not None
            assert test_tool["server"] == sample_mcp_server["name"]
            assert test_tool["server_type"] == "tool"

    @pytest.mark.asyncio
    async def test_mcp_resources_retrieval(self, mcp_registry_url, sample_mcp_server):
        """Test retrieving resources from registered servers."""
        # Add resources to sample server
        sample_mcp_server["resources"] = [
            {
                "name": "test_resource",
                "description": "A test resource",
                "mime_type": "text/plain"
            }
        ]

        async with httpx.AsyncClient() as client:
            # Register server first
            await client.post(
                f"{mcp_registry_url}/mcp/registry/register",
                json=sample_mcp_server
            )

            # Get all resources
            response = await client.get(f"{mcp_registry_url}/mcp/registry/resources")
            assert response.status_code == 200

            resources = response.json()
            assert len(resources) > 0

            # Find our test resource
            test_resource = next(
                (r for r in resources if r["name"] == "test_resource"),
                None
            )
            assert test_resource is not None
            assert test_resource["server"] == sample_mcp_server["name"]

    @pytest.mark.asyncio
    async def test_mcp_server_schema(self, mcp_registry_url, sample_mcp_server):
        """Test getting server schema."""
        async with httpx.AsyncClient() as client:
            # Register server first
            await client.post(
                f"{mcp_registry_url}/mcp/registry/register",
                json=sample_mcp_server
            )

            # Get server schema
            response = await client.get(
                f"{mcp_registry_url}/mcp/registry/{sample_mcp_server['name']}/schema"
            )
            assert response.status_code == 200

            schema = response.json()
            assert schema is not None

    @pytest.mark.asyncio
    async def test_mcp_search_tools(self, mcp_registry_url, sample_mcp_server):
        """Test searching tools."""
        async with httpx.AsyncClient() as client:
            # Register server first
            await client.post(
                f"{mcp_registry_url}/mcp/registry/register",
                json=sample_mcp_server
            )

            # Search for tools
            response = await client.get(
                f"{mcp_registry_url}/mcp/registry/search/tools",
                params={"q": "test"}
            )
            assert response.status_code == 200

            tools = response.json()
            assert len(tools) > 0
            assert any("test" in tool["name"].lower() for tool in tools)

    @pytest.mark.asyncio
    async def test_mcp_search_resources(self, mcp_registry_url, sample_mcp_server):
        """Test searching resources."""
        # Add resources to sample server
        sample_mcp_server["resources"] = [
            {
                "name": "test_resource",
                "description": "A test resource for searching",
                "mime_type": "text/plain"
            }
        ]

        async with httpx.AsyncClient() as client:
            # Register server first
            await client.post(
                f"{mcp_registry_url}/mcp/registry/register",
                json=sample_mcp_server
            )

            # Search for resources
            response = await client.get(
                f"{mcp_registry_url}/mcp/registry/search/resources",
                params={"q": "test"}
            )
            assert response.status_code == 200

            resources = response.json()
            assert len(resources) > 0
            assert any("test" in resource["name"].lower() for resource in resources)

    @pytest.mark.asyncio
    async def test_mcp_registry_stats(self, mcp_registry_url, sample_mcp_server):
        """Test registry statistics."""
        async with httpx.AsyncClient() as client:
            # Register server first
            await client.post(
                f"{mcp_registry_url}/mcp/registry/register",
                json=sample_mcp_server
            )

            # Get registry stats
            response = await client.get(f"{mcp_registry_url}/mcp/registry/stats")
            assert response.status_code == 200

            stats = response.json()
            assert "total_servers" in stats
            assert "tool_servers" in stats
            assert "resource_servers" in stats
            assert "total_tools" in stats
            assert "total_resources" in stats
            assert stats["total_servers"] > 0

    @pytest.mark.asyncio
    async def test_mcp_registry_health(self, mcp_registry_url):
        """Test MCP registry health endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{mcp_registry_url}/health")
            assert response.status_code == 200

            health = response.json()
            assert health["status"] == "healthy"
            assert "service" in health
            assert "servers_count" in health

    @pytest.mark.asyncio
    async def test_duplicate_server_registration(self, mcp_registry_url, sample_mcp_server):
        """Test registering duplicate server (should update)."""
        async with httpx.AsyncClient() as client:
            # Register server first time
            response1 = await client.post(
                f"{mcp_registry_url}/mcp/registry/register",
                json=sample_mcp_server
            )
            assert response1.status_code == 200

            # Update server with new URL
            updated_server = sample_mcp_server.copy()
            updated_server["url"] = "http://test-mcp-updated:7000"

            # Register server second time (should update)
            response2 = await client.post(
                f"{mcp_registry_url}/mcp/registry/register",
                json=updated_server
            )
            assert response2.status_code == 200

            # Verify server was updated
            response3 = await client.get(
                f"{mcp_registry_url}/mcp/registry/{sample_mcp_server['name']}"
            )
            assert response3.status_code == 200

            server = response3.json()
            assert server["url"] == "http://test-mcp-updated:7000"

    @pytest.mark.asyncio
    async def test_invalid_server_registration(self, mcp_registry_url):
        """Test registering invalid server data."""
        async with httpx.AsyncClient() as client:
            # Try to register server with missing required fields
            invalid_server = {
                "name": "invalid-server",
                # Missing required fields
            }

            response = await client.post(
                f"{mcp_registry_url}/mcp/registry/register",
                json=invalid_server
            )
            assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_server_filtering_by_type(self, mcp_registry_url):
        """Test filtering servers by type."""
        # Register tool server
        tool_server = {
            "name": "test-tool-server",
            "type": "tool",
            "description": "Test tool server",
            "version": "1.0.0",
            "url": "http://tool-server:7000",
            "tools": [],
            "resources": []
        }

        # Register resource server
        resource_server = {
            "name": "test-resource-server",
            "type": "resource",
            "description": "Test resource server",
            "version": "1.0.0",
            "url": "http://resource-server:7000",
            "tools": [],
            "resources": []
        }

        async with httpx.AsyncClient() as client:
            # Register both servers
            await client.post(f"{mcp_registry_url}/mcp/registry/register", json=tool_server)
            await client.post(f"{mcp_registry_url}/mcp/registry/register", json=resource_server)

            # Filter by tool type
            response = await client.get(
                f"{mcp_registry_url}/mcp/registry",
                params={"type": "tool"}
            )
            assert response.status_code == 200

            tool_servers = response.json()
            assert len(tool_servers) > 0
            assert all(server["type"] == "tool" for server in tool_servers)

            # Filter by resource type
            response = await client.get(
                f"{mcp_registry_url}/mcp/registry",
                params={"type": "resource"}
            )
            assert response.status_code == 200

            resource_servers = response.json()
            assert len(resource_servers) > 0
            assert all(server["type"] == "resource" for server in resource_servers)
