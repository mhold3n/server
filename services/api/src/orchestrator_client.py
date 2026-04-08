"""Async client for the LangGraph-based agent platform orchestrator.

This module defines the **canonical** contract that the API control plane uses
to talk to the TypeScript `agent-platform` service. All orchestration that
should flow through LangGraph must go through this client so that agents and
humans have a single place to reason about request/response shapes, routing
behaviour, and error semantics.

The underlying HTTP server is implemented in `services/agent-platform/server`,
which currently exposes `/health`, `/v1/workflows`, and `/v1/workflows/execute`.

This client intentionally does **not** know anything about local-vs-hosted
provider details; those decisions live behind the LangGraph workflows and
their configuration. From the API's perspective, this is a generic workflow
executor that takes a workflow name and a JSON-serialisable input payload.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, cast

import httpx

from .config import settings


class OrchestratorClient:
    """Async client for the LangGraph orchestrator.

    The base URL normally points at the WrkHrs agent-platform service
    (for example `http://wrkhrs-agent-platform:8000` in docker-compose),
    but the exact address is provided by `settings.agent_platform_url`
    so that tests and alternative deployments can override it.

    This client is designed to be used as an async context manager to
    avoid leaking HTTP connections.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        resolved = base_url or getattr(
            settings,
            "agent_platform_url",
            "http://wrkhrs-agent-platform:8000",
        )
        self.base_url = resolved.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "OrchestratorClient":
        """Open the underlying HTTP client for this context."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Close the underlying HTTP client when the context exits."""
        if self._client:
            await self._client.aclose()

    async def execute_workflow(
        self,
        workflow_name: str,
        input_data: dict[str, Any],
        workflow_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a LangGraph workflow by name.

        Args:
            workflow_name: Name of the workflow to execute (for example
                ``\"wrkhrs_chat\"``, ``\"rag_retrieval\"``, or
                ``\"devplane_code_task\"``). The set of valid names is owned
                by the agent-platform service.
            input_data: JSON-serialisable payload that the workflow expects
                as its input.
            workflow_config: Optional configuration dictionary for workflows
                that support additional tuning.

        Returns:
            The JSON response from `/v1/workflows/execute` as a plain dict.

        Raises:
            httpx.HTTPError: If the underlying HTTP request fails or the
                orchestrator returns a non-2xx status code.
        """
        if not self._client:
            raise RuntimeError(
                "Client not initialized. Use OrchestratorClient as an async context manager.",
            )

        payload: dict[str, Any] = {
            "workflow_name": workflow_name,
            "input_data": input_data,
        }
        # Fail-closed defaults: hosted escalation is opt-in per workflow run.
        merged_config: dict[str, Any] = {}
        if workflow_config:
            merged_config.update(workflow_config)
        merged_config.setdefault("allow_api_brain", False)
        merged_config.setdefault("escalation_budget", 0)
        payload["workflow_config"] = merged_config

        response = await self._client.post("/v1/workflows/execute", json=payload)
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

