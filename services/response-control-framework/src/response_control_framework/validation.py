"""
Load Draft 2020-12 schemas from the repo and validate instances.

For agents: uses canonical `$id` registry under `schemas/control-plane/v1/registry.json`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

from .contracts import (
    DecisionLogPayload,
    EngineeringState,
    EnvironmentSpecPayload,
    EvidenceBundlePayload,
    ExecutionAdapterSpecPayload,
    GuiSessionSpecPayload,
    KnowledgePackPayload,
    KnowledgePoolAssessment,
    KnowledgePoolPayload,
    ModuleCardPayload,
    ProblemBrief,
    RecipeObjectPayload,
    ResponseControlAssessment,
    ResponseModePayload,
    RoleContextBundlePayload,
    RoutingPolicy,
    TaskPacket,
    TaskQueue,
    TechniqueCardPayload,
    TheoryCardPayload,
    VerificationReportPayload,
    WikiEditProposalPayload,
)
from .errors import ContractErrorDetail, ContractValidationError

TASK_PACKET_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/task-packet.schema.json"
)
ARTIFACT_RECORD_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/artifact-record.schema.json"
)
PROBLEM_BRIEF_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/problem-brief.schema.json"
)
KNOWLEDGE_PACK_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/knowledge-pack.schema.json"
)
KNOWLEDGE_POOL_ASSESSMENT_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/knowledge-pool-assessment.schema.json"
)
RESPONSE_MODE_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/response-mode.schema.json"
)
KNOWLEDGE_POOL_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/knowledge-pool.schema.json"
)
MODULE_CARD_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/module-card.schema.json"
)
TECHNIQUE_CARD_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/technique-card.schema.json"
)
THEORY_CARD_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/theory-card.schema.json"
)
RESPONSE_CONTROL_ASSESSMENT_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/response-control-assessment.schema.json"
)
RECIPE_OBJECT_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/recipe-object.schema.json"
)
EXECUTION_ADAPTER_SPEC_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/execution-adapter-spec.schema.json"
)
EVIDENCE_BUNDLE_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/evidence-bundle.schema.json"
)
ROLE_CONTEXT_BUNDLE_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/role-context-bundle.schema.json"
)
ENVIRONMENT_SPEC_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/environment-spec.schema.json"
)
GUI_SESSION_SPEC_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/gui-session-spec.schema.json"
)
DECISION_LOG_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/decision-log.schema.json"
)
VERIFICATION_REPORT_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/verification-report.schema.json"
)
TASK_QUEUE_SCHEMA_ID = "https://birtha.local/schemas/control-plane/v1/task-queue.schema.json"
ENGINEERING_STATE_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/engineering-state.schema.json"
)
ROUTING_POLICY_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/routing-policy.schema.json"
)
WIKI_EDIT_PROPOSAL_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/wiki-edit-proposal.schema.json"
)


def _repo_root() -> Path:
    """Walk up from this file until `schemas/control-plane/v1` exists."""
    here = Path(__file__).resolve()
    for p in [here, *here.parents]:
        if (p / "services" / "response-control-framework" / "schemas" / "control-plane" / "v1" / "registry.json").exists():
            return p
    raise RuntimeError("Could not locate repo root (schemas/control-plane/v1 missing)")


def _load_registry_store() -> dict[str, dict[str, Any]]:
    root = _repo_root()
    reg_path = root / "services" / "response-control-framework" / "schemas" / "control-plane" / "v1" / "registry.json"
    manifest = json.loads(reg_path.read_text(encoding="utf-8"))
    store: dict[str, dict[str, Any]] = {}
    for entry in manifest.get("schemas", []):
        path = root / "services" / "response-control-framework" / "schemas" / "control-plane" / "v1" / entry["path"]
        data = json.loads(path.read_text(encoding="utf-8"))
        sid = data.get("$id")
        if sid != entry["id"]:
            raise RuntimeError(f"Schema $id mismatch for {entry['path']}")
        store[sid] = data
    return store


_store: dict[str, dict[str, Any]] | None = None


def get_schema_store() -> dict[str, dict[str, Any]]:
    global _store  # noqa: PLW0603 — intentional module cache
    if _store is None:
        _store = _load_registry_store()
    return _store


def _validator_for(schema_id: str) -> Draft202012Validator:
    store = get_schema_store()
    if schema_id not in store:
        raise KeyError(f"Unknown schema id: {schema_id}")
    schema = store[schema_id]
    resolver = jsonschema.RefResolver(base_uri="", referrer=None, store=store)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, resolver=resolver)


def _schema_error(
    *,
    schema_id: str,
    contract_type: str,
    error: jsonschema.exceptions.ValidationError,
) -> ContractValidationError:
    path = "/" + "/".join(str(p) for p in error.absolute_path) if error.absolute_path else "/"
    return ContractValidationError(
        error_code="SCHEMA_VALIDATION_FAILED",
        contract_type=contract_type,
        schema_id=schema_id,
        details=[ContractErrorDetail(path=path, message=error.message, keyword=error.validator)],
    )


def _model_error(
    *,
    schema_id: str,
    contract_type: str,
    error: ValueError,
) -> ContractValidationError:
    return ContractValidationError(
        error_code="SCHEMA_VALIDATION_FAILED",
        contract_type=contract_type,
        schema_id=schema_id,
        details=[ContractErrorDetail(path="/", message=str(error), keyword="model_validate")],
    )


def validate_task_packet_json(data: dict[str, Any]) -> TaskPacket:
    """JSON Schema + Pydantic consumer conformance for task_packet."""
    v = _validator_for(TASK_PACKET_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        path = "/" + "/".join(str(p) for p in e.absolute_path) if e.absolute_path else "/"
        raise ContractValidationError(
            error_code="SCHEMA_VALIDATION_FAILED",
            contract_type="TASK_PACKET",
            schema_id=TASK_PACKET_SCHEMA_ID,
            details=[
                ContractErrorDetail(path=path, message=e.message, keyword=e.validator)
            ],
        ) from e
    try:
        return TaskPacket.model_validate(data)
    except ValueError as e:
        raise ContractValidationError(
            error_code="SCHEMA_VALIDATION_FAILED",
            contract_type="TASK_PACKET",
            schema_id=TASK_PACKET_SCHEMA_ID,
            details=[ContractErrorDetail(path="/", message=str(e), keyword="model_validate")],
        ) from e


def validate_typed_artifact_json(data: dict[str, Any]) -> None:
    """Schema-only validation for typed artifact envelope (Pydantic optional follow-up)."""
    v = _validator_for(ARTIFACT_RECORD_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        path = "/" + "/".join(str(p) for p in e.absolute_path) if e.absolute_path else "/"
        raise ContractValidationError(
            error_code="SCHEMA_VALIDATION_FAILED",
            contract_type="ARTIFACT_RECORD",
            schema_id=ARTIFACT_RECORD_SCHEMA_ID,
            details=[
                ContractErrorDetail(path=path, message=e.message, keyword=e.validator)
            ],
        ) from e


def validate_knowledge_pack_json(data: dict[str, Any]) -> KnowledgePackPayload:
    v = _validator_for(KNOWLEDGE_PACK_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        raise _schema_error(
            schema_id=KNOWLEDGE_PACK_SCHEMA_ID,
            contract_type="KNOWLEDGE_PACK",
            error=e,
        ) from e
    try:
        return KnowledgePackPayload.model_validate(data)
    except ValueError as e:
        raise _model_error(
            schema_id=KNOWLEDGE_PACK_SCHEMA_ID,
            contract_type="KNOWLEDGE_PACK",
            error=e,
        ) from e


def validate_knowledge_pool_assessment_json(data: dict[str, Any]) -> KnowledgePoolAssessment:
    v = _validator_for(KNOWLEDGE_POOL_ASSESSMENT_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        raise _schema_error(
            schema_id=KNOWLEDGE_POOL_ASSESSMENT_SCHEMA_ID,
            contract_type="KNOWLEDGE_POOL_ASSESSMENT",
            error=e,
        ) from e
    try:
        return KnowledgePoolAssessment.model_validate(data)
    except ValueError as e:
        raise _model_error(
            schema_id=KNOWLEDGE_POOL_ASSESSMENT_SCHEMA_ID,
            contract_type="KNOWLEDGE_POOL_ASSESSMENT",
            error=e,
        ) from e


def validate_response_mode_json(data: dict[str, Any]) -> ResponseModePayload:
    v = _validator_for(RESPONSE_MODE_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        raise _schema_error(
            schema_id=RESPONSE_MODE_SCHEMA_ID,
            contract_type="RESPONSE_MODE",
            error=e,
        ) from e
    try:
        return ResponseModePayload.model_validate(data)
    except ValueError as e:
        raise _model_error(
            schema_id=RESPONSE_MODE_SCHEMA_ID,
            contract_type="RESPONSE_MODE",
            error=e,
        ) from e


def validate_knowledge_pool_json(data: dict[str, Any]) -> KnowledgePoolPayload:
    v = _validator_for(KNOWLEDGE_POOL_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        raise _schema_error(
            schema_id=KNOWLEDGE_POOL_SCHEMA_ID,
            contract_type="KNOWLEDGE_POOL",
            error=e,
        ) from e
    try:
        return KnowledgePoolPayload.model_validate(data)
    except ValueError as e:
        raise _model_error(
            schema_id=KNOWLEDGE_POOL_SCHEMA_ID,
            contract_type="KNOWLEDGE_POOL",
            error=e,
        ) from e


def validate_module_card_json(data: dict[str, Any]) -> ModuleCardPayload:
    v = _validator_for(MODULE_CARD_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        raise _schema_error(
            schema_id=MODULE_CARD_SCHEMA_ID,
            contract_type="MODULE_CARD",
            error=e,
        ) from e
    try:
        return ModuleCardPayload.model_validate(data)
    except ValueError as e:
        raise _model_error(
            schema_id=MODULE_CARD_SCHEMA_ID,
            contract_type="MODULE_CARD",
            error=e,
        ) from e


def validate_technique_card_json(data: dict[str, Any]) -> TechniqueCardPayload:
    v = _validator_for(TECHNIQUE_CARD_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        raise _schema_error(
            schema_id=TECHNIQUE_CARD_SCHEMA_ID,
            contract_type="TECHNIQUE_CARD",
            error=e,
        ) from e
    try:
        return TechniqueCardPayload.model_validate(data)
    except ValueError as e:
        raise _model_error(
            schema_id=TECHNIQUE_CARD_SCHEMA_ID,
            contract_type="TECHNIQUE_CARD",
            error=e,
        ) from e


def validate_theory_card_json(data: dict[str, Any]) -> TheoryCardPayload:
    v = _validator_for(THEORY_CARD_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        raise _schema_error(
            schema_id=THEORY_CARD_SCHEMA_ID,
            contract_type="THEORY_CARD",
            error=e,
        ) from e
    try:
        return TheoryCardPayload.model_validate(data)
    except ValueError as e:
        raise _model_error(
            schema_id=THEORY_CARD_SCHEMA_ID,
            contract_type="THEORY_CARD",
            error=e,
        ) from e


def validate_response_control_assessment_json(
    data: dict[str, Any],
) -> ResponseControlAssessment:
    v = _validator_for(RESPONSE_CONTROL_ASSESSMENT_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        raise _schema_error(
            schema_id=RESPONSE_CONTROL_ASSESSMENT_SCHEMA_ID,
            contract_type="RESPONSE_CONTROL_ASSESSMENT",
            error=e,
        ) from e
    try:
        return ResponseControlAssessment.model_validate(data)
    except ValueError as e:
        raise _model_error(
            schema_id=RESPONSE_CONTROL_ASSESSMENT_SCHEMA_ID,
            contract_type="RESPONSE_CONTROL_ASSESSMENT",
            error=e,
        ) from e


def validate_recipe_object_json(data: dict[str, Any]) -> RecipeObjectPayload:
    v = _validator_for(RECIPE_OBJECT_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        raise _schema_error(
            schema_id=RECIPE_OBJECT_SCHEMA_ID,
            contract_type="RECIPE_OBJECT",
            error=e,
        ) from e
    try:
        return RecipeObjectPayload.model_validate(data)
    except ValueError as e:
        raise _model_error(
            schema_id=RECIPE_OBJECT_SCHEMA_ID,
            contract_type="RECIPE_OBJECT",
            error=e,
        ) from e


def validate_execution_adapter_spec_json(data: dict[str, Any]) -> ExecutionAdapterSpecPayload:
    v = _validator_for(EXECUTION_ADAPTER_SPEC_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        raise _schema_error(
            schema_id=EXECUTION_ADAPTER_SPEC_SCHEMA_ID,
            contract_type="EXECUTION_ADAPTER_SPEC",
            error=e,
        ) from e
    try:
        return ExecutionAdapterSpecPayload.model_validate(data)
    except ValueError as e:
        raise _model_error(
            schema_id=EXECUTION_ADAPTER_SPEC_SCHEMA_ID,
            contract_type="EXECUTION_ADAPTER_SPEC",
            error=e,
        ) from e


def validate_evidence_bundle_json(data: dict[str, Any]) -> EvidenceBundlePayload:
    v = _validator_for(EVIDENCE_BUNDLE_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        raise _schema_error(
            schema_id=EVIDENCE_BUNDLE_SCHEMA_ID,
            contract_type="EVIDENCE_BUNDLE",
            error=e,
        ) from e
    try:
        return EvidenceBundlePayload.model_validate(data)
    except ValueError as e:
        raise _model_error(
            schema_id=EVIDENCE_BUNDLE_SCHEMA_ID,
            contract_type="EVIDENCE_BUNDLE",
            error=e,
        ) from e


def validate_role_context_bundle_json(data: dict[str, Any]) -> RoleContextBundlePayload:
    v = _validator_for(ROLE_CONTEXT_BUNDLE_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        raise _schema_error(
            schema_id=ROLE_CONTEXT_BUNDLE_SCHEMA_ID,
            contract_type="ROLE_CONTEXT_BUNDLE",
            error=e,
        ) from e
    try:
        return RoleContextBundlePayload.model_validate(data)
    except ValueError as e:
        raise _model_error(
            schema_id=ROLE_CONTEXT_BUNDLE_SCHEMA_ID,
            contract_type="ROLE_CONTEXT_BUNDLE",
            error=e,
        ) from e


def validate_environment_spec_json(data: dict[str, Any]) -> EnvironmentSpecPayload:
    v = _validator_for(ENVIRONMENT_SPEC_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        raise _schema_error(
            schema_id=ENVIRONMENT_SPEC_SCHEMA_ID,
            contract_type="ENVIRONMENT_SPEC",
            error=e,
        ) from e
    try:
        return EnvironmentSpecPayload.model_validate(data)
    except ValueError as e:
        raise _model_error(
            schema_id=ENVIRONMENT_SPEC_SCHEMA_ID,
            contract_type="ENVIRONMENT_SPEC",
            error=e,
        ) from e


def validate_gui_session_spec_json(data: dict[str, Any]) -> GuiSessionSpecPayload:
    v = _validator_for(GUI_SESSION_SPEC_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        raise _schema_error(
            schema_id=GUI_SESSION_SPEC_SCHEMA_ID,
            contract_type="GUI_SESSION_SPEC",
            error=e,
        ) from e
    try:
        return GuiSessionSpecPayload.model_validate(data)
    except ValueError as e:
        raise _model_error(
            schema_id=GUI_SESSION_SPEC_SCHEMA_ID,
            contract_type="GUI_SESSION_SPEC",
            error=e,
        ) from e


def validate_decision_log_json(data: dict[str, Any]) -> DecisionLogPayload:
    v = _validator_for(DECISION_LOG_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        raise _schema_error(
            schema_id=DECISION_LOG_SCHEMA_ID,
            contract_type="DECISION_LOG",
            error=e,
        ) from e
    try:
        return DecisionLogPayload.model_validate(data)
    except ValueError as e:
        raise _model_error(
            schema_id=DECISION_LOG_SCHEMA_ID,
            contract_type="DECISION_LOG",
            error=e,
        ) from e


def validate_verification_report_json(data: dict[str, Any]) -> VerificationReportPayload:
    v = _validator_for(VERIFICATION_REPORT_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        raise _schema_error(
            schema_id=VERIFICATION_REPORT_SCHEMA_ID,
            contract_type="VERIFICATION_REPORT",
            error=e,
        ) from e
    try:
        return VerificationReportPayload.model_validate(data)
    except ValueError as e:
        raise _model_error(
            schema_id=VERIFICATION_REPORT_SCHEMA_ID,
            contract_type="VERIFICATION_REPORT",
            error=e,
        ) from e


def validate_problem_brief_json(data: dict[str, Any]) -> ProblemBrief:
    """JSON Schema + Pydantic consumer conformance for problem_brief."""
    v = _validator_for(PROBLEM_BRIEF_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        path = "/" + "/".join(str(p) for p in e.absolute_path) if e.absolute_path else "/"
        raise ContractValidationError(
            error_code="SCHEMA_VALIDATION_FAILED",
            contract_type="PROBLEM_BRIEF",
            schema_id=PROBLEM_BRIEF_SCHEMA_ID,
            details=[
                ContractErrorDetail(path=path, message=e.message, keyword=e.validator)
            ],
        ) from e
    try:
        return ProblemBrief.model_validate(data)
    except ValueError as e:
        raise ContractValidationError(
            error_code="SCHEMA_VALIDATION_FAILED",
            contract_type="PROBLEM_BRIEF",
            schema_id=PROBLEM_BRIEF_SCHEMA_ID,
            details=[ContractErrorDetail(path="/", message=str(e), keyword="model_validate")],
        ) from e


def validate_task_queue_json(data: dict[str, Any]) -> TaskQueue:
    """JSON Schema + Pydantic consumer conformance for task_queue."""
    v = _validator_for(TASK_QUEUE_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        path = "/" + "/".join(str(p) for p in e.absolute_path) if e.absolute_path else "/"
        raise ContractValidationError(
            error_code="SCHEMA_VALIDATION_FAILED",
            contract_type="TASK_QUEUE",
            schema_id=TASK_QUEUE_SCHEMA_ID,
            details=[
                ContractErrorDetail(path=path, message=e.message, keyword=e.validator)
            ],
        ) from e
    try:
        return TaskQueue.model_validate(data)
    except ValueError as e:
        raise ContractValidationError(
            error_code="SCHEMA_VALIDATION_FAILED",
            contract_type="TASK_QUEUE",
            schema_id=TASK_QUEUE_SCHEMA_ID,
            details=[ContractErrorDetail(path="/", message=str(e), keyword="model_validate")],
        ) from e


def validate_engineering_state_json(data: dict[str, Any]) -> EngineeringState:
    """JSON Schema + Pydantic consumer conformance for engineering_state."""
    v = _validator_for(ENGINEERING_STATE_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        path = "/" + "/".join(str(p) for p in e.absolute_path) if e.absolute_path else "/"
        raise ContractValidationError(
            error_code="SCHEMA_VALIDATION_FAILED",
            contract_type="ENGINEERING_STATE",
            schema_id=ENGINEERING_STATE_SCHEMA_ID,
            details=[
                ContractErrorDetail(path=path, message=e.message, keyword=e.validator)
            ],
        ) from e
    try:
        return EngineeringState.model_validate(data)
    except ValueError as e:
        raise ContractValidationError(
            error_code="SCHEMA_VALIDATION_FAILED",
            contract_type="ENGINEERING_STATE",
            schema_id=ENGINEERING_STATE_SCHEMA_ID,
            details=[ContractErrorDetail(path="/", message=str(e), keyword="model_validate")],
        ) from e


def validate_routing_policy_json(data: dict[str, Any]) -> RoutingPolicy:
    """JSON Schema + Pydantic consumer conformance for routing_policy."""
    v = _validator_for(ROUTING_POLICY_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        path = "/" + "/".join(str(p) for p in e.absolute_path) if e.absolute_path else "/"
        raise ContractValidationError(
            error_code="SCHEMA_VALIDATION_FAILED",
            contract_type="ROUTING_POLICY",
            schema_id=ROUTING_POLICY_SCHEMA_ID,
            details=[
                ContractErrorDetail(path=path, message=e.message, keyword=e.validator)
            ],
        ) from e
    try:
        return RoutingPolicy.model_validate(data)
    except ValueError as e:
        raise ContractValidationError(
            error_code="SCHEMA_VALIDATION_FAILED",
            contract_type="ROUTING_POLICY",
            schema_id=ROUTING_POLICY_SCHEMA_ID,
            details=[ContractErrorDetail(path="/", message=str(e), keyword="model_validate")],
        ) from e


def validate_wiki_edit_proposal_json(data: dict[str, Any]) -> WikiEditProposalPayload:
    """JSON Schema + Pydantic consumer conformance for wiki_edit_proposal."""
    v = _validator_for(WIKI_EDIT_PROPOSAL_SCHEMA_ID)
    try:
        v.validate(data)
    except jsonschema.exceptions.ValidationError as e:
        path = "/" + "/".join(str(p) for p in e.absolute_path) if e.absolute_path else "/"
        raise ContractValidationError(
            error_code="SCHEMA_VALIDATION_FAILED",
            contract_type="WIKI_EDIT_PROPOSAL",
            schema_id=WIKI_EDIT_PROPOSAL_SCHEMA_ID,
            details=[
                ContractErrorDetail(path=path, message=e.message, keyword=e.validator)
            ],
        ) from e
    try:
        return WikiEditProposalPayload.model_validate(data)
    except ValueError as e:
        raise ContractValidationError(
            error_code="SCHEMA_VALIDATION_FAILED",
            contract_type="WIKI_EDIT_PROPOSAL",
            schema_id=WIKI_EDIT_PROPOSAL_SCHEMA_ID,
            details=[ContractErrorDetail(path="/", message=str(e), keyword="model_validate")],
        ) from e
