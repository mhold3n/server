"""
Pydantic mirrors of control-plane JSON contracts (task_packet, budgets, routing).

For agents: keep field names aligned with JSON Schemas under `schemas/control-plane/v1/`.
Authoritative shapes are the `.schema.json` files; this module adds runtime invariants.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class TaskPacketStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskType(StrEnum):
    CODEGEN = "CODEGEN"
    TRANSFORM = "TRANSFORM"
    VALIDATION_CODE = "VALIDATION_CODE"
    MULTIMODAL_EXTRACTION = "MULTIMODAL_EXTRACTION"
    RESEARCH_SYNTHESIS = "RESEARCH_SYNTHESIS"
    VALIDATION = "VALIDATION"
    ESCALATION_REVIEW = "ESCALATION_REVIEW"


class Priority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Executor(StrEnum):
    LOCAL_GENERAL_MODEL = "local_general_model"
    CODING_MODEL = "coding_model"
    MULTIMODAL_MODEL = "multimodal_model"
    STRATEGIC_REVIEWER = "strategic_reviewer"
    DETERMINISTIC_VALIDATOR = "deterministic_validator"


class ArtifactType(StrEnum):
    PROBLEM_BRIEF = "PROBLEM_BRIEF"
    REQUIREMENTS_SET = "REQUIREMENTS_SET"
    CONSTRAINTS_REGISTER = "CONSTRAINTS_REGISTER"
    ASSUMPTIONS_REGISTER = "ASSUMPTIONS_REGISTER"
    RESEARCH_DIGEST = "RESEARCH_DIGEST"
    CLAIMS_REGISTRY = "CLAIMS_REGISTRY"
    SOURCE_INDEX = "SOURCE_INDEX"
    DOCUMENT_EXTRACT = "DOCUMENT_EXTRACT"
    VARIABLES_REGISTER = "VARIABLES_REGISTER"
    BOUNDARY_CONDITIONS = "BOUNDARY_CONDITIONS"
    CANDIDATE_MODELS = "CANDIDATE_MODELS"
    ANALYSIS_PLAN = "ANALYSIS_PLAN"
    DOE_PLAN = "DOE_PLAN"
    TASK_PACKET = "TASK_PACKET"
    CODE_PATCH = "CODE_PATCH"
    PARSER_OUTPUT = "PARSER_OUTPUT"
    SIMULATION_RESULT = "SIMULATION_RESULT"
    VERIFICATION_REPORT = "VERIFICATION_REPORT"
    DECISION_LOG = "DECISION_LOG"
    COST_LOG = "COST_LOG"
    ESCALATION_RECORD = "ESCALATION_RECORD"
    APPROVAL_RECORD = "APPROVAL_RECORD"
    ENGINEERING_STATE = "ENGINEERING_STATE"
    TASK_QUEUE = "TASK_QUEUE"
    ROUTING_POLICY = "ROUTING_POLICY"


class Scope(BaseModel):
    included: list[str] = Field(default_factory=list)
    excluded: list[str] = Field(default_factory=list)


class RequiredOutputSpec(BaseModel):
    artifact_type: ArtifactType
    schema_version: str = Field(..., pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")


class BudgetPolicy(BaseModel):
    allow_escalation: bool
    max_tokens: int | None = Field(default=None, ge=0)
    max_cost_usd: float | None = Field(default=None, ge=0)


class RoutingMetadata(BaseModel):
    requested_by: str = Field(..., min_length=1)
    selected_executor: Executor
    reason: str = Field(..., min_length=1)
    router_policy_version: str = Field(..., min_length=1)


class Provenance(BaseModel):
    source_stage: str = Field(..., min_length=1)
    parent_task_packet_id: str | None = None
    decision_log_ref: str | None = None


class TaskPacket(BaseModel):
    """Specialist execution contract."""

    task_packet_id: UUID
    schema_version: str = Field(default="1.0.0", pattern=r"^1\.0\.0$")
    status: TaskPacketStatus
    task_type: TaskType
    title: str = Field(..., min_length=1)
    objective: str = Field(..., min_length=1)
    scope: Scope | None = None
    input_artifact_refs: list[str] = Field(..., min_length=1)
    context_summary: str | None = None
    constraints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    required_outputs: list[RequiredOutputSpec] = Field(..., min_length=1)
    acceptance_criteria: list[str] = Field(..., min_length=1)
    validation_requirements: list[str] = Field(default_factory=list)
    priority: Priority | None = None
    budget_policy: BudgetPolicy
    routing_metadata: RoutingMetadata
    provenance: Provenance
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _invariants(self) -> TaskPacket:
        """Runtime invariants beyond JSON Schema (consumer conformance)."""
        if self.task_type is TaskType.ESCALATION_REVIEW and not self.budget_policy.allow_escalation:
            raise ValueError("ESCALATION_REVIEW requires budget_policy.allow_escalation=true")
        if self.task_type is TaskType.VALIDATION and len(self.validation_requirements) < 1:
            raise ValueError("VALIDATION requires non-empty validation_requirements")
        return self


class ArtifactStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"
    ARCHIVED = "ARCHIVED"


class ArtifactValidationState(StrEnum):
    PENDING = "PENDING"
    VALID = "VALID"
    INVALID = "INVALID"
    WAIVED = "WAIVED"


class Producer(BaseModel):
    component: str = Field(..., min_length=1)
    executor: str = Field(..., min_length=1)
    run_id: str | None = None
    task_packet_id: str | None = None


class TypedArtifactRecord(BaseModel):
    """Envelope for DevPlane-persisted typed artifacts."""

    artifact_id: UUID
    artifact_type: ArtifactType
    schema_version: str = Field(..., pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    status: ArtifactStatus
    validation_state: ArtifactValidationState
    producer: Producer
    input_artifact_refs: list[str] = Field(default_factory=list)
    supersedes: list[str] = Field(default_factory=list)
    invalid_reasons: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def _artifact_invariants(self) -> TypedArtifactRecord:
        if self.status is ArtifactStatus.SUPERSEDED and not self.supersedes:
            raise ValueError("SUPERSEDED requires non-empty supersedes")
        if self.validation_state is ArtifactValidationState.INVALID and not self.invalid_reasons:
            raise ValueError("INVALID requires non-empty invalid_reasons")
        return self


class VerificationOutcome(StrEnum):
    PASS = "PASS"
    REWORK = "REWORK"
    ESCALATE = "ESCALATE"


class VerificationFinding(BaseModel):
    code: str = Field(..., min_length=1)
    severity: str = Field(..., pattern=r"^(low|medium|high|critical)$")
    artifact_ref: str | None = None


class GateKind(StrEnum):
    SCHEMA = "schema"
    UNITS = "units"
    NUMERIC_SANITY = "numeric_sanity"
    TESTS = "tests"
    CITATIONS = "citations"
    POLICY = "policy"
    SIMULATION = "simulation"
    CUSTOM = "custom"


class GateResultStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    ERROR = "ERROR"


class VerificationGateResult(BaseModel):
    """Single gate row in verification_report.gate_results (auditable checklist)."""

    gate_id: str = Field(..., min_length=1)
    gate_kind: GateKind
    status: GateResultStatus
    detail: str | None = None
    remediation_hint: str | None = None
    artifact_ref: str | None = None


class VerificationReportPayload(BaseModel):
    verification_report_id: UUID
    schema_version: str = Field(default="1.0.0", pattern=r"^1\.0\.0$")
    outcome: VerificationOutcome
    reasons: list[str] = Field(default_factory=list)
    blocking_findings: list[VerificationFinding] = Field(default_factory=list)
    gate_results: list[VerificationGateResult] = Field(default_factory=list)
    recommended_next_action: str = Field(..., min_length=1)
    suggested_executor: Executor | None = None
    validated_artifact_refs: list[str] = Field(..., min_length=1)
    source_task_packet_id: UUID | None = None
    created_at: datetime

    @model_validator(mode="after")
    def _verification_invariants(self) -> VerificationReportPayload:
        if self.outcome in (VerificationOutcome.REWORK, VerificationOutcome.ESCALATE):
            if not self.blocking_findings:
                raise ValueError("REWORK/ESCALATE requires blocking_findings")
        if self.outcome is VerificationOutcome.ESCALATE:
            if self.recommended_next_action != "create_escalation_packet":
                raise ValueError("ESCALATE requires recommended_next_action=create_escalation_packet")
        return self


class EscalationReason(StrEnum):
    AMBIGUITY = "AMBIGUITY"
    CONFLICT = "CONFLICT"
    COMPLEXITY = "COMPLEXITY"
    HIGH_IMPACT_REVIEW = "HIGH_IMPACT_REVIEW"


class EscalationPacket(BaseModel):
    escalation_packet_id: UUID
    schema_version: str = Field(default="1.0.0", pattern=r"^1\.0\.0$")
    reason: EscalationReason
    unresolved_items: list[str] = Field(..., min_length=1)
    supporting_artifact_refs: list[str] = Field(..., min_length=1)
    compressed_state_ref: str = Field(..., min_length=1)
    requested_by: str = Field(..., min_length=1)
    parent_verification_report_id: UUID | None = None
    created_at: datetime


# --- problem_brief (see problem-brief.schema.json) ---


class QuantifiedScalar(BaseModel):
    value: float
    unit: str = Field(..., min_length=1)


class EnvelopeBound(BaseModel):
    name: str = Field(..., min_length=1)
    min: QuantifiedScalar | None = None
    max: QuantifiedScalar | None = None
    nominal: QuantifiedScalar | None = None


class OperatingEnvelope(BaseModel):
    unit_system: str | None = None
    notes: str | None = None
    bounds: list[EnvelopeBound] = Field(default_factory=list)


class EngineeringObjective(BaseModel):
    id: str = Field(..., min_length=1)
    statement: str = Field(..., min_length=1)
    priority: Priority | None = None


class RequiredDeliverable(BaseModel):
    id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    artifact_type_hint: ArtifactType | None = None


class AcceptanceTestSpec(BaseModel):
    id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    kind: str = Field(
        ...,
        pattern=r"^(manual|automated|simulation|inspection)$",
    )
    criteria_ref: str | None = None


class EvidenceExpectation(BaseModel):
    kind: str = Field(
        ...,
        pattern=r"^(document|drawing|codebase|standard|measurement|other)$",
    )
    notes: str | None = None


class HumanApprovalGate(BaseModel):
    gate_id: str = Field(..., min_length=1)
    rationale: str | None = None


class HumanApprovalBlock(BaseModel):
    required_before_execution: bool = False
    gates: list[HumanApprovalGate] = Field(default_factory=list)


class ProblemBriefProvenance(BaseModel):
    source_stage: str = Field(..., min_length=1)
    producer: Producer
    input_digest_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    parent_trace_id: str | None = None
    raw_intent_artifact_ref: str | None = Field(
        default=None,
        pattern=r"^artifact://.+",
    )


class ProblemBrief(BaseModel):
    """Root intent artifact produced at Stage 0 (intent capture)."""

    problem_brief_id: UUID
    schema_version: str = Field(..., pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    trace_id: str | None = Field(default=None, min_length=8)
    title: str = Field(..., min_length=1)
    summary: str = ""
    system_purpose: str = Field(..., min_length=1)
    scope: Scope | None = None
    engineering_objectives: list[EngineeringObjective] = Field(..., min_length=1)
    operating_envelope: OperatingEnvelope | None = None
    assumptions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    required_deliverables: list[RequiredDeliverable] = Field(..., min_length=1)
    acceptance_tests: list[AcceptanceTestSpec] = Field(..., min_length=1)
    evidence_expectations: list[EvidenceExpectation] = Field(default_factory=list)
    human_approval: HumanApprovalBlock | None = None
    provenance: ProblemBriefProvenance
    created_at: datetime
    updated_at: datetime


# --- task_queue (see task-queue.schema.json) ---


class QueueStatus(StrEnum):
    OPEN = "OPEN"
    DRAINING = "DRAINING"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class TaskQueueApproval(BaseModel):
    required: bool
    status: str = Field(
        ...,
        pattern=r"^(PENDING|APPROVED|REJECTED|WAIVED)$",
    )
    approver: str | None = None
    decided_at: datetime | None = None


class TaskQueueItem(BaseModel):
    order_hint: int | None = None
    task_packet_ref: str = Field(..., min_length=1, pattern=r"^artifact://.+")
    depends_on: list[str] = Field(default_factory=list)
    approval: TaskQueueApproval
    aggregate_budget: BudgetPolicy | None = None


class TaskQueue(BaseModel):
    """Ordered DAG of task_packet refs with optional per-row approvals."""

    task_queue_id: UUID
    schema_version: str = Field(..., pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    trace_id: str | None = Field(default=None, min_length=8)
    problem_brief_ref: str = Field(..., min_length=1, pattern=r"^artifact://.+")
    engineering_state_ref: str | None = Field(
        default=None,
        pattern=r"^artifact://.+",
    )
    merge_policy_version: str | None = None
    queue_status: QueueStatus
    items: list[TaskQueueItem] = Field(default_factory=list)
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


# --- engineering_state (see engineering-state.schema.json) ---


class StateVariable(BaseModel):
    id: str = Field(..., min_length=1)
    description: str = ""
    unit: str | None = None
    bounds: dict[str, float] | None = None
    source_artifact_ref: str | None = Field(default=None, pattern=r"^artifact://.+")


class StateConstraint(BaseModel):
    id: str = Field(..., min_length=1)
    statement: str = ""
    kind: str | None = Field(
        default=None,
        pattern=r"^(physical|geometric|regulatory|economic|other)$",
    )
    source_artifact_ref: str | None = Field(default=None, pattern=r"^artifact://.+")


class UnknownItem(BaseModel):
    id: str = Field(..., min_length=1)
    description: str = ""
    blocking: bool | None = None


class MechanismCandidate(BaseModel):
    id: str = Field(..., min_length=1)
    name: str = ""
    notes: str | None = None


class AnalysisPathway(BaseModel):
    id: str = Field(..., min_length=1)
    summary: str = ""


class ConflictRecord(BaseModel):
    conflict_id: str = Field(..., min_length=1)
    description: str = ""
    severity: str | None = Field(default=None, pattern=r"^(low|medium|high|critical)$")
    involved_artifact_refs: list[str] = Field(..., min_length=1)
    resolution_status: str = Field(
        ...,
        pattern=r"^(open|escalated|resolved|waived)$",
    )
    resolution_notes: str | None = None


class StalenessRecord(BaseModel):
    artifact_ref: str = Field(..., min_length=1, pattern=r"^artifact://.+")
    invalid_after: datetime | None = None
    reason: str = ""


class EngineeringState(BaseModel):
    """Canonical merged technical state for routing and decomposition."""

    engineering_state_id: UUID
    schema_version: str = Field(..., pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    trace_id: str | None = Field(default=None, min_length=8)
    problem_brief_ref: str = Field(..., min_length=1, pattern=r"^artifact://.+")
    evidence_bundle_refs: list[str] = Field(default_factory=list)
    variables: list[StateVariable] = Field(default_factory=list)
    constraints: list[StateConstraint] = Field(default_factory=list)
    boundary_conditions: list[str] = Field(default_factory=list)
    unknowns: list[UnknownItem] = Field(default_factory=list)
    mechanism_candidates: list[MechanismCandidate] = Field(default_factory=list)
    analysis_pathways: list[AnalysisPathway] = Field(default_factory=list)
    conflicts: list[ConflictRecord] = Field(default_factory=list)
    staleness: list[StalenessRecord] = Field(default_factory=list)
    merge_policy_version: str = Field(..., min_length=1)
    summary_for_routing: str | None = None
    updated_at: datetime


# --- routing_policy (see routing-policy.schema.json) ---


class EscalationWhen(StrEnum):
    CONFLICT_OPEN_COUNT_GT = "conflict_open_count_gt"
    VERIFICATION_FAIL_COUNT_GT = "verification_fail_count_gt"
    UNKNOWN_BLOCKING_COUNT_GT = "unknown_blocking_count_gt"
    MANUAL_FLAG = "manual_flag"
    STALE_EVIDENCE_PRESENT = "stale_evidence_present"


class EscalationAction(StrEnum):
    ESCALATE = "ESCALATE"
    REQUEST_HUMAN = "REQUEST_HUMAN"
    RECOMPRESS = "RECOMPRESS"
    STOP = "STOP"


class EscalationRule(BaseModel):
    rule_id: str = Field(..., min_length=1)
    when: EscalationWhen
    threshold: float
    action: EscalationAction


class PlaneName(StrEnum):
    INTERACTION = "interaction"
    CONTROL = "control"
    RESEARCH = "research"
    MULTIMODAL = "multimodal"
    CODING = "coding"
    ANALYSIS_SIMULATION = "analysis_simulation"
    REVIEW_VERIFICATION = "review_verification"


class SideEffectLevel(StrEnum):
    NONE = "none"
    READ_ONLY = "read_only"
    WRITE_REPO = "write_repo"
    WRITE_ARTIFACTS = "write_artifacts"
    NETWORK = "network"
    EXECUTE_CODE = "execute_code"


class PlaneToolRow(BaseModel):
    plane: PlaneName
    allowed_tools: list[str] = Field(default_factory=list)
    side_effects: SideEffectLevel
    notes: str | None = None


class CostCeiling(BaseModel):
    max_tokens_per_trace: int | None = Field(default=None, ge=0)
    max_cost_usd_per_trace: float | None = Field(default=None, ge=0)
    max_escalation_events_per_trace: int | None = Field(default=None, ge=0)


class CachePolicy(BaseModel):
    key_components: list[str] = Field(default_factory=list)
    persist_tier: str | None = Field(
        default=None,
        pattern=r"^(memory_only|disk_allowed|disabled)$",
    )


class RoutingPolicy(BaseModel):
    """Versioned defaults for router, escalation, tool matrix, and cache hints."""

    routing_policy_id: UUID
    schema_version: str = Field(..., pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    router_policy_version: str = Field(..., min_length=1)
    notes: str | None = None
    default_budget_policy: BudgetPolicy
    cost_ceiling: CostCeiling | None = None
    escalation_rules: list[EscalationRule] = Field(..., min_length=1)
    executor_defaults: dict[str, Executor] = Field(default_factory=dict)
    plane_tool_matrix: list[PlaneToolRow] = Field(..., min_length=1)
    cache_policy: CachePolicy | None = None
    created_at: datetime
