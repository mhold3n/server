"""Tests for the worker client."""

from unittest.mock import AsyncMock, patch

import pytest

from src.worker_client import (
    ChatMessage,
    ChatRequest,
    WorkerClient,
    create_chat_completion,
    create_chat_completion_stream,
)


class TestWorkerClient:
    """Test WorkerClient class."""

    @pytest.mark.asyncio
    async def test_init(self):
        """Test client initialization."""
        client = WorkerClient(
            base_url="http://test:8000",
            api_key="test-key",
            timeout=60,
            max_retries=2,
        )

        assert client.base_url == "http://test:8000"
        assert client.api_key == "test-key"
        assert client.timeout == 60
        assert client.max_retries == 2

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_openai_client: AsyncMock):
        """Test successful health check."""
        client = WorkerClient()

        with patch("src.worker_client.AsyncOpenAI", return_value=mock_openai_client):
            async with client:
                result = await client.health_check()
                assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check failure."""
        client = WorkerClient()

        mock_client = AsyncMock()
        mock_client.models.list.side_effect = Exception("Connection failed")

        with patch("src.worker_client.AsyncOpenAI", return_value=mock_client):
            async with client:
                result = await client.health_check()
                assert result is False

    @pytest.mark.asyncio
    async def test_list_models(self, mock_openai_client: AsyncMock):
        """Test listing models."""
        client = WorkerClient()

        with patch("src.worker_client.AsyncOpenAI", return_value=mock_openai_client):
            async with client:
                models = await client.list_models()

                assert len(models) == 1
                assert models[0].id == "test-model"
                assert models[0].owned_by == "vllm"

    @pytest.mark.asyncio
    async def test_chat_completion_success(
        self,
        mock_openai_client: AsyncMock,
        sample_chat_request: ChatRequest,
    ):
        """Test successful chat completion."""
        client = WorkerClient()

        with patch("src.worker_client.AsyncOpenAI", return_value=mock_openai_client):
            async with client:
                response = await client.chat_completion(sample_chat_request)

                assert response.id == "chatcmpl-test"
                assert response.model == "test-model"
                assert len(response.choices) == 1
                assert response.choices[0]["message"]["content"] == "Test response"
                assert response.usage["total_tokens"] == 15

    @pytest.mark.asyncio
    async def test_chat_completion_with_retries(
        self,
        sample_chat_request: ChatRequest,
    ):
        """Test chat completion with retries."""
        client = WorkerClient(max_retries=2)

        mock_client = AsyncMock()
        mock_client.models.list.return_value = AsyncMock()

        # First call fails, second succeeds
        mock_response = AsyncMock()
        mock_response.id = "chatcmpl-test"
        mock_response.created = 1234567890
        mock_response.model = "test-model"
        mock_response.choices = [
            AsyncMock(
                index=0,
                message=AsyncMock(role="assistant", content="Test response"),
                finish_reason="stop",
            )
        ]
        mock_response.usage = AsyncMock()
        mock_response.usage.dict.return_value = {"total_tokens": 15}

        mock_client.chat.completions.create.side_effect = [
            Exception("First attempt fails"),
            mock_response,
        ]

        with patch("src.worker_client.AsyncOpenAI", return_value=mock_client):
            async with client:
                response = await client.chat_completion(sample_chat_request)

                assert response.id == "chatcmpl-test"
                assert mock_client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_chat_completion_stream(
        self,
        sample_chat_request: ChatRequest,
    ):
        """Test streaming chat completion."""
        client = WorkerClient()

        # Mock streaming response
        mock_chunk1 = AsyncMock()
        mock_chunk1.id = "chatcmpl-test"
        mock_chunk1.object = "chat.completion.chunk"
        mock_chunk1.created = 1234567890
        mock_chunk1.model = "test-model"
        mock_chunk1.choices = [
            AsyncMock(
                index=0,
                delta=AsyncMock(role=None, content="Hello"),
                finish_reason=None,
            )
        ]

        mock_chunk2 = AsyncMock()
        mock_chunk2.id = "chatcmpl-test"
        mock_chunk2.object = "chat.completion.chunk"
        mock_chunk2.created = 1234567890
        mock_chunk2.model = "test-model"
        mock_chunk2.choices = [
            AsyncMock(
                index=0,
                delta=AsyncMock(role=None, content=" world!"),
                finish_reason="stop",
            )
        ]

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [mock_chunk1, mock_chunk2]

        mock_client = AsyncMock()
        mock_client.models.list.return_value = AsyncMock()
        mock_client.chat.completions.create.return_value = mock_stream

        with patch("src.worker_client.AsyncOpenAI", return_value=mock_client):
            async with client:
                chunks = []
                async for chunk in client.chat_completion_stream(sample_chat_request):
                    chunks.append(chunk)

                assert len(chunks) == 2
                assert chunks[0]["choices"][0]["delta"]["content"] == "Hello"
                assert chunks[1]["choices"][0]["delta"]["content"] == " world!"

    @pytest.mark.asyncio
    async def test_get_model_info(self, mock_openai_client: AsyncMock):
        """Test getting model info."""
        client = WorkerClient()

        with patch("src.worker_client.AsyncOpenAI", return_value=mock_openai_client):
            async with client:
                model_info = await client.get_model_info("test-model")

                assert model_info is not None
                assert model_info.id == "test-model"
                assert model_info.owned_by == "vllm"

    @pytest.mark.asyncio
    async def test_get_model_info_not_found(self, mock_openai_client: AsyncMock):
        """Test getting model info for non-existent model."""
        client = WorkerClient()

        with patch("src.worker_client.AsyncOpenAI", return_value=mock_openai_client):
            async with client:
                model_info = await client.get_model_info("nonexistent-model")

                assert model_info is None

    @pytest.mark.asyncio
    async def test_estimate_tokens(self):
        """Test token estimation."""
        client = WorkerClient()

        # Test with simple text
        tokens = await client.estimate_tokens("Hello world")
        assert tokens > 0

        # Test with longer text
        long_text = "This is a much longer text with many more words to test the token estimation function."
        tokens_long = await client.estimate_tokens(long_text)
        assert tokens_long > tokens


class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.mark.asyncio
    async def test_create_chat_completion(
        self,
        sample_messages: list[ChatMessage],
        mock_openai_client: AsyncMock,
    ):
        """Test create_chat_completion convenience function."""
        with patch("src.worker_client.AsyncOpenAI", return_value=mock_openai_client):
            response = await create_chat_completion(
                messages=sample_messages,
                model="test-model",
                temperature=0.5,
            )

            assert response.id == "chatcmpl-test"
            assert response.model == "test-model"

    @pytest.mark.asyncio
    async def test_create_chat_completion_stream(
        self,
        sample_messages: list[ChatMessage],
    ):
        """Test create_chat_completion_stream convenience function."""
        # Mock streaming response
        mock_chunk = AsyncMock()
        mock_chunk.id = "chatcmpl-test"
        mock_chunk.object = "chat.completion.chunk"
        mock_chunk.created = 1234567890
        mock_chunk.model = "test-model"
        mock_chunk.choices = [
            AsyncMock(
                index=0,
                delta=AsyncMock(role=None, content="Test"),
                finish_reason="stop",
            )
        ]

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [mock_chunk]

        mock_client = AsyncMock()
        mock_client.models.list.return_value = AsyncMock()
        mock_client.chat.completions.create.return_value = mock_stream

        with patch("src.worker_client.AsyncOpenAI", return_value=mock_client):
            chunks = []
            async for chunk in create_chat_completion_stream(
                messages=sample_messages,
                model="test-model",
            ):
                chunks.append(chunk)

            assert len(chunks) == 1
            assert chunks[0]["choices"][0]["delta"]["content"] == "Test"


class TestChatRequest:
    """Test ChatRequest model."""

    def test_chat_request_defaults(self):
        """Test ChatRequest with default values."""
        messages = [ChatMessage(role="user", content="Hello")]
        request = ChatRequest(messages=messages)

        assert request.model == "mistralai/Mistral-7B-Instruct-v0.3"
        assert request.temperature == 0.7
        assert request.max_tokens == 2048
        assert request.stream is False

    def test_chat_request_validation(self):
        """Test ChatRequest validation."""
        messages = [ChatMessage(role="user", content="Hello")]

        # Test valid temperature
        request = ChatRequest(messages=messages, temperature=0.5)
        assert request.temperature == 0.5

        # Test invalid temperature (should raise validation error)
        with pytest.raises(ValueError):
            ChatRequest(messages=messages, temperature=3.0)

        # Test invalid max_tokens
        with pytest.raises(ValueError):
            ChatRequest(messages=messages, max_tokens=0)


class TestChatMessage:
    """Test ChatMessage model."""

    def test_chat_message_creation(self):
        """Test ChatMessage creation."""
        message = ChatMessage(role="user", content="Hello, world!")

        assert message.role == "user"
        assert message.content == "Hello, world!"

    def test_chat_message_validation(self):
        """Test ChatMessage validation."""
        # Valid message
        message = ChatMessage(role="assistant", content="Hi there!")
        assert message.role == "assistant"
        assert message.content == "Hi there!"

        # Empty content should still be valid
        message = ChatMessage(role="system", content="")
        assert message.content == ""
