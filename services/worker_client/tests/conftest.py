"""Shared test fixtures for worker client."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import AsyncOpenAI

from src.worker_client import ChatMessage, ChatRequest, ChatResponse, ModelInfo


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_openai_client() -> AsyncMock:
    """Mock OpenAI client."""
    mock = AsyncMock(spec=AsyncOpenAI)

    # Mock models.list response
    mock_models = MagicMock()
    mock_models.data = [
        MagicMock(
            id="test-model",
            created=1234567890,
            owned_by="vllm",
            permission=[],
            root=None,
            parent=None,
        )
    ]
    mock.models.list.return_value = mock_models

    # Mock chat completions response
    mock_response = MagicMock()
    mock_response.id = "chatcmpl-test"
    mock_response.object = "chat.completion"
    mock_response.created = 1234567890
    mock_response.model = "test-model"
    mock_response.choices = [
        MagicMock(
            index=0,
            message=MagicMock(role="assistant", content="Test response"),
            finish_reason="stop",
        )
    ]
    mock_response.usage = MagicMock()
    mock_response.usage.dict.return_value = {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }

    mock.chat.completions.create.return_value = mock_response

    return mock


@pytest.fixture
def sample_messages() -> list[ChatMessage]:
    """Sample chat messages."""
    return [
        ChatMessage(role="system", content="You are a helpful assistant."),
        ChatMessage(role="user", content="Hello, world!"),
    ]


@pytest.fixture
def sample_chat_request(sample_messages: list[ChatMessage]) -> ChatRequest:
    """Sample chat request."""
    return ChatRequest(
        messages=sample_messages,
        model="test-model",
        temperature=0.7,
        max_tokens=100,
    )


@pytest.fixture
def sample_chat_response() -> ChatResponse:
    """Sample chat response."""
    return ChatResponse(
        id="chatcmpl-test",
        created=1234567890,
        model="test-model",
        choices=[
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Test response"},
                "finish_reason": "stop",
            }
        ],
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    )


@pytest.fixture
def sample_model_info() -> ModelInfo:
    """Sample model info."""
    return ModelInfo(
        id="test-model",
        created=1234567890,
        owned_by="vllm",
        permission=[],
        root=None,
        parent=None,
    )
