"""HTTP client for the internal agent-platform execution backend."""

from __future__ import annotations

from typing import Literal

import httpx
from pydantic import BaseModel, Field

from .models import (
    ArtifactRecord,
    FileChangeRecord,
    PatchPlanRecord,
    RunPhase,
    RunRecord,
    TaskPlan,
    TaskState,
    VerificationResult,
    WorkspaceRecord,
)


class ExecutionBackendError(RuntimeError):
    """Raised when the internal execution backend cannot be reached or rejects a run."""

    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class CallbackConfig(BaseModel):
    """Callback URLs used by the execution backend to stream run updates."""

    events_url: str
    complete_url: str


class BackendRunCreateRequest(BaseModel):
    """Payload sent to the internal execution backend."""

    control_run_id: str
    task_id: str
    project_id: str
    engagement_mode: str | None = None
    engagement_mode_source: str | None = None
    engagement_mode_confidence: float | None = None
    engagement_mode_reasons: list[str] = Field(default_factory=list)
    minimum_engagement_mode: str | None = None
    pending_mode_change: dict[str, object] | None = None
    lifecycle_reason: str | None = None
    lifecycle_detail: dict[str, object] = Field(default_factory=dict)
    workspace: WorkspaceRecord
    plan: TaskPlan
    patch_plan: PatchPlanRecord | None = None
    task_packet_path: str | None = None
    callback: CallbackConfig


class BackendRunSnapshot(BaseModel):
    """Current execution-backend view of a dev-plane run."""

    run_id: str
    control_run_id: str
    status: Literal[
        "queued",
        "running",
        "blocked",
        "escalated",
        "ready_to_publish",
        "failed",
        "cancelled",
    ]
    phase: RunPhase | None = None
    summary: str | None = None
    files_changed: list[FileChangeRecord] = Field(default_factory=list)
    verification_results: list[VerificationResult] = Field(default_factory=list)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)

    def task_state(self) -> TaskState | None:
        """Return the task state represented by this snapshot, if any."""
        mapping = {
            "blocked": TaskState.BLOCKED,
            "escalated": TaskState.ESCALATED,
            "ready_to_publish": TaskState.READY_TO_PUBLISH,
            "failed": TaskState.FAILED,
            "cancelled": TaskState.CANCELLED,
        }
        return mapping.get(self.status)


class DevPlaneExecutionClient:
    """Async client for the agent-platform dev-plane execution endpoints."""

    def __init__(self, *, base_url: str, timeout: float = 300.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def start_run(
        self,
        *,
        run: RunRecord,
        plan: TaskPlan,
        patch_plan: PatchPlanRecord | None,
        callback_base_url: str,
        task_packet_path: str | None,
    ) -> BackendRunSnapshot:
        """Create and dispatch an internal execution run."""
        if run.workspace is None:
            raise ExecutionBackendError("Run has no provisioned workspace", status_code=409)
        payload = BackendRunCreateRequest(
            control_run_id=run.run_id,
            task_id=run.task_id,
            project_id=run.project_id,
            engagement_mode=run.engagement_mode,
            engagement_mode_source=run.engagement_mode_source,
            engagement_mode_confidence=run.engagement_mode_confidence,
            engagement_mode_reasons=run.engagement_mode_reasons,
            minimum_engagement_mode=run.minimum_engagement_mode,
            pending_mode_change=run.pending_mode_change,
            lifecycle_reason=run.lifecycle_reason,
            lifecycle_detail=run.lifecycle_detail,
            workspace=run.workspace,
            plan=plan,
            patch_plan=patch_plan,
            task_packet_path=task_packet_path,
            callback=CallbackConfig(
                events_url=f"{callback_base_url}/api/dev/runs/{run.run_id}/events",
                complete_url=f"{callback_base_url}/api/dev/runs/{run.run_id}/complete",
            ),
        )
        return await self._request(
            "POST",
            "/v1/devplane/runs",
            payload.model_dump(mode="json"),
        )

    async def get_run(self, backend_run_id: str) -> BackendRunSnapshot:
        """Fetch the latest execution-backend status for a run."""
        return await self._request(
            "GET",
            f"/v1/devplane/runs/{backend_run_id}",
            None,
        )

    async def cancel_run(self, backend_run_id: str) -> BackendRunSnapshot:
        """Request cancellation for an internal execution run."""
        return await self._request(
            "POST",
            f"/v1/devplane/runs/{backend_run_id}/cancel",
            {},
        )

    async def _request(
        self,
        method: str,
        path: str,
        payload: dict | None,
    ) -> BackendRunSnapshot:
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            ) as client:
                response = await client.request(method, path, json=payload)
        except httpx.HTTPError as exc:
            raise ExecutionBackendError(
                f"Execution backend request failed: {exc}"
            ) from exc

        if response.status_code >= 400:
            raise ExecutionBackendError(
                f"Execution backend error {response.status_code}: {response.text}",
                status_code=response.status_code,
            )

        return BackendRunSnapshot.model_validate(response.json())
