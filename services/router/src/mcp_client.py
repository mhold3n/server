"""MCP client for communicating with MCP servers."""

import asyncio
from typing import Any

import structlog
import yaml
from httpx import AsyncClient, HTTPError, Timeout

from .config import settings

logger = structlog.get_logger()


class MCPServer:
    """Represents an MCP server configuration."""

    def __init__(self, name: str, url: str, server_type: str | None = None, type: str | None = None, **kwargs):
        # Accept either 'server_type' or legacy 'type' key from config
        resolved_type = server_type or type
        if not resolved_type:
            raise ValueError("server_type is required (use 'server_type' or 'type' in config)")
        self.name = name
        self.server_type = resolved_type
        self.url = url
        self.config = kwargs

    def __repr__(self) -> str:
        return f"MCPServer(name={self.name}, type={self.server_type}, url={self.url})"


class MCPClient:
    """Client for communicating with MCP servers."""

    def __init__(self):
        self.servers: dict[str, MCPServer] = {}
        self.http_client: AsyncClient | None = None
        self._load_servers()

    def _load_servers(self) -> None:
        """Load MCP servers from configuration file."""
        try:
            with open(settings.mcp_servers_config) as f:
                config = yaml.safe_load(f)

            servers_config = config.get('servers', [])
            for server_config in servers_config:
                server = MCPServer(**server_config)
                self.servers[server.name] = server

            logger.info(
                "Loaded MCP servers",
                count=len(self.servers),
                servers=list(self.servers.keys()),
            )
        except Exception as e:
            logger.error(
                "Failed to load MCP servers configuration",
                error=str(e),
                config_path=settings.mcp_servers_config,
            )

    async def __aenter__(self):
        """Async context manager entry."""
        self.http_client = AsyncClient(
            timeout=Timeout(
                connect=settings.mcp_connect_timeout,
                read=settings.mcp_request_timeout,
                write=settings.mcp_request_timeout,
                pool=settings.mcp_request_timeout,
            )
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.http_client:
            await self.http_client.aclose()

    async def list_servers(self) -> list[MCPServer]:
        """List all configured MCP servers."""
        return list(self.servers.values())

    async def get_server_tools(self, server_name: str) -> list[dict[str, Any]]:
        """Get available tools from an MCP server."""
        if server_name not in self.servers:
            raise ValueError(f"Server '{server_name}' not found")

        server = self.servers[server_name]

        try:
            response = await self.http_client.get(f"{server.url}/tools")
            response.raise_for_status()
            return response.json()
        except HTTPError as e:
            logger.error(
                "Failed to get tools from MCP server",
                server=server_name,
                error=str(e),
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error getting tools from MCP server",
                server=server_name,
                error=str(e),
            )
            raise

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call a tool on an MCP server."""
        if server_name not in self.servers:
            raise ValueError(f"Server '{server_name}' not found")

        server = self.servers[server_name]

        payload = {
            "tool": tool_name,
            "arguments": arguments or {},
        }

        try:
            logger.info(
                "Calling MCP tool",
                server=server_name,
                tool=tool_name,
                arguments=arguments,
            )

            response = await self.http_client.post(
                f"{server.url}/call",
                json=payload,
            )
            response.raise_for_status()

            result = response.json()

            logger.info(
                "MCP tool call successful",
                server=server_name,
                tool=tool_name,
                result_keys=list(result.keys()) if isinstance(result, dict) else None,
            )

            return result

        except HTTPError as e:
            logger.error(
                "Failed to call MCP tool",
                server=server_name,
                tool=tool_name,
                error=str(e),
                status_code=e.response.status_code if e.response else None,
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error calling MCP tool",
                server=server_name,
                tool=tool_name,
                error=str(e),
            )
            raise

    async def health_check(self, server_name: str) -> bool:
        """Check if an MCP server is healthy."""
        if server_name not in self.servers:
            return False

        server = self.servers[server_name]

        try:
            response = await self.http_client.get(f"{server.url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def health_check_all(self) -> dict[str, bool]:
        """Check health of all MCP servers."""
        health_status = {}

        tasks = [
            self.health_check(server_name)
            for server_name in self.servers.keys()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, server_name in enumerate(self.servers.keys()):
            result = results[i]
            if isinstance(result, Exception):
                health_status[server_name] = False
                logger.error(
                    "Health check failed for MCP server",
                    server=server_name,
                    error=str(result),
                )
            else:
                health_status[server_name] = result

        return health_status


# Global MCP client instance
mcp_client = MCPClient()
