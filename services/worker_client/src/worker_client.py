"""Typed client for vLLM/TGI worker communication."""

from collections.abc import AsyncGenerator
from types import TracebackType
from typing import Any

import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from tenacity import (
    AsyncRetrying,
    RetryError,
    stop_after_attempt,
    wait_exponential,
)

from .config import settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


class ChatMessage(BaseModel):
    """Chat message model."""

    role: str = Field(..., description="Message role (system, user, assistant)")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Chat completion request model."""

    model: str = Field(
        default=settings.default_model,
        description="Model to use for completion",
    )
    messages: list[ChatMessage] = Field(..., description="List of messages")
    temperature: float = Field(
        default=settings.default_temperature,
        ge=0.0,
        le=2.0,
        description="Sampling temperature",
    )
    max_tokens: int = Field(
        default=settings.default_max_tokens,
        gt=0,
        description="Maximum tokens to generate",
    )
    stream: bool = Field(
        default=False,
        description="Enable streaming response",
    )
    top_p: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling parameter",
    )
    frequency_penalty: float | None = Field(
        default=None,
        ge=-2.0,
        le=2.0,
        description="Frequency penalty",
    )
    presence_penalty: float | None = Field(
        default=None,
        ge=-2.0,
        le=2.0,
        description="Presence penalty",
    )


class ChatResponse(BaseModel):
    """Chat completion response model."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[dict[str, Any]]
    usage: dict[str, int] | None = None


class ModelInfo(BaseModel):
    """Model information model."""

    id: str
    object: str = "model"
    created: int
    owned_by: str = "vllm"
    permission: list[dict[str, Any]] = Field(default_factory=list)
    root: str | None = None
    parent: str | None = None


class WorkerClient:
    """Client for communicating with vLLM/TGI workers."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
    ) -> None:
        """Initialize the worker client."""
        self.base_url = base_url or settings.worker_base_url
        self.api_key = api_key or settings.worker_api_key
        self.timeout = timeout or settings.timeout
        self.max_retries = max_retries or settings.max_retries

        self._client: AsyncOpenAI | None = None

        logger.info(
            "Initialized worker client",
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )

    async def __aenter__(self) -> "WorkerClient":
        """Async context manager entry."""
        await self._ensure_client()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.close()

    async def _ensure_client(self) -> None:
        """Ensure the OpenAI client is initialized."""
        if not self._client:
            self._client = AsyncOpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout,
            )

    async def health_check(self) -> bool:
        """Check if the worker is healthy."""
        try:
            await self._ensure_client()
            if not self._client:
                return False
            await self._client.models.list()
            return True
        except Exception as e:
            logger.error("Worker health check failed", error=str(e))
            return False

    async def list_models(self) -> list[ModelInfo]:
        """List available models."""
        await self._ensure_client()

        try:
            if not self._client:
                raise RuntimeError("OpenAI client not initialized")
            response = await self._client.models.list()
            models = []

            for model in response.data:
                models.append(
                    ModelInfo(
                        id=model.id,
                        created=model.created,
                        owned_by=getattr(model, "owned_by", "vllm"),
                        permission=getattr(model, "permission", []),
                        root=getattr(model, "root", None),
                        parent=getattr(model, "parent", None),
                    )
                )

            logger.info("Listed models", count=len(models))
            return models

        except Exception as e:
            logger.error("Failed to list models", error=str(e))
            raise

    async def chat_completion(
        self,
        request: ChatRequest,
    ) -> ChatResponse:
        """Send a chat completion request with retries."""
        await self._ensure_client()

        # Convert to OpenAI format
        openai_messages = [
            {"role": msg.role, "content": msg.content} for msg in request.messages
        ]

        # Prepare request parameters
        request_params: dict[str, Any] = {
            "model": request.model,
            "messages": openai_messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": request.stream,
        }

        # Add optional parameters
        if request.top_p is not None:
            request_params["top_p"] = request.top_p
        if request.frequency_penalty is not None:
            request_params["frequency_penalty"] = request.frequency_penalty
        if request.presence_penalty is not None:
            request_params["presence_penalty"] = request.presence_penalty

        # Retry logic
        retry_strategy = AsyncRetrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(
                multiplier=settings.retry_delay,
                max=settings.retry_delay * settings.retry_backoff**self.max_retries,
            ),
            reraise=True,
        )

        try:
            async for attempt in retry_strategy:
                try:
                    logger.info(
                        "Sending chat completion request",
                        model=request.model,
                        message_count=len(request.messages),
                        attempt=attempt.retry_state.attempt_number,
                    )

                    if not self._client:
                        raise RuntimeError("OpenAI client not initialized")
                    response = await self._client.chat.completions.create(
                        **request_params
                    )

                    # Convert to our response model
                    chat_response = ChatResponse(
                        id=response.id,
                        created=response.created,
                        model=response.model,
                        choices=[
                            {
                                "index": choice.index,
                                "message": {
                                    "role": choice.message.role,
                                    "content": choice.message.content,
                                },
                                "finish_reason": choice.finish_reason,
                            }
                            for choice in response.choices
                        ],
                        usage=response.usage.dict() if response.usage else None,
                    )

                    logger.info(
                        "Chat completion successful",
                        model=request.model,
                        response_id=chat_response.id,
                        usage=chat_response.usage,
                    )

                    return chat_response

                except Exception as e:
                    logger.warning(
                        "Chat completion attempt failed",
                        model=request.model,
                        attempt=attempt.retry_state.attempt_number,
                        error=str(e),
                    )
                    raise

        except RetryError as e:
            logger.error(
                "Chat completion failed after all retries",
                model=request.model,
                attempts=self.max_retries,
                error=str(e),
            )
            raise
        raise RuntimeError("Chat completion exhausted retries without result")

    async def chat_completion_stream(
        self,
        request: ChatRequest,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Send a streaming chat completion request."""
        await self._ensure_client()

        # Ensure streaming is enabled
        request.stream = True

        # Convert to OpenAI format
        openai_messages = [
            {"role": msg.role, "content": msg.content} for msg in request.messages
        ]

        # Prepare request parameters
        request_params: dict[str, Any] = {
            "model": request.model,
            "messages": openai_messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": True,
        }

        # Add optional parameters
        if request.top_p is not None:
            request_params["top_p"] = request.top_p
        if request.frequency_penalty is not None:
            request_params["frequency_penalty"] = request.frequency_penalty
        if request.presence_penalty is not None:
            request_params["presence_penalty"] = request.presence_penalty

        try:
            logger.info(
                "Starting streaming chat completion",
                model=request.model,
                message_count=len(request.messages),
            )

            if not self._client:
                raise RuntimeError("OpenAI client not initialized")
            stream = await self._client.chat.completions.create(**request_params)

            async for chunk in stream:
                if chunk.choices:
                    choice = chunk.choices[0]
                    if choice.delta.content:
                        yield {
                            "id": chunk.id,
                            "object": chunk.object,
                            "created": chunk.created,
                            "model": chunk.model,
                            "choices": [
                                {
                                    "index": choice.index,
                                    "delta": {
                                        "role": getattr(choice.delta, "role", None),
                                        "content": choice.delta.content,
                                    },
                                    "finish_reason": choice.finish_reason,
                                }
                            ],
                        }

            logger.info("Streaming chat completion completed", model=request.model)

        except Exception as e:
            logger.error(
                "Streaming chat completion failed",
                model=request.model,
                error=str(e),
            )
            raise

    async def get_model_info(self, model_id: str) -> ModelInfo | None:
        """Get information about a specific model."""
        models = await self.list_models()
        for model in models:
            if model.id == model_id:
                return model
        return None

    async def estimate_tokens(self, text: str, model: str | None = None) -> int:
        """Estimate the number of tokens in text (rough approximation).

        Args:
            text: Input text.
            model: Reserved for future per-model tokenizers.
        """
        # This is a rough approximation - in production, you'd want to use
        # the actual tokenizer for the model
        _ = model
        return int(len(text.split()) * 1.3)


# Convenience functions
async def create_chat_completion(
    messages: list[ChatMessage],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    **kwargs: Any,
) -> ChatResponse:
    """Convenience function to create a chat completion."""
    request = ChatRequest(
        messages=messages,
        model=model or settings.default_model,
        temperature=temperature or settings.default_temperature,
        max_tokens=max_tokens or settings.default_max_tokens,
        **kwargs,
    )

    async with WorkerClient() as client:
        return await client.chat_completion(request)


async def create_chat_completion_stream(
    messages: list[ChatMessage],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    **kwargs: Any,
) -> AsyncGenerator[dict[str, Any], None]:
    """Convenience function to create a streaming chat completion."""
    request = ChatRequest(
        messages=messages,
        model=model or settings.default_model,
        temperature=temperature or settings.default_temperature,
        max_tokens=max_tokens or settings.default_max_tokens,
        stream=True,
        **kwargs,
    )

    async with WorkerClient() as client:
        async for chunk in client.chat_completion_stream(request):
            yield chunk
