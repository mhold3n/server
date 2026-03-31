"""Shared test fixtures for router service."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from redis.asyncio import Redis

from src.router import app


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mock Redis client."""
    mock = AsyncMock(spec=Redis)
    mock.ping.return_value = True
    return mock


@pytest.fixture
def mock_api_client() -> AsyncMock:
    """Mock API client."""
    mock = AsyncMock()

    # Mock health check response
    mock_health_response = MagicMock()
    mock_health_response.status_code = 200
    mock.get.return_value = mock_health_response

    # Mock chat completions response
    mock_chat_response = MagicMock()
    mock_chat_response.status_code = 200
    mock_chat_response.json.return_value = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Test response"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    mock_chat_response.raise_for_status.return_value = None
    mock.post.return_value = mock_chat_response

    return mock


@pytest.fixture
def mock_mcp_client() -> AsyncMock:
    """Mock MCP client."""
    mock = AsyncMock()

    # Mock server list
    mock_server = MagicMock()
    mock_server.name = "test-server"
    mock_server.server_type = "http"
    mock_server.url = "http://test-server:7000"
    mock.list_servers.return_value = [mock_server]

    # Mock tools
    mock.get_server_tools.return_value = [
        {"name": "test-tool", "description": "A test tool"}
    ]

    # Mock tool call
    mock.call_tool.return_value = {"result": "test result"}

    # Mock health check
    mock.health_check_all.return_value = {"test-server": True}

    return mock


@pytest.fixture
def setup_clients(
    mock_redis: AsyncMock, mock_api_client: AsyncMock, test_client: TestClient
) -> Generator[None, None, None]:
    """Setup mock clients for testing (sync for pytest 9+)."""
    import src.router

    original_redis = src.router.redis_client
    original_api = src.router.api_client

    src.router.redis_client = mock_redis
    src.router.api_client = mock_api_client

    yield

    src.router.redis_client = original_redis
    src.router.api_client = original_api


@pytest.fixture
def sample_task_request() -> dict:
    """Sample task request payload."""
    return {
        "prompt": "Hello, world!",
        "system": "You are a helpful assistant.",
        "model": "test-model",
        "tools": ["test-server:test-tool"],
        "temperature": 0.7,
        "max_tokens": 100,
    }


@pytest.fixture
def sample_mcp_servers_config() -> dict:
    """Sample MCP servers configuration."""
    return {
        "servers": [
            {
                "name": "test-server",
                "type": "http",
                "url": "http://test-server:7000",
                "description": "Test MCP server",
            }
        ]
    }
