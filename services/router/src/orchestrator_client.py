"""Client for WrkHrs Orchestrator with LangChain/LangGraph integration."""

from types import TracebackType
from typing import Any, cast

import structlog
from httpx import AsyncClient, HTTPError, HTTPStatusError

logger = structlog.get_logger()


class WrkHrsOrchestratorClient:
    """Async client for WrkHrs Orchestrator with LangChain/LangGraph workflows."""

    def __init__(
        self,
        base_url: str = "http://wrkhrs-orchestrator:8000",
        timeout: float = 120.0,
    ) -> None:
        """Initialize WrkHrs Orchestrator client.

        Args:
            base_url: Base URL for WrkHrs Orchestrator API
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: AsyncClient | None = None

    async def __aenter__(self) -> "WrkHrsOrchestratorClient":
        """Async context manager entry."""
        self._client = AsyncClient(
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
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def health_check(self) -> dict[str, Any]:
        """Check orchestrator health status.

        Returns:
            Health status response
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        try:
            response = await self._client.get("/health")
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except HTTPError as e:
            logger.error("Orchestrator health check failed", error=str(e))
            raise

    async def execute_workflow(
        self,
        workflow_name: str,
        input_data: dict[str, Any],
        workflow_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a LangGraph workflow.

        Args:
            workflow_name: Name of the workflow to execute
            input_data: Input data for the workflow
            workflow_config: Optional workflow configuration

        Returns:
            Workflow execution result
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        payload = {
            "workflow_name": workflow_name,
            "input_data": input_data,
        }

        if workflow_config:
            payload["workflow_config"] = workflow_config

        try:
            logger.info(
                "Executing workflow",
                workflow=workflow_name,
                input_keys=list(input_data.keys()),
            )

            response = await self._client.post(
                "/v1/workflows/execute",
                json=payload,
            )
            response.raise_for_status()

            result = cast(dict[str, Any], response.json())

            logger.info(
                "Workflow execution completed",
                workflow=workflow_name,
                status=result.get("status"),
                duration=result.get("duration"),
            )

            return result

        except HTTPError as e:
            response_text = (
                e.response.text
                if isinstance(e, HTTPStatusError) and e.response is not None
                else None
            )
            logger.error(
                "Workflow execution failed",
                workflow=workflow_name,
                error=str(e),
                response_text=response_text,
            )
            raise

    async def get_available_workflows(self) -> dict[str, Any]:
        """Get list of available workflows.

        Returns:
            Available workflows list
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        try:
            response = await self._client.get("/v1/workflows")
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except HTTPError as e:
            logger.error("Failed to get workflows", error=str(e))
            raise

    async def get_workflow_schema(
        self,
        workflow_name: str,
    ) -> dict[str, Any]:
        """Get workflow schema and input/output definitions.

        Args:
            workflow_name: Name of the workflow

        Returns:
            Workflow schema
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        try:
            response = await self._client.get(f"/v1/workflows/{workflow_name}/schema")
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except HTTPError as e:
            logger.error(
                "Failed to get workflow schema",
                workflow=workflow_name,
                error=str(e),
            )
            raise

    async def execute_rag_workflow(
        self,
        query: str,
        domain_weights: dict[str, float] | None = None,
        top_k: int = 6,
        min_score: float = 0.35,
    ) -> dict[str, Any]:
        """Execute RAG workflow with domain weighting.

        Args:
            query: Search query
            domain_weights: Optional domain weights for retrieval
            top_k: Number of documents to retrieve
            min_score: Minimum similarity score

        Returns:
            RAG workflow result
        """
        input_data = {
            "query": query,
            "top_k": top_k,
            "min_score": min_score,
        }

        if domain_weights:
            input_data["domain_weights"] = domain_weights

        return await self.execute_workflow("rag_retrieval", input_data)

    async def execute_tool_workflow(
        self,
        task: str,
        tools: list[str],
        tool_args: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Execute tool workflow with MCP tools.

        Args:
            task: Task description
            tools: List of tools to use
            tool_args: Optional tool-specific arguments

        Returns:
            Tool workflow result
        """
        input_data: dict[str, Any] = {
            "task": task,
            "tools": tools,
        }

        if tool_args:
            input_data["tool_args"] = tool_args

        return await self.execute_workflow("tool_execution", input_data)

    async def execute_github_workflow(
        self,
        prompt: str,
        repository: str | None = None,
        project: str | None = None,
    ) -> dict[str, Any]:
        """Execute GitHub workflow for code-related tasks.

        Args:
            prompt: User prompt
            repository: Optional repository name
            project: Optional project name

        Returns:
            GitHub workflow result
        """
        input_data = {
            "prompt": prompt,
        }

        if repository:
            input_data["repository"] = repository

        if project:
            input_data["project"] = project

        return await self.execute_workflow("github_integration", input_data)

    async def execute_policy_workflow(
        self,
        content: str,
        policies: list[str],
        policy_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute policy validation workflow.

        Args:
            content: Content to validate
            policies: List of policies to apply
            policy_config: Optional policy configuration

        Returns:
            Policy validation result
        """
        input_data: dict[str, Any] = {
            "content": content,
            "policies": policies,
        }

        if policy_config:
            input_data["policy_config"] = policy_config

        return await self.execute_workflow("policy_validation", input_data)

    async def get_workflow_status(
        self,
        workflow_id: str,
    ) -> dict[str, Any]:
        """Get status of a running workflow.

        Args:
            workflow_id: Workflow execution ID

        Returns:
            Workflow status
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        try:
            response = await self._client.get(f"/v1/workflows/{workflow_id}/status")
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except HTTPError as e:
            logger.error(
                "Failed to get workflow status",
                workflow_id=workflow_id,
                error=str(e),
            )
            raise

    async def cancel_workflow(
        self,
        workflow_id: str,
    ) -> dict[str, Any]:
        """Cancel a running workflow.

        Args:
            workflow_id: Workflow execution ID

        Returns:
            Cancellation result
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        try:
            response = await self._client.post(f"/v1/workflows/{workflow_id}/cancel")
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except HTTPError as e:
            logger.error(
                "Failed to cancel workflow",
                workflow_id=workflow_id,
                error=str(e),
            )
            raise
