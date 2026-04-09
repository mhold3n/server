"""Typed contracts for the OpenClaw-first development plane."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


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
    BLOCKED = "blocked"
    ESCALATED = "escalated"
    READY_TO_PUBLISH = "ready_to_publish"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunPhase(StrEnum):
    """Execution phase updates emitted by an external operator/agent."""

    PLANNING = "planning"
    IMPLEMENTING = "implementing"
    VERIFYING = "verifying"
    BLOCKED = "blocked"
    ESCALATED = "escalated"
    READY_TO_PUBLISH = "ready_to_publish"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EngagementMode(StrEnum):
    """Ordered engagement strictness for routed work."""

    CASUAL_CHAT = "casual_chat"
    IDEATION = "ideation"
    NAPKIN_MATH = "napkin_math"
    ENGINEERING_TASK = "engineering_task"
    STRICT_ENGINEERING = "strict_engineering"


class EngagementModeSource(StrEnum):
    """How the current engagement mode was chosen."""

    EXPLICIT = "explicit"
    INFERRED = "inferred"
    RESUMED_SESSION = "resumed_session"
    CONFIRMED_DEESCALATION = "confirmed_deescalation"


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


class PendingModeChange(BaseModel):
    """Pending lower-strictness mode proposal awaiting explicit confirmation."""

    proposed_mode: EngagementMode
    reason: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)


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


class CostLedgerEntry(BaseModel):
    """Per-node / per-call token and cost accounting for budget-aware routing."""

    component: str = Field(..., min_length=1)
    model: str | None = None
    tokens_in: int | None = Field(default=None, ge=0)
    tokens_out: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    run_id: str | None = None
    task_packet_id: str | None = None
    timestamp: datetime = Field(default_factory=utc_now)


class MigrationStatus(StrEnum):
    """Legacy artifact disposition (migration gate)."""

    MIGRATED = "migrated"
    LEGACY_READONLY = "legacy_readonly"
    REJECTED = "rejected"


class LegacyMigrationMeta(BaseModel):
    """Required when persisting or reading legacy-shaped artifacts."""

    original_type: str = Field(..., min_length=1)
    original_version: str = Field(..., min_length=1)
    migration_status: MigrationStatus
    target_schema_id: str = Field(..., min_length=1)
    target_schema_version: str = Field(..., min_length=1)
    migration_timestamp: datetime = Field(default_factory=utc_now)
    migration_tool: str = Field(..., min_length=1)
    migration_tool_version: str = Field(..., min_length=1)
    lossy_migration: bool = False
    review_needed: bool = False


class ArtifactRecord(BaseModel):
    """Artifacts emitted by the task or run.

    Either **legacy** shape (name, path, kind) or **typed** control-plane envelope
    (artifact_id, artifact_type, schema_version, ...). Typed writes on canonical paths
    must pass JSON Schema + lifecycle gates.
    """

    name: str = ""
    path: str = ""
    kind: str = ""
    description: str | None = None
    # --- Typed control-plane fields (optional) ---
    artifact_id: str | None = None
    artifact_type: str | None = None
    schema_version: str | None = None
    artifact_status: str | None = None
    validation_state: str | None = None
    producer: dict[str, Any] | None = None
    input_artifact_refs: list[str] = Field(default_factory=list)
    supersedes: list[str] = Field(default_factory=list)
    invalid_reasons: list[str] = Field(default_factory=list)
    payload: dict[str, Any] | None = None
    migration: LegacyMigrationMeta | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @model_validator(mode="after")
    def _legacy_or_typed(self) -> ArtifactRecord:
        typed = self.artifact_id is not None
        legacy = bool(self.name and self.path and self.kind)
        if typed:
            if not self.artifact_type or not self.schema_version:
                raise ValueError(
                    "typed artifact requires artifact_type and schema_version",
                )
        elif legacy:
            return self
        elif not self.name and not self.path and not self.kind and not typed:
            raise ValueError(
                "ArtifactRecord requires legacy fields (name, path, kind) or typed artifact_id",
            )
        else:
            raise ValueError(
                "ArtifactRecord: incomplete legacy or typed fields",
            )
        return self


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


class EngineeringSessionRecord(BaseModel):
    """Durable strict-engineering session state backed by DevPlane records."""

    engineering_session_id: str
    origin: str = "chat_strict_engineering"
    promotion_reason: str | None = None
    run_id: str | None = None
    status: str = "pending"
    engagement_mode: EngagementMode = EngagementMode.STRICT_ENGINEERING
    engagement_mode_source: EngagementModeSource | None = None
    engagement_mode_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    engagement_mode_reasons: list[str] = Field(default_factory=list)
    minimum_engagement_mode: EngagementMode | None = None
    pending_mode_change: PendingModeChange | None = None
    lifecycle_reason: str | None = None
    lifecycle_detail: dict[str, Any] = Field(default_factory=dict)
    problem_brief: dict[str, Any] | None = None
    problem_brief_ref: str | None = None
    knowledge_pool_assessment: dict[str, Any] | None = None
    knowledge_pool_assessment_ref: str | None = None
    knowledge_pool_coverage: str | None = None
    knowledge_candidate_refs: list[str] = Field(default_factory=list)
    knowledge_role_context_refs: list[str] = Field(default_factory=list)
    knowledge_gaps: list[str] = Field(default_factory=list)
    knowledge_required: bool = False
    engineering_state: dict[str, Any] | None = None
    engineering_state_ref: str | None = None
    task_queue: dict[str, Any] | None = None
    task_packets: list[dict[str, Any]] = Field(default_factory=list)
    active_task_packet: dict[str, Any] | None = None
    active_task_packet_ref: str | None = None
    active_selected_executor: str | None = None
    clarification_questions: list[str] = Field(default_factory=list)
    required_gates: list[dict[str, Any]] = Field(default_factory=list)
    verification_outcome: str | None = None
    verification_report: dict[str, Any] | None = None
    verification_report_ref: str | None = None
    escalation_packet: dict[str, Any] | None = None
    escalation_packet_ref: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class TaskDossier(BaseModel):
    """The final dossier and running audit log for a task."""

    task_id: str
    project_id: str
    state: TaskState
    engagement_mode: EngagementMode = EngagementMode.ENGINEERING_TASK
    engagement_mode_source: EngagementModeSource | None = None
    engagement_mode_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    engagement_mode_reasons: list[str] = Field(default_factory=list)
    minimum_engagement_mode: EngagementMode | None = None
    pending_mode_change: PendingModeChange | None = None
    lifecycle_reason: str | None = None
    lifecycle_detail: dict[str, Any] = Field(default_factory=dict)
    knowledge_pool_assessment_ref: str | None = None
    knowledge_pool_coverage: str | None = None
    knowledge_candidate_refs: list[str] = Field(default_factory=list)
    knowledge_role_context_refs: list[str] = Field(default_factory=list)
    knowledge_gaps: list[str] = Field(default_factory=list)
    knowledge_required: bool = False
    reasoning_tier: str | None = Field(
        default=None,
        description=(
            "Execution routing tier for the task (e.g. 'local_worker', 'hosted_api_brain'). "
            "This is informational and can be used by operators to understand escalation."
        ),
    )
    request: TaskRequestRecord
    clarifications: TaskClarification = Field(default_factory=TaskClarification)
    engineering_session: EngineeringSessionRecord | None = None
    plan: TaskPlan | None = None
    patch_plan: PatchPlanRecord | None = None
    workspace: WorkspaceRecord | None = None
    run_ids: list[str] = Field(default_factory=list)
    logs: list[RunLogEntry] = Field(default_factory=list)
    commands: list[CommandExecution] = Field(default_factory=list)
    files_changed: list[FileChangeRecord] = Field(default_factory=list)
    verification_results: list[VerificationResult] = Field(default_factory=list)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    typed_artifacts: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Serialized TypedArtifactRecord payloads for control-plane registry.",
    )
    cost_ledger: list[CostLedgerEntry] = Field(
        default_factory=list,
        description="Cumulative token/cost usage for budget-aware routing.",
    )
    escalation_packets: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Compressed evidence packets produced during local-first execution "
            "and optionally sent to a hosted API brain for planning/review."
        ),
    )
    api_brain_verdict: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Latest structured PLAN/REVIEW/DECISION/PATCH_GUIDANCE response from the hosted API brain."
        ),
    )
    publish_result: PublishResult | None = None
    final_outcome: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class TaskRecord(BaseModel):
    """Top-level persisted task state."""

    task_id: str
    project_id: str
    state: TaskState
    engagement_mode: EngagementMode = EngagementMode.ENGINEERING_TASK
    engagement_mode_source: EngagementModeSource | None = None
    engagement_mode_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    engagement_mode_reasons: list[str] = Field(default_factory=list)
    minimum_engagement_mode: EngagementMode | None = None
    pending_mode_change: PendingModeChange | None = None
    lifecycle_reason: str | None = None
    lifecycle_detail: dict[str, Any] = Field(default_factory=dict)
    knowledge_pool_assessment_ref: str | None = None
    knowledge_pool_coverage: str | None = None
    knowledge_candidate_refs: list[str] = Field(default_factory=list)
    knowledge_role_context_refs: list[str] = Field(default_factory=list)
    knowledge_gaps: list[str] = Field(default_factory=list)
    knowledge_required: bool = False
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
    engagement_mode: EngagementMode = EngagementMode.ENGINEERING_TASK
    engagement_mode_source: EngagementModeSource | None = None
    engagement_mode_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    engagement_mode_reasons: list[str] = Field(default_factory=list)
    minimum_engagement_mode: EngagementMode | None = None
    pending_mode_change: PendingModeChange | None = None
    lifecycle_reason: str | None = None
    lifecycle_detail: dict[str, Any] = Field(default_factory=dict)
    knowledge_pool_assessment_ref: str | None = None
    knowledge_pool_coverage: str | None = None
    knowledge_candidate_refs: list[str] = Field(default_factory=list)
    knowledge_role_context_refs: list[str] = Field(default_factory=list)
    knowledge_gaps: list[str] = Field(default_factory=list)
    knowledge_required: bool = False
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
    cost_ledger: list[CostLedgerEntry] = Field(default_factory=list)
    publish_result: PublishResult | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None


class TaskCreateRequest(BaseModel):
    """Public task submission API request."""

    project_id: str
    user_intent: str = Field(..., min_length=1)
    engagement_mode: EngagementMode = EngagementMode.ENGINEERING_TASK
    repo_ref_hint: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    risk_hints: list[str] = Field(default_factory=list)


class TaskRunLaunchRequest(BaseModel):
    """Launch or resume a task execution run."""

    execution_mode: ExecutionMode = ExecutionMode.INTERNAL
    engagement_mode: EngagementMode | None = None
    agent_session_id: str | None = None
    force_new_run: bool = False


class RunEventRequest(BaseModel):
    """Run event update from an external operator or agent session."""

    phase: RunPhase | None = None
    status: TaskState | None = None
    engagement_mode: EngagementMode | None = None
    engagement_mode_source: EngagementModeSource | None = None
    engagement_mode_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    engagement_mode_reasons: list[str] = Field(default_factory=list)
    minimum_engagement_mode: EngagementMode | None = None
    pending_mode_change: PendingModeChange | None = None
    lifecycle_reason: str | None = None
    lifecycle_detail: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None
    level: str = "info"
    details: dict[str, Any] = Field(default_factory=dict)
    commands: list[CommandExecution] = Field(default_factory=list)
    files_changed: list[FileChangeRecord] = Field(default_factory=list)
    verification_results: list[VerificationResult] = Field(default_factory=list)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    cost_ledger: list[CostLedgerEntry] = Field(default_factory=list)


class RunCompleteRequest(BaseModel):
    """Mark a run complete, failed, or cancelled."""

    status: TaskState
    summary: str | None = None
    phase: RunPhase | None = None
    lifecycle_reason: str | None = None
    lifecycle_detail: dict[str, Any] = Field(default_factory=dict)
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
