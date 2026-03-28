"""Async client for WrkHrs Gateway API."""

from typing import Any

import structlog
from httpx import AsyncClient, HTTPError

logger = structlog.get_logger()


class WrkHrsGatewayClient:
    """Async client for WrkHrs Gateway API with OpenAI-compatible endpoints."""

    def __init__(
        self,
        base_url: str = "http://wrkhrs-gateway:8000",
        timeout: float = 60.0,
    ):
        """Initialize WrkHrs Gateway client.

        Args:
            base_url: Base URL for WrkHrs Gateway API
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: AsyncClient | None = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def health_check(self) -> dict[str, Any]:
        """Check gateway health status.

        Returns:
            Health status response
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        try:
            response = await self._client.get("/health")
            response.raise_for_status()
            return response.json()
        except HTTPError as e:
            logger.error("Gateway health check failed", error=str(e))
            raise

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str = "mistralai/Mistral-7B-Instruct-v0.3",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send chat completion request to WrkHrs Gateway.

        Args:
            messages: List of chat messages
            model: Model to use for completion
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Enable streaming response
            **kwargs: Additional parameters

        Returns:
            Chat completion response
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        payload = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "stream": stream,
        }

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        # Add any additional parameters
        payload.update(kwargs)

        try:
            logger.info(
                "Sending chat completion request",
                model=model,
                message_count=len(messages),
                stream=stream,
            )

            response = await self._client.post(
                "/v1/chat/completions",
                json=payload,
            )
            response.raise_for_status()

            result = response.json()

            logger.info(
                "Chat completion successful",
                model=model,
                usage=result.get("usage", {}),
            )

            return result

        except HTTPError as e:
            logger.error(
                "Chat completion failed",
                model=model,
                error=str(e),
                response_text=e.response.text if e.response else None,
            )
            raise

    async def get_models(self) -> dict[str, Any]:
        """Get available models from gateway.

        Returns:
            Models list response
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        try:
            response = await self._client.get("/v1/models")
            response.raise_for_status()
            return response.json()
        except HTTPError as e:
            logger.error("Failed to get models", error=str(e))
            raise

    async def domain_classify(
        self,
        text: str,
        domains: list[str] | None = None,
    ) -> dict[str, Any]:
        """Classify text domain using WrkHrs domain classifier.

        Args:
            text: Text to classify
            domains: Optional list of domains to consider

        Returns:
            Domain classification results
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        payload = {"text": text}
        if domains:
            payload["domains"] = domains

        try:
            response = await self._client.post(
                "/v1/classify/domain",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except HTTPError as e:
            logger.error("Domain classification failed", error=str(e))
            raise

    async def apply_conditioning(
        self,
        prompt: str,
        conditioning_type: str = "domain_weighting",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Apply non-generative conditioning to prompt.

        Args:
            prompt: Original prompt
            conditioning_type: Type of conditioning to apply
            **kwargs: Additional conditioning parameters

        Returns:
            Conditioned prompt and metadata
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        payload = {
            "prompt": prompt,
            "conditioning_type": conditioning_type,
        }
        payload.update(kwargs)

        try:
            response = await self._client.post(
                "/v1/conditioning/apply",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except HTTPError as e:
            logger.error("Conditioning application failed", error=str(e))
            raise











