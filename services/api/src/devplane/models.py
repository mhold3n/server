"""Typed contracts for the OpenClaw-first development plane."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return a timezone-naive UTC timestamp compatible with existing models."""
    return datetime.now(UTC)


class TaskState(StrEnum):
    """Stable task lifecycle states exposed by the control API."""

    PENDING_CLARIFICATION = "pending_clarification"
    READY = "ready"
    PLANNING = "planning"
    IMPLEMENTING = "implementing"
    VERIFYING = "verifying"
    READY_TO_PUBLISH = "ready_to_publish"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunPhase(StrEnum):
    """Execution phase updates emitted by an external operator/agent."""

    PLANNING = "planning"
    IMPLEMENTING = "implementing"
    VERIFYING = "verifying"
    READY_TO_PUBLISH = "ready_to_publish"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VerificationStatus(StrEnum):
    """Verification result status."""

    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ExecutionMode(StrEnum):
    """How a task run is executed."""

    INTERNAL = "internal"
    EXTERNAL = "external"


class PublishMode(StrEnum):
    """Publish delivery mode."""

    LOCAL = "local"
    REMOTE = "remote"


class FileChangeType(StrEnum):
    """Normalized file change status."""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"
    UNTRACKED = "untracked"
    UNKNOWN = "unknown"


class ProjectGithubSettings(BaseModel):
    """Resolved GitHub metadata for a registered project."""

    owner: str | None = None
    repo: str | None = None
    default_pr_base: str | None = None


class ProjectCreateRequest(BaseModel):
    """Project registration request."""

    name: str = Field(..., min_length=1)
    canonical_repo_path: str = Field(..., min_length=1)
    default_branch: str | None = None
    remote_name: str = Field(default="origin", min_length=1)
    github_owner: str | None = None
    github_repo: str | None = None


class ProjectRecord(BaseModel):
    """Canonical project registry record."""

    project_id: str
    name: str
    canonical_repo_path: str
    default_branch: str
    remote_name: str = "origin"
    remote_url: str | None = None
    workspace_root: str
    github: ProjectGithubSettings = Field(default_factory=ProjectGithubSettings)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ClarificationQuestion(BaseModel):
    """A structured clarification question for incomplete task intent."""

    question_id: str
    prompt: str
    field: str
    required: bool = True


class ClarificationAnswer(BaseModel):
    """User answer to a clarification question."""

    question_id: str
    answer: str = Field(..., min_length=1)


class PublishIntent(BaseModel):
    """Publish preferences carried in the task plan."""

    mode: str = "branch_pr_dossier"
    push: bool = True
    create_pr: bool = True
    remote_name: str = "origin"


class TaskPlan(BaseModel):
    """Canonical normalized implementation plan for a code task."""

    project_id: str
    objective: str
    constraints: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    implementation_outline: list[str] = Field(default_factory=list)
    verification_plan: list[str] = Field(default_factory=list)
    delegation_hints: list[str] = Field(default_factory=list)
    work_items: list[str] = Field(default_factory=list)
    verification_blocks: list[VerificationBlock] = Field(default_factory=list)
    publish_intent: PublishIntent = Field(default_factory=PublishIntent)
    repo_ref_hint: str | None = None
    planned_branch: str | None = None


class PatchOperation(BaseModel):
    """A planned file operation for the task."""

    file_path: str
    operation: str
    summary: str | None = None
    requires_approval: bool = False


class PatchPlanRecord(BaseModel):
    """Intermediate patch plan retained in the task dossier."""

    plan_id: str = Field(default_factory=lambda: str(uuid4()))
    patches: list[PatchOperation] = Field(default_factory=list)
    validation_status: str = "pending"


class WorkspaceRecord(BaseModel):
    """Isolated task workspace metadata."""

    canonical_repo_path: str
    worktree_path: str
    branch_name: str
    base_branch: str
    remote_name: str = "origin"
    created_at: datetime = Field(default_factory=utc_now)


class RunLogEntry(BaseModel):
    """Structured run log entry."""

    timestamp: datetime = Field(default_factory=utc_now)
    phase: RunPhase | None = None
    level: str = "info"
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class CommandExecution(BaseModel):
    """Command invocation recorded in a run dossier."""

    timestamp: datetime = Field(default_factory=utc_now)
    command: str
    cwd: str
    exit_code: int | None = None
    stdout_excerpt: str | None = None
    stderr_excerpt: str | None = None
    source: str = "control_plane"


class FileChangeRecord(BaseModel):
    """Tracked file change for a task workspace."""

    path: str
    change_type: FileChangeType = FileChangeType.UNKNOWN
    git_status: str | None = None


class VerificationResult(BaseModel):
    """A verification command result."""

    timestamp: datetime = Field(default_factory=utc_now)
    name: str
    command: str | None = None
    status: VerificationStatus = VerificationStatus.PENDING
    exit_code: int | None = None
    stdout_excerpt: str | None = None
    stderr_excerpt: str | None = None


class VerificationBlock(BaseModel):
    """Explicit verification command block carried in the task plan."""

    name: str
    command: str
    required: bool = True


class ArtifactRecord(BaseModel):
    """Artifacts emitted by the task or run."""

    name: str
    path: str
    kind: str
    description: str | None = None


class PublishResult(BaseModel):
    """Publish outcome for a completed task."""

    timestamp: datetime = Field(default_factory=utc_now)
    mode: PublishMode = PublishMode.LOCAL
    branch_name: str
    remote_name: str = "origin"
    commit_sha: str | None = None
    pushed: bool = False
    pr_url: str | None = None
    review_status: str | None = None
    errors: list[str] = Field(default_factory=list)


class TaskRequestRecord(BaseModel):
    """Persisted user task request."""

    task_id: str
    project_id: str
    user_intent: str
    repo_ref_hint: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    risk_hints: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class TaskClarification(BaseModel):
    """Clarification state for a task."""

    questions: list[ClarificationQuestion] = Field(default_factory=list)
    answers: list[ClarificationAnswer] = Field(default_factory=list)


class TaskDossier(BaseModel):
    """The final dossier and running audit log for a task."""

    task_id: str
    project_id: str
    state: TaskState
    request: TaskRequestRecord
    clarifications: TaskClarification = Field(default_factory=TaskClarification)
    plan: TaskPlan | None = None
    patch_plan: PatchPlanRecord | None = None
    workspace: WorkspaceRecord | None = None
    run_ids: list[str] = Field(default_factory=list)
    logs: list[RunLogEntry] = Field(default_factory=list)
    commands: list[CommandExecution] = Field(default_factory=list)
    files_changed: list[FileChangeRecord] = Field(default_factory=list)
    verification_results: list[VerificationResult] = Field(default_factory=list)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    publish_result: PublishResult | None = None
    final_outcome: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class TaskRecord(BaseModel):
    """Top-level persisted task state."""

    task_id: str
    project_id: str
    state: TaskState
    request: TaskRequestRecord
    clarifications: TaskClarification = Field(default_factory=TaskClarification)
    plan: TaskPlan | None = None
    patch_plan: PatchPlanRecord | None = None
    dossier: TaskDossier
    current_run_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RunRecord(BaseModel):
    """Persisted execution run for a task workspace."""

    run_id: str
    task_id: str
    project_id: str
    phase: RunPhase = RunPhase.PLANNING
    workspace: WorkspaceRecord | None = None
    execution_mode: ExecutionMode = ExecutionMode.INTERNAL
    execution_backend: str | None = None
    backend_run_id: str | None = None
    agent_session_id: str | None = None
    logs: list[RunLogEntry] = Field(default_factory=list)
    commands: list[CommandExecution] = Field(default_factory=list)
    files_changed: list[FileChangeRecord] = Field(default_factory=list)
    verification_results: list[VerificationResult] = Field(default_factory=list)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    publish_result: PublishResult | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None


class TaskCreateRequest(BaseModel):
    """Public task submission API request."""

    project_id: str
    user_intent: str = Field(..., min_length=1)
    repo_ref_hint: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    risk_hints: list[str] = Field(default_factory=list)


class TaskRunLaunchRequest(BaseModel):
    """Launch or resume a task execution run."""

    execution_mode: ExecutionMode = ExecutionMode.INTERNAL
    agent_session_id: str | None = None
    force_new_run: bool = False


class RunEventRequest(BaseModel):
    """Run event update from an external operator or agent session."""

    phase: RunPhase | None = None
    message: str | None = None
    level: str = "info"
    details: dict[str, Any] = Field(default_factory=dict)
    commands: list[CommandExecution] = Field(default_factory=list)
    files_changed: list[FileChangeRecord] = Field(default_factory=list)
    verification_results: list[VerificationResult] = Field(default_factory=list)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)


class RunCompleteRequest(BaseModel):
    """Mark a run complete, failed, or cancelled."""

    status: TaskState
    summary: str | None = None
    phase: RunPhase | None = None
    files_changed: list[FileChangeRecord] = Field(default_factory=list)
    verification_results: list[VerificationResult] = Field(default_factory=list)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)


class PublishRequest(BaseModel):
    """Publish a task branch and optionally create a PR."""

    commit_message: str | None = None
    push: bool = True
    create_pr: bool = True
    pr_title: str | None = None
    pr_body: str | None = None
    remote_name: str = "origin"
