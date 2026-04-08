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
    EngineeringState,
    ProblemBrief,
    RoutingPolicy,
    TaskPacket,
    TaskQueue,
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
TASK_QUEUE_SCHEMA_ID = "https://birtha.local/schemas/control-plane/v1/task-queue.schema.json"
ENGINEERING_STATE_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/engineering-state.schema.json"
)
ROUTING_POLICY_SCHEMA_ID = (
    "https://birtha.local/schemas/control-plane/v1/routing-policy.schema.json"
)


def _repo_root() -> Path:
    """Walk up from this file until `schemas/control-plane/v1` exists."""
    here = Path(__file__).resolve()
    for p in [here, *here.parents]:
        if (p / "schemas" / "control-plane" / "v1" / "registry.json").exists():
            return p
    raise RuntimeError("Could not locate repo root (schemas/control-plane/v1 missing)")


def _load_registry_store() -> dict[str, dict[str, Any]]:
    root = _repo_root()
    reg_path = root / "schemas" / "control-plane" / "v1" / "registry.json"
    manifest = json.loads(reg_path.read_text(encoding="utf-8"))
    store: dict[str, dict[str, Any]] = {}
    for entry in manifest.get("schemas", []):
        path = root / "schemas" / "control-plane" / "v1" / entry["path"]
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
