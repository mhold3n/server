from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from tenacity import Future, RetryError

from src.worker_client import ChatMessage, ChatRequest, WorkerClient


@pytest.mark.asyncio
async def test_health_check_returns_false_when_client_missing(monkeypatch) -> None:
    client = WorkerClient()

    async def noop() -> None:
        return None

    monkeypatch.setattr(client, "_ensure_client", noop)
    assert await client.health_check() is False


@pytest.mark.asyncio
async def test_list_models_raises_when_openai_client_missing(monkeypatch) -> None:
    client = WorkerClient()

    async def noop() -> None:
        return None

    monkeypatch.setattr(client, "_ensure_client", noop)
    with pytest.raises(RuntimeError, match="OpenAI client not initialized"):
        await client.list_models()


@pytest.mark.asyncio
async def test_list_models_logs_and_reraises_on_exception(monkeypatch) -> None:
    client = WorkerClient()
    client._client = AsyncMock()
    client._client.models.list.side_effect = RuntimeError("boom")

    async def noop() -> None:
        return None

    monkeypatch.setattr(client, "_ensure_client", noop)
    with pytest.raises(RuntimeError, match="boom"):
        await client.list_models()


@pytest.mark.asyncio
async def test_chat_completion_optional_params_and_client_missing(monkeypatch) -> None:
    client = WorkerClient()
    req = ChatRequest(
        messages=[ChatMessage(role="user", content="hi")],
        top_p=0.9,
        frequency_penalty=1.0,
        presence_penalty=1.0,
    )

    async def noop() -> None:
        return None

    monkeypatch.setattr(client, "_ensure_client", noop)
    with pytest.raises(RuntimeError, match="OpenAI client not initialized"):
        await client.chat_completion(req)


@pytest.mark.asyncio
async def test_chat_completion_retry_error_path(monkeypatch) -> None:
    client = WorkerClient(max_retries=2)
    req = ChatRequest(messages=[ChatMessage(role="user", content="hi")])

    async def noop() -> None:
        return None

    monkeypatch.setattr(client, "_ensure_client", noop)
    client._client = AsyncMock()

    class _Retrying:
        def __aiter__(self):
            fut = Future(1)
            fut.set_exception(RuntimeError("boom"))
            raise RetryError(fut)

    monkeypatch.setattr("src.worker_client.AsyncRetrying", lambda *a, **k: _Retrying())

    with pytest.raises(RetryError):
        await client.chat_completion(req)


@pytest.mark.asyncio
async def test_chat_completion_stream_optional_params_and_missing_client(
    monkeypatch,
) -> None:
    client = WorkerClient()
    req = ChatRequest(
        messages=[ChatMessage(role="user", content="hi")],
        top_p=0.9,
        frequency_penalty=1.0,
        presence_penalty=1.0,
    )

    async def noop() -> None:
        return None

    monkeypatch.setattr(client, "_ensure_client", noop)
    with pytest.raises(RuntimeError, match="OpenAI client not initialized"):
        async for _ in client.chat_completion_stream(req):
            pass


@pytest.mark.asyncio
async def test_chat_completion_stream_logs_and_reraises(monkeypatch) -> None:
    client = WorkerClient()
    req = ChatRequest(messages=[ChatMessage(role="user", content="hi")])

    async def noop() -> None:
        return None

    monkeypatch.setattr(client, "_ensure_client", noop)
    client._client = AsyncMock()
    client._client.chat.completions.create.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        async for _ in client.chat_completion_stream(req):
            pass
