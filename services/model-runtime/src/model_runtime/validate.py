"""JSON Schema validation helpers + orchestration provenance runtime rules."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema import RefResolver

from model_runtime.schema_store import build_validator_store

_ORCH_ID = "https://birtha.local/schemas/model-runtime/v1/orchestration_packet.schema.json"
_SOLVE_ID = "https://birtha.local/schemas/model-runtime/v1/solve_mechanics_request_v1.schema.json"
_TASK_ID = "https://birtha.local/schemas/control-plane/v1/task-packet.schema.json"


def _validator_for(schema_id: str) -> Draft202012Validator:
    store = build_validator_store()
    resolver = RefResolver(base_uri="", referrer=None, store=store)
    return Draft202012Validator(store[schema_id], resolver=resolver)


_orch_val = None
_solve_val = None
_task_val = None


def orch_validator() -> Draft202012Validator:
    global _orch_val
    if _orch_val is None:
        _orch_val = _validator_for(_ORCH_ID)
    return _orch_val


def solve_validator() -> Draft202012Validator:
    global _solve_val
    if _solve_val is None:
        _solve_val = _validator_for(_SOLVE_ID)
    return _solve_val


def task_validator() -> Draft202012Validator:
    global _task_val
    if _task_val is None:
        _task_val = _validator_for(_TASK_ID)
    return _task_val


CODING_ALLOWED_TASK_TYPES = frozenset(
    {"CODEGEN", "TRANSFORM", "VALIDATION_CODE"},
)
MULTIMODAL_TASK_TYPE = "MULTIMODAL_EXTRACTION"


def validate_orchestration_packet(
    body: dict[str, Any],
    *,
    workflow_root: bool,
) -> None:
    orch_validator().validate(body)
    prov = body.get("provenance") or {}
    parent = prov.get("parent_packet_id")
    if workflow_root:
        if parent is not None:
            raise ValueError("workflow_root=true requires provenance.parent_packet_id null")
    else:
        if parent is None:
            raise ValueError(
                "descendant packet requires non-null provenance.parent_packet_id "
                "and workflow_root=false",
            )


def validate_task_packet_coding(body: dict[str, Any]) -> None:
    task_validator().validate(body)
    tt = body.get("task_type")
    if tt not in CODING_ALLOWED_TASK_TYPES:
        raise ValueError(f"task_type {tt!r} not allowed on /infer/coding")


def validate_task_packet_multimodal(body: dict[str, Any]) -> None:
    task_validator().validate(body)
    if body.get("task_type") != MULTIMODAL_TASK_TYPE:
        raise ValueError("multimodal endpoint requires task_type=MULTIMODAL_EXTRACTION")


def validate_solve_request(body: dict[str, Any]) -> None:
    solve_validator().validate(body)
