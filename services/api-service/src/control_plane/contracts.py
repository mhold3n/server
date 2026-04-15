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
    RESPONSE_MODE = "RESPONSE_MODE"
    RESPONSE_CONTROL_ASSESSMENT = "RESPONSE_CONTROL_ASSESSMENT"
    KNOWLEDGE_POOL = "KNOWLEDGE_POOL"
    KNOWLEDGE_POOL_ASSESSMENT = "KNOWLEDGE_POOL_ASSESSMENT"
    KNOWLEDGE_PACK = "KNOWLEDGE_PACK"
    MODULE_CARD = "MODULE_CARD"
    TECHNIQUE_CARD = "TECHNIQUE_CARD"
    THEORY_CARD = "THEORY_CARD"
    RECIPE_OBJECT = "RECIPE_OBJECT"
    EXECUTION_ADAPTER_SPEC = "EXECUTION_ADAPTER_SPEC"
    EVIDENCE_BUNDLE = "EVIDENCE_BUNDLE"
    ROLE_CONTEXT_BUNDLE = "ROLE_CONTEXT_BUNDLE"
    ENVIRONMENT_SPEC = "ENVIRONMENT_SPEC"
    GUI_SESSION_SPEC = "GUI_SESSION_SPEC"
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


class CodeGuidance(BaseModel):
    summary: str | None = None
    file_scope: Scope | None = None
    target_paths: list[str] = Field(default_factory=list)
    implementation_hints: list[str] = Field(default_factory=list)
    acceptance_focus: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)


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


class KnowledgeContext(BaseModel):
    assessment_ref: str = Field(..., min_length=1, pattern=r"^artifact://.+")
    candidate_pack_refs: list[str] = Field(default_factory=list)
    role_context_ref: str | None = Field(default=None, pattern=r"^artifact://.+")
    role_context_summary: str | None = None
    preferred_adapter_ref: str | None = Field(default=None, pattern=r"^artifact://.+")
    preferred_environment_ref: str | None = Field(default=None, pattern=r"^artifact://.+")
    runtime_verification_refs: list[str] = Field(default_factory=list)
    coverage_class: KnowledgeCoverageClass
    required: bool = False


class ResponseModeKey(StrEnum):
    CASUAL_CHAT = "casual_chat"
    IDEATION = "ideation"
    NAPKIN_MATH = "napkin_math"
    ENGINEERING = "engineering"
    RESEARCH = "research"
    DICTIONARY_DEFINITION = "dictionary_definition"
    QUERY = "query"
    BUSINESS = "business"
    CONTENT = "content"
    MARKETING = "marketing"


class ModuleKind(StrEnum):
    TOOL = "tool"
    PACKAGE = "package"
    KNOWLEDGE_BANK = "knowledge_bank"


class ResponseModePolicy(BaseModel):
    response_posture: str = Field(..., min_length=1)
    governance_rules: list[str] = Field(default_factory=list)
    strict_constraints: list[str] = Field(default_factory=list)


class ResponseModePayload(BaseModel):
    response_mode_id: str = Field(..., min_length=1)
    schema_version: str = Field(default="1.0.0", pattern=r"^1\.0\.0$")
    mode_key: ResponseModeKey
    label: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    policy: ResponseModePolicy
    keywords: list[str] = Field(default_factory=list)
    seed_status: str = Field(..., pattern=r"^(formalized|seeded)$")


class KnowledgePoolPayload(BaseModel):
    knowledge_pool_id: str = Field(..., min_length=1)
    schema_version: str = Field(default="1.0.0", pattern=r"^1\.0\.0$")
    pool_key: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    keywords: list[str] = Field(default_factory=list)
    theory_refs: list[str] = Field(..., min_length=1)
    module_refs: list[str] = Field(default_factory=list)


class ModuleCardPayload(BaseModel):
    module_card_id: str = Field(..., min_length=1)
    schema_version: str = Field(default="1.0.0", pattern=r"^1\.0\.0$")
    module_key: str = Field(..., min_length=1)
    module_kind: ModuleKind
    label: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    keywords: list[str] = Field(default_factory=list)
    pool_refs: list[str] = Field(default_factory=list)
    technique_refs: list[str] = Field(default_factory=list)
    legacy_knowledge_pack_refs: list[str] = Field(default_factory=list)


class TechniqueCardPayload(BaseModel):
    technique_card_id: str = Field(..., min_length=1)
    schema_version: str = Field(default="1.0.0", pattern=r"^1\.0\.0$")
    technique_key: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    module_refs: list[str] = Field(..., min_length=1)
    theory_refs: list[str] = Field(default_factory=list)
    application_rules: list[str] = Field(..., min_length=1)
    verification_rules: list[str] = Field(..., min_length=1)


class TheoryCardPayload(BaseModel):
    theory_card_id: str = Field(..., min_length=1)
    schema_version: str = Field(default="1.0.0", pattern=r"^1\.0\.0$")
    theory_key: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    pool_ref: str = Field(..., pattern=r"^artifact://.+")
    summary: str = Field(..., min_length=1)
    source_refs: list[str] = Field(default_factory=list)
    principles: list[str] = Field(..., min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    reference_points: list[str] = Field(default_factory=list)
    interpretation_rules: list[str] = Field(..., min_length=1)


class ModeDissonance(BaseModel):
    inferred_mode: ResponseModeKey
    suggested_mode: ResponseModeKey
    reason: str = Field(..., min_length=1)


class ModeSelection(BaseModel):
    selected_mode: ResponseModeKey
    user_override: bool
    confidence: float = Field(..., ge=0, le=1)
    reasons: list[str] = Field(..., min_length=1)
    mode_dissonance: ModeDissonance | None = None


class KnowledgePoolSelection(BaseModel):
    selected_pool_refs: list[str] = Field(default_factory=list)
    selected_theory_refs: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class ModuleSelection(BaseModel):
    selected_module_refs_by_kind: dict[ModuleKind, list[str]]
    selected_module_refs: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class TechniqueSelection(BaseModel):
    selected_technique_refs: list[str] = Field(default_factory=list)
    derived_from_module_refs: list[str] = Field(default_factory=list)


class ResponseControlAssessment(BaseModel):
    response_control_assessment_id: UUID
    schema_version: str = Field(default="1.0.0", pattern=r"^1\.0\.0$")
    mode_selection: ModeSelection
    knowledge_pool_selection: KnowledgePoolSelection
    module_selection: ModuleSelection
    technique_selection: TechniqueSelection
    assembly_order: list[str] = Field(
        default_factory=lambda: ["mode", "knowledge_pool", "module", "technique", "theory"],
    )
    created_at: datetime

    @model_validator(mode="after")
    def _response_control_invariants(self) -> ResponseControlAssessment:
        """
        Validates the semantic coherence of a response control formulation.
        
        Why: We mandate a strict assembly order because the conceptual reasoning must flow
        from abstract (theory/pool) to concrete implementation (module/technique).
        Additionally, techniques cannot be derived from modules that were not explicitly selected,
        ensuring that the workflow doesn't hallucinate method applications from disjoint libraries.
        """
        expected = ["mode", "knowledge_pool", "module", "technique", "theory"]
        if self.assembly_order != expected:
            raise ValueError("response_control assembly_order must be mode, knowledge_pool, module, technique, theory")
        selected_modules = set(self.module_selection.selected_module_refs)
        derived_modules = set(self.technique_selection.derived_from_module_refs)
        if not derived_modules.issubset(selected_modules):
            raise ValueError("technique_selection.derived_from_module_refs must come from selected_module_refs")
        return self


class TaskPacket(BaseModel):
    """
    The atomic unit of work dispatched to an execution agent or deterministic solver.
    
    Why: Instead of streaming messy chat history to an agent, the control plane synthesizes
    all constraints, required tools, and domain boundaries into a TaskPacket. This acts
    as a strict, auditable contract that agents are evaluated against in the verification stage.
    """

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
    knowledge_context: KnowledgeContext | None = None
    response_control_ref: str | None = Field(default=None, pattern=r"^artifact://.+")
    selected_knowledge_pool_refs: list[str] = Field(default_factory=list)
    selected_module_refs: list[str] = Field(default_factory=list)
    selected_technique_refs: list[str] = Field(default_factory=list)
    selected_theory_refs: list[str] = Field(default_factory=list)
    code_guidance: CodeGuidance | None = None
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
        """
        Runtime invariants beyond JSON Schema (consumer conformance).
        
        Why: These invariants explicitly block invalid state configurations before they hit the agent engine.
        For example:
        - If knowledge is required but coverage is WEAK, we block the packet rather than letting the agent guess.
        - If the coding_model runs with a response_control boundary, it MUST have module_refs so it knows what libraries to use.
        """
        if self.task_type is TaskType.ESCALATION_REVIEW and not self.budget_policy.allow_escalation:
            raise ValueError("ESCALATION_REVIEW requires budget_policy.allow_escalation=true")
        if self.task_type is TaskType.VALIDATION and len(self.validation_requirements) < 1:
            raise ValueError("VALIDATION requires non-empty validation_requirements")
        if self.knowledge_context and self.knowledge_context.required:
            if self.knowledge_context.coverage_class in {
                KnowledgeCoverageClass.NONE,
                KnowledgeCoverageClass.WEAK,
            }:
                raise ValueError(
                    "knowledge_context.required=true requires partial or strong coverage",
                )
            if self.knowledge_context.role_context_ref is None:
                raise ValueError("knowledge_context.required=true requires role_context_ref")
        has_response_control_context = any(
            [
                self.selected_knowledge_pool_refs,
                self.selected_module_refs,
                self.selected_technique_refs,
                self.selected_theory_refs,
            ]
        )
        if has_response_control_context and self.response_control_ref is None:
            raise ValueError("selected response-control refs require response_control_ref")
        if self.selected_knowledge_pool_refs and not self.selected_theory_refs:
            raise ValueError("selected_knowledge_pool_refs require selected_theory_refs")
        if (
            self.response_control_ref
            and self.routing_metadata.selected_executor is Executor.CODING_MODEL
            and not self.selected_module_refs
        ):
            raise ValueError("coding_model packets with response_control_ref require selected_module_refs")
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


class KnowledgePoolCoverageStatus(StrEnum):
    SEEDED = "SEEDED"
    PARTIAL = "PARTIAL"
    PLANNED = "PLANNED"
    COMPLETE = "COMPLETE"


class KnowledgeCoverageClass(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    NONE = "none"
    WEAK = "weak"
    PARTIAL = "partial"
    STRONG = "strong"


class KnowledgeSource(BaseModel):
    source_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    kind: str = Field(
        ...,
        pattern=r"^(codebase|contract_registry|tool_catalog|documentation|runbook|artifact|other)$",
    )
    location: str | None = None
    access_pattern: str = Field(..., min_length=1)
    trust_notes: str | None = None
    refresh_policy: str | None = None
    tags: list[str] = Field(default_factory=list)


class ExecutionAdapter(BaseModel):
    adapter_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    kind: str = Field(
        ...,
        pattern=r"^(mcp_server|cli|http_api|runtime|workflow|other)$",
    )
    interface_contract: str = Field(..., min_length=1)
    execution_backend: str = Field(..., min_length=1)
    primary_uses: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class ValidationHarnessSpec(BaseModel):
    harness_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    kind: str = Field(
        ...,
        pattern=r"^(schema|deterministic_command|artifact_audit|verification_report|policy_gate|other)$",
    )
    trigger: str = Field(..., min_length=1)
    evidence_emitted: list[str] = Field(default_factory=list)
    blocking_conditions: list[str] = Field(default_factory=list)


class RoleSpecificContextCompilation(BaseModel):
    role_id: str = Field(..., min_length=1)
    role_label: str = Field(..., min_length=1)
    applies_to_executor: Executor | None = None
    knowledge_source_ids: list[str] = Field(default_factory=list)
    adapter_ids: list[str] = Field(default_factory=list)
    validation_harness_ids: list[str] = Field(default_factory=list)
    summary: str = Field(..., min_length=1)
    compiled_context: str = Field(..., min_length=1)


class KnowledgePool(BaseModel):
    """Reusable focus-scoped knowledge substrate for engineering workflows."""

    knowledge_pool_id: UUID
    schema_version: str = Field(default="1.0.0", pattern=r"^1\.0\.0$")
    focus_area: str = Field(
        ...,
        pattern=r"^(engineering|general_engineering|chemistry|physics|other)$",
    )
    domain: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    coverage_status: KnowledgePoolCoverageStatus = KnowledgePoolCoverageStatus.SEEDED
    planned_expansion_domains: list[str] = Field(default_factory=list)
    shared_external_knowledge_substrate: list[KnowledgeSource] = Field(..., min_length=1)
    typed_execution_adapters: list[ExecutionAdapter] = Field(..., min_length=1)
    validation_evidence_harness: list[ValidationHarnessSpec] = Field(..., min_length=1)
    role_specific_context_compilation: list[RoleSpecificContextCompilation] = Field(
        ...,
        min_length=1,
    )
    created_at: datetime
    updated_at: datetime


class KnowledgePoolAssessment(BaseModel):
    """Deterministic knowledge-pool fit assessment for routing and governed execution."""

    knowledge_pool_assessment_id: UUID
    schema_version: str = Field(default="1.0.0", pattern=r"^1\.0\.0$")
    derived_task_class: str = Field(..., min_length=1)
    coverage_class: KnowledgeCoverageClass
    required_for_mode: bool
    candidate_pack_refs: list[str] = Field(default_factory=list)
    preferred_adapter_refs: list[str] = Field(default_factory=list)
    preferred_environment_refs: list[str] = Field(default_factory=list)
    runtime_verification_refs: list[str] = Field(default_factory=list)
    knowledge_gaps: list[str] = Field(default_factory=list)
    rule_matches: list[str] = Field(default_factory=list)
    created_at: datetime


class KnowledgePackScope(BaseModel):
    solves: list[str] = Field(..., min_length=1)
    not_for: list[str] = Field(default_factory=list)


class KnowledgeCoreObject(BaseModel):
    name: str = Field(..., min_length=1)
    kind: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)


class KnowledgePackInterfaces(BaseModel):
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)


class KnowledgePackProvenance(BaseModel):
    sources: list[str] = Field(..., min_length=1)
    examples: list[str] = Field(default_factory=list)
    benchmarks: list[str] = Field(default_factory=list)


class EnvironmentSpecPayload(BaseModel):
    environment_spec_id: str = Field(..., min_length=1)
    schema_version: str = Field(default="1.0.0", pattern=r"^1\.0\.0$")
    runtime_profile: str = Field(..., min_length=1)
    delivery_kind: str = Field(..., pattern=r"^(docker_image|uv_venv|dotnet_toolchain|host_app)$")
    docker_platform: str | None = None
    gui_session_refs: list[str] = Field(default_factory=list)
    default_gui_session_ref: str | None = Field(default=None, pattern=r"^artifact://.+")
    gui_capability_state: str = Field(
        default="NO_GUI",
        pattern=r"^(NO_GUI|PLANNED_CONTAINER_GUI|VERIFIED_CONTAINER_GUI|BLOCKED_CONTAINER_GUI|API_ONLY_HOST_PATH)$",
    )
    module_ids: list[str] = Field(..., min_length=1)
    supported_host_platforms: list[str] = Field(..., min_length=1)
    manifest_format: str = Field(
        ...,
        pattern=r"^(dockerfile|requirements_txt|csproj|script|other)$",
    )
    manifest_path: str = Field(..., min_length=1)
    runtime_locator: str = Field(..., min_length=1)
    bootstrap_command: str = Field(..., min_length=1)
    healthcheck_command: str = Field(..., min_length=1)
    launcher_ref: str = Field(..., min_length=1)
    notes: list[str] = Field(default_factory=list)


class GuiContainerPorts(BaseModel):
    bind_host: str = Field(default="127.0.0.1", pattern=r"^127\.0\.0\.1$")
    novnc: int = Field(..., ge=1)
    vnc: int = Field(..., ge=1)


class GuiSecurityPolicy(BaseModel):
    bind_host: str = Field(default="127.0.0.1", pattern=r"^127\.0\.0\.1$")
    require_token: bool = True
    network_mode: str = Field(..., pattern=r"^(bridge|none)$")
    allow_host_desktop: bool = False
    close_on_session_end: bool = True

    @model_validator(mode="after")
    def _no_host_desktop_and_token_required(self) -> GuiSecurityPolicy:
        if self.bind_host != "127.0.0.1":
            raise ValueError("GUI sessions must bind noVNC to 127.0.0.1")
        if not self.require_token:
            raise ValueError("GUI sessions must require a token/password")
        if self.allow_host_desktop:
            raise ValueError("GUI sessions must not allow host desktop control")
        return self


class GuiSessionSpecPayload(BaseModel):
    gui_session_spec_id: str = Field(..., min_length=1)
    schema_version: str = Field(default="1.0.0", pattern=r"^1\.0\.0$")
    base_environment_ref: str = Field(..., pattern=r"^artifact://.+")
    gui_environment_ref: str = Field(..., pattern=r"^artifact://.+")
    module_ids: list[str] = Field(..., min_length=1)
    docker_image: str = Field(..., min_length=1)
    docker_platform: str = Field(..., min_length=1)
    display_protocol: str = Field(default="novnc_web", pattern=r"^novnc_web$")
    control_provider: str = Field(default="openclaw_browser", pattern=r"^openclaw_browser$")
    container_ports: GuiContainerPorts
    display_env: dict[str, str] = Field(..., min_length=1)
    launch_command: str = Field(..., min_length=1)
    healthcheck_command: str = Field(..., min_length=1)
    openclaw_entry_url: str = Field(..., min_length=1)
    artifact_output_dir: str = Field(..., min_length=1)
    security_policy: GuiSecurityPolicy
    manifest_path: str = Field(..., min_length=1)
    launcher_ref: str = Field(..., min_length=1)
    app_profile: str | None = None
    launch_target_command: str | None = None
    verification_ref: str | None = Field(default=None, pattern=r"^artifact://.+")
    notes: list[str] = Field(default_factory=list)


class KnowledgePackPayload(BaseModel):
    knowledge_pack_id: str = Field(..., min_length=1)
    schema_version: str = Field(default="1.0.0", pattern=r"^1\.0\.0$")
    tool_id: str = Field(..., min_length=1)
    tool_name: str = Field(..., min_length=1)
    module_class: str = Field(
        ...,
        pattern=r"^(application|framework|integration_layer|runtime_kernel|translator|standard)$",
    )
    library_version: str = Field(..., min_length=1)
    bindings: list[str] = Field(..., min_length=1)
    scope: KnowledgePackScope
    core_objects: list[KnowledgeCoreObject] = Field(..., min_length=1)
    best_for: list[str] = Field(..., min_length=1)
    anti_patterns: list[str] = Field(default_factory=list)
    interfaces: KnowledgePackInterfaces
    integration_refs: list[str] = Field(default_factory=list)
    recipe_refs: list[str] = Field(..., min_length=1)
    adapter_refs: list[str] = Field(..., min_length=1)
    evidence_refs: list[str] = Field(..., min_length=1)
    minutes_source_refs: list[str] = Field(..., min_length=1)
    environment_refs: list[str] = Field(..., min_length=1)
    alias_names: list[str] = Field(default_factory=list)
    substitution_note: str | None = None
    excluded_reason: str | None = None
    provenance: KnowledgePackProvenance


class RecipeTouchedObject(BaseModel):
    name: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    notes: str | None = None


class RecipeObjectPayload(BaseModel):
    recipe_id: str = Field(..., min_length=1)
    schema_version: str = Field(default="1.0.0", pattern=r"^1\.0\.0$")
    title: str = Field(..., min_length=1)
    task_class: str = Field(..., min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    why_this_stack: str = Field(..., min_length=1)
    knowledge_pack_ref: str = Field(..., pattern=r"^artifact://.+")
    touched_objects: list[RecipeTouchedObject] = Field(..., min_length=1)
    implementation_pattern: list[str] = Field(..., min_length=1)
    required_inputs: list[str] = Field(default_factory=list)
    required_outputs: list[str] = Field(default_factory=list)
    failure_signatures: list[str] = Field(default_factory=list)
    acceptance_tests: list[str] = Field(..., min_length=1)
    adapter_refs: list[str] = Field(..., min_length=1)
    evidence_refs: list[str] = Field(..., min_length=1)


class AdapterIOField(BaseModel):
    name: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    required: bool | None = None
    unit: str | None = None


class CallableInterfaceSpec(BaseModel):
    kind: str = Field(
        ...,
        pattern=r"^(python_function|python_module|cli|dotnet|cxx_binding)$",
    )
    entrypoint: str = Field(..., min_length=1)
    signature: str | None = None


class UnitPolicySpec(BaseModel):
    unit_system: str = Field(..., pattern=r"^(SI|US_CUSTOMARY|MIXED_DECLARED)$")
    require_declared_units: bool
    notes: str | None = None


class FileTranslatorSpec(BaseModel):
    from_: str = Field(..., alias="from", min_length=1)
    to: str = Field(..., min_length=1)
    notes: str = Field(..., min_length=1)


class ExecutionAdapterSpecPayload(BaseModel):
    adapter_spec_id: str = Field(..., min_length=1)
    schema_version: str = Field(default="1.0.0", pattern=r"^1\.0\.0$")
    tool_id: str = Field(..., min_length=1)
    supported_library_version: str = Field(..., min_length=1)
    knowledge_pack_ref: str = Field(..., pattern=r"^artifact://.+")
    preferred_environment_ref: str = Field(..., pattern=r"^artifact://.+")
    environment_refs: list[str] = Field(..., min_length=1)
    callable_interface: CallableInterfaceSpec
    typed_inputs: list[AdapterIOField] = Field(..., min_length=1)
    typed_outputs: list[AdapterIOField] = Field(..., min_length=1)
    unit_policy: UnitPolicySpec
    file_translators: list[FileTranslatorSpec] = Field(default_factory=list)
    runtime_requirements: list[str] = Field(default_factory=list)
    healthcheck_refs: list[str] = Field(..., min_length=1)
    safety_limits: list[str] = Field(default_factory=list)
    emitted_artifact_refs: list[str] = Field(default_factory=list)
    launcher_ref: str = Field(..., min_length=1)


class EvidenceBundleProvenance(BaseModel):
    sources: list[str] = Field(..., min_length=1)
    benchmarks: list[str] = Field(default_factory=list)


class EvidenceBundlePayload(BaseModel):
    evidence_bundle_id: str = Field(..., min_length=1)
    schema_version: str = Field(default="1.0.0", pattern=r"^1\.0\.0$")
    title: str = Field(..., min_length=1)
    tool_id: str = Field(..., min_length=1)
    knowledge_pack_ref: str = Field(..., pattern=r"^artifact://.+")
    recipe_refs: list[str] = Field(..., min_length=1)
    adapter_refs: list[str] = Field(..., min_length=1)
    smoke_tests: list[str] = Field(..., min_length=1)
    benchmark_cases: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    tolerances: list[str] = Field(default_factory=list)
    convergence_criteria: list[str] = Field(default_factory=list)
    reviewer_checklist: list[str] = Field(..., min_length=1)
    runtime_verification_refs: list[str] = Field(..., min_length=1)
    healthcheck_commands: list[str] = Field(..., min_length=1)
    reference_artifact_refs: list[str] = Field(default_factory=list)
    provenance: EvidenceBundleProvenance


class SourceHashRecord(BaseModel):
    artifact_ref: str = Field(..., pattern=r"^artifact://.+")
    sha256: str = Field(..., pattern=r"^[a-f0-9]{64}$")


class RoleContextBundlePayload(BaseModel):
    role_context_bundle_id: str = Field(..., min_length=1)
    schema_version: str = Field(default="1.0.0", pattern=r"^1\.0\.0$")
    role: str = Field(..., pattern=r"^(general|coder|reviewer)$")
    task_class: str = Field(..., min_length=1)
    source_artifact_refs: list[str] = Field(..., min_length=1)
    source_hashes: list[SourceHashRecord] = Field(..., min_length=1)
    compiled_summary: str = Field(..., min_length=1)
    included_sections: list[str] = Field(..., min_length=1)
    excluded_sections: list[str] = Field(default_factory=list)
    retrieval_keys: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _source_hash_refs_match(self) -> RoleContextBundlePayload:
        source_refs = set(self.source_artifact_refs)
        hash_refs = {item.artifact_ref for item in self.source_hashes}
        if source_refs != hash_refs:
            raise ValueError("source_hashes must cover exactly the source_artifact_refs")
        return self


class DecisionLogPayload(BaseModel):
    decision_id: str = Field(..., min_length=1)
    schema_version: str = Field(default="1.0.0", pattern=r"^1\.0\.0$")
    title: str = Field(..., min_length=1)
    statement: str = Field(..., min_length=1)
    rationale: str = Field(..., min_length=1)
    chosen_refs: list[str] = Field(..., min_length=1)
    rejected_refs: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)
    status: str = Field(..., pattern=r"^(accepted|proposed|superseded)$")


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


class SystemBoundary(BaseModel):
    system_of_interest: str = Field(..., min_length=1)
    system_level: str | None = None
    included: list[str] = Field(default_factory=list)
    excluded: list[str] = Field(default_factory=list)
    interfaces: list[str] = Field(default_factory=list)


class ProblemStatement(BaseModel):
    need: str = Field(..., min_length=1)
    why: str | None = None
    non_goals: list[str] = Field(default_factory=list)


class EngineeringObjective(BaseModel):
    id: str = Field(..., min_length=1)
    statement: str = Field(..., min_length=1)
    priority: Priority | None = None


class OperationalScenario(BaseModel):
    scenario_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    operating_conditions: list[str] = Field(default_factory=list)
    environment: str | None = None
    usage_mode: str | None = None


class OperationalContext(BaseModel):
    unit_system: str | None = None
    notes: str | None = None
    scenarios: list[OperationalScenario] = Field(..., min_length=1)


class RequiredDeliverable(BaseModel):
    id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    artifact_type_hint: ArtifactType | None = None


class DeliverableSpec(BaseModel):
    deliverable_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    artifact_type_hint: ArtifactType | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)


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


class EvidenceInput(BaseModel):
    input_id: str = Field(..., min_length=1)
    kind: str = Field(
        ...,
        pattern=r"^(document|drawing|codebase|standard|measurement|artifact|other)$",
    )
    description: str = Field(..., min_length=1)
    ref: str | None = None
    required: bool = True


class SuccessCriterion(BaseModel):
    criterion_id: str = Field(..., min_length=1)
    statement: str = Field(..., min_length=1)
    metric: str = Field(..., min_length=1)
    target: QuantifiedScalar | None = None
    minimum: QuantifiedScalar | None = None
    maximum: QuantifiedScalar | None = None
    verification_method: str = Field(
        ...,
        pattern=r"^(analytical|simulation|test|inspection|review|other)$",
    )
    expected_evidence: str = Field(
        ...,
        pattern=r"^(document|drawing|codebase|standard|measurement|simulation|other)$",
    )
    priority: Priority | None = None
    rationale: str | None = None

    @model_validator(mode="after")
    def _require_quantitative_target(self) -> SuccessCriterion:
        if self.target is None and self.minimum is None and self.maximum is None:
            raise ValueError(
                "success_criteria require at least one of target, minimum, or maximum",
            )
        return self


class ConstraintProvenance(BaseModel):
    source_type: str = Field(
        ...,
        pattern=r"^(user|task_packet|task_plan|document|drawing|standard|codebase|system_policy|other)$",
    )
    source_ref: str | None = None
    rationale: str | None = None


class ConstraintSpec(BaseModel):
    constraint_id: str = Field(..., min_length=1)
    statement: str = Field(..., min_length=1)
    kind: str | None = Field(
        default=None,
        pattern=r"^(physical|geometric|regulatory|economic|software|workflow|other)$",
    )
    metric: str | None = None
    target: QuantifiedScalar | None = None
    minimum: QuantifiedScalar | None = None
    maximum: QuantifiedScalar | None = None
    provenance: ConstraintProvenance


class AssumptionSpec(BaseModel):
    assumption_id: str = Field(..., min_length=1)
    statement: str = Field(..., min_length=1)
    validation_intent: str = Field(..., min_length=1)
    impact_if_false: str = Field(..., min_length=1)
    blocking_if_unvalidated: bool = False
    status: str = Field(
        default="assumed",
        pattern=r"^(assumed|validated|waived)$",
    )


class DesignVariableSpec(BaseModel):
    variable_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    category: str = Field(
        ...,
        pattern=r"^(response|controllable|noise|fixed)$",
    )
    unit: str | None = None
    bounds: dict[str, float] | None = None


class DesignSpace(BaseModel):
    responses: list[DesignVariableSpec] = Field(..., min_length=1)
    controllable_variables: list[DesignVariableSpec] = Field(default_factory=list)
    noise_factors: list[DesignVariableSpec] = Field(default_factory=list)
    fixed_parameters: list[DesignVariableSpec] = Field(default_factory=list)


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
    system_boundary: SystemBoundary
    problem_statement: ProblemStatement
    operational_context: OperationalContext
    success_criteria: list[SuccessCriterion] = Field(..., min_length=1)
    constraints: list[ConstraintSpec] = Field(..., min_length=1)
    assumptions: list[AssumptionSpec] = Field(default_factory=list)
    design_space: DesignSpace
    deliverables: list[DeliverableSpec] = Field(..., min_length=1)
    inputs: list[EvidenceInput] = Field(..., min_length=1)
    code_guidance: CodeGuidance | None = None
    system_purpose: str | None = None
    scope: Scope | None = None
    engineering_objectives: list[EngineeringObjective] = Field(default_factory=list)
    operating_envelope: OperatingEnvelope | None = None
    forbidden_actions: list[str] = Field(default_factory=list)
    required_deliverables: list[RequiredDeliverable] = Field(default_factory=list)
    acceptance_tests: list[AcceptanceTestSpec] = Field(default_factory=list)
    evidence_expectations: list[EvidenceExpectation] = Field(default_factory=list)
    human_approval: HumanApprovalBlock | None = None
    provenance: ProblemBriefProvenance
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _backfill_legacy_views(self) -> ProblemBrief:
        if self.system_purpose is None:
            self.system_purpose = self.problem_statement.need
        if self.scope is None:
            self.scope = Scope(
                included=list(self.system_boundary.included),
                excluded=list(self.system_boundary.excluded),
            )
        if not self.engineering_objectives:
            self.engineering_objectives = [
                EngineeringObjective(
                    id=criterion.criterion_id,
                    statement=criterion.statement,
                    priority=criterion.priority,
                )
                for criterion in self.success_criteria
            ]
        if not self.required_deliverables:
            self.required_deliverables = [
                RequiredDeliverable(
                    id=deliverable.deliverable_id,
                    description=deliverable.description,
                    artifact_type_hint=deliverable.artifact_type_hint,
                )
                for deliverable in self.deliverables
            ]
        if not self.acceptance_tests:
            self.acceptance_tests = [
                AcceptanceTestSpec(
                    id=criterion.criterion_id,
                    description=criterion.statement,
                    kind=(
                        "simulation"
                        if criterion.verification_method == "simulation"
                        else "inspection"
                        if criterion.verification_method == "inspection"
                        else "automated"
                    ),
                    criteria_ref=criterion.criterion_id,
                )
                for criterion in self.success_criteria
            ]
        if not self.evidence_expectations:
            seen: set[str] = set()
            for criterion in self.success_criteria:
                if criterion.expected_evidence in seen:
                    continue
                seen.add(criterion.expected_evidence)
                self.evidence_expectations.append(
                    EvidenceExpectation(
                        kind=criterion.expected_evidence
                        if criterion.expected_evidence
                        in {"document", "drawing", "codebase", "standard", "measurement", "other"}
                        else "other",
                        notes=f"Derived from success criterion {criterion.criterion_id}",
                    )
                )
        return self


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
    role: str | None = Field(
        default=None,
        pattern=r"^(response|controllable|noise|fixed)$",
    )
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
    provenance_source: str | None = None
    rationale: str | None = None


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


class NormalizedBoundary(BaseModel):
    system_of_interest: str = Field(..., min_length=1)
    system_level: str | None = None
    included: list[str] = Field(default_factory=list)
    excluded: list[str] = Field(default_factory=list)
    interfaces: list[str] = Field(default_factory=list)


class ObjectiveRecord(BaseModel):
    objective_id: str = Field(..., min_length=1)
    statement: str = Field(..., min_length=1)
    metric: str = Field(..., min_length=1)
    verification_method: str = Field(..., min_length=1)
    priority: Priority | None = None


class VerificationIntentRow(BaseModel):
    criterion_id: str = Field(..., min_length=1)
    verification_method: str = Field(..., min_length=1)
    expected_evidence: str = Field(..., min_length=1)
    target_summary: str = Field(..., min_length=1)
    status: str = Field(default="planned", pattern=r"^(planned|blocked|satisfied)$")


class AssumptionStatusRecord(BaseModel):
    assumption_id: str = Field(..., min_length=1)
    statement: str = Field(..., min_length=1)
    validation_intent: str = Field(..., min_length=1)
    status: str = Field(..., pattern=r"^(pending|validated|waived)$")
    blocking: bool = False
    impact_if_false: str = Field(..., min_length=1)


class OpenIssueRecord(BaseModel):
    issue_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    category: str = Field(
        ...,
        pattern=r"^(missing_information|assumption|approval|conflict|staleness|other)$",
    )
    blocking: bool = False
    source_artifact_refs: list[str] = Field(default_factory=list)


class RequiredGateRecord(BaseModel):
    gate_id: str = Field(..., min_length=1)
    gate_type: str = Field(
        ...,
        pattern=r"^(clarification|approval|verification|conflict|staleness)$",
    )
    status: str = Field(..., pattern=r"^(PENDING|SATISFIED|WAIVED)$")
    rationale: str = Field(..., min_length=1)


class EngineeringState(BaseModel):
    """Canonical merged technical state for routing and decomposition."""

    engineering_state_id: UUID
    schema_version: str = Field(..., pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    trace_id: str | None = Field(default=None, min_length=8)
    problem_brief_ref: str = Field(..., min_length=1, pattern=r"^artifact://.+")
    knowledge_pool_assessment_ref: str | None = Field(
        default=None,
        pattern=r"^artifact://.+",
    )
    knowledge_pool_coverage: KnowledgeCoverageClass | None = None
    knowledge_candidate_refs: list[str] = Field(default_factory=list)
    knowledge_role_context_refs: list[str] = Field(default_factory=list)
    knowledge_gaps: list[str] = Field(default_factory=list)
    knowledge_required: bool = False
    response_control_ref: str | None = Field(default=None, pattern=r"^artifact://.+")
    selected_knowledge_pool_refs: list[str] = Field(default_factory=list)
    selected_module_refs: list[str] = Field(default_factory=list)
    selected_technique_refs: list[str] = Field(default_factory=list)
    selected_theory_refs: list[str] = Field(default_factory=list)
    evidence_bundle_refs: list[str] = Field(default_factory=list)
    normalized_boundary: NormalizedBoundary
    objectives: list[ObjectiveRecord] = Field(..., min_length=1)
    verification_intent: list[VerificationIntentRow] = Field(..., min_length=1)
    variables: list[StateVariable] = Field(default_factory=list)
    constraints: list[StateConstraint] = Field(default_factory=list)
    boundary_conditions: list[str] = Field(default_factory=list)
    unknowns: list[UnknownItem] = Field(default_factory=list)
    assumption_status: list[AssumptionStatusRecord] = Field(default_factory=list)
    open_issues: list[OpenIssueRecord] = Field(default_factory=list)
    mechanism_candidates: list[MechanismCandidate] = Field(default_factory=list)
    analysis_pathways: list[AnalysisPathway] = Field(default_factory=list)
    conflicts: list[ConflictRecord] = Field(default_factory=list)
    staleness: list[StalenessRecord] = Field(default_factory=list)
    required_gates: list[RequiredGateRecord] = Field(default_factory=list)
    ready_for_task_decomposition: bool
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
