"""
Internal control-plane contract endpoints: validation, structure routing bridge.

For agents: used by agent-platform LangGraph nodes and operators; not a public IDE surface.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..control_plane.engineering import (
    build_escalation_packet,
    build_task_queue,
    derive_engineering_state,
    intake_engineering_request,
)
from ..control_plane.errors import ContractValidationError
from ..control_plane.structure_bridge import classify_user_input
from ..control_plane.validation import (
    validate_engineering_state_json,
    validate_problem_brief_json,
    validate_task_packet_json,
)
from .devplane import get_service

router = APIRouter(prefix="/api/control-plane", tags=["control-plane"])


class ValidateTaskPacketRequest(BaseModel):
    """Raw task_packet JSON to validate."""

    task_packet: dict[str, Any]


class StructureClassifyRequest(BaseModel):
    user_input: str = Field(..., min_length=1)
    request_id: str | None = None


class EngineeringIntakeRequest(BaseModel):
    user_input: str | None = None
    messages: list[dict[str, Any]] | None = None
    context: dict[str, Any] | None = None
    session_id: str | None = None
    task_id: str | None = None
    run_id: str | None = None
    task_packet: dict[str, Any] | None = None
    task_plan: dict[str, Any] | None = None
    project_context: dict[str, Any] | None = None
    engagement_mode: str | None = None
    engagement_mode_source: str | None = None
    engagement_mode_confidence: float | None = None
    engagement_mode_reasons: list[str] | None = None
    minimum_engagement_mode: str | None = None
    pending_mode_change: dict[str, Any] | None = None


class DeriveEngineeringStateRequest(BaseModel):
    problem_brief: dict[str, Any]


class BuildTaskQueueRequest(BaseModel):
    problem_brief: dict[str, Any]
    engineering_state: dict[str, Any]


class BuildEscalationRequest(BaseModel):
    engineering_state: dict[str, Any]
    verification_report: dict[str, Any]
    problem_brief_ref: str = Field(..., min_length=1)
    verification_report_ref: str | None = None


@router.post("/validate/task-packet")
async def validate_task_packet(req: ValidateTaskPacketRequest) -> dict[str, Any]:
    """Runtime gate: JSON Schema + Pydantic consumer conformance."""
    try:
        tp = validate_task_packet_json(req.task_packet)
    except ContractValidationError as e:
        raise HTTPException(status_code=422, detail=e.to_envelope()) from e
    return {"ok": True, "task_packet": tp.model_dump(mode="json")}


@router.post("/structure/classify")
async def structure_classify(req: StructureClassifyRequest) -> dict[str, Any]:
    """Invoke services/structure classifier inside the unified control-plane path."""
    try:
        spec = classify_user_input(
            user_input=req.user_input,
            request_id=req.request_id,
        )
    except Exception as e:  # noqa: BLE001 — bridge may fail if structure deps missing
        raise HTTPException(
            status_code=502,
            detail={
                "error_code": "STRUCTURE_CLASSIFY_FAILED",
                "message": str(e),
            },
        ) from e
    return {"ok": True, "task_spec": spec}


@router.post("/engineering/intake")
async def engineering_intake(req: EngineeringIntakeRequest) -> dict[str, Any]:
    """Bridge chat/task-plan/task-packet inputs into governing engineering artifacts."""
    try:
        persisted_snapshot = get_service().load_engineering_session_snapshot(
            session_id=req.session_id,
            task_id=req.task_id,
        )
        return intake_engineering_request(
            user_input=req.user_input,
            messages=req.messages,
            context=req.context,
            session_id=req.session_id,
            persisted_snapshot=persisted_snapshot,
            task_packet=req.task_packet,
            task_plan=req.task_plan,
            project_context=req.project_context,
            engagement_mode=req.engagement_mode,
            engagement_mode_source=req.engagement_mode_source,
            engagement_mode_confidence=req.engagement_mode_confidence,
            engagement_mode_reasons=req.engagement_mode_reasons,
            minimum_engagement_mode=req.minimum_engagement_mode,
            pending_mode_change=req.pending_mode_change,
        )
    except ContractValidationError as e:
        raise HTTPException(status_code=422, detail=e.to_envelope()) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"message": str(e)}) from e


@router.post("/engineering/derive-state")
async def engineering_derive_state(req: DeriveEngineeringStateRequest) -> dict[str, Any]:
    """Derive a deterministic engineering_state from a valid problem_brief."""
    try:
        problem_brief = validate_problem_brief_json(req.problem_brief)
        state = derive_engineering_state(problem_brief)
    except ContractValidationError as e:
        raise HTTPException(status_code=422, detail=e.to_envelope()) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"message": str(e)}) from e
    return {"ok": True, "engineering_state": state.model_dump(mode="json", exclude_none=True)}


@router.post("/engineering/build-task-queue")
async def engineering_build_task_queue(req: BuildTaskQueueRequest) -> dict[str, Any]:
    """Build a governed task_queue only when engineering_state is ready."""
    try:
        problem_brief = validate_problem_brief_json(req.problem_brief)
        engineering_state = validate_engineering_state_json(req.engineering_state)
        task_queue, task_packets = build_task_queue(
            problem_brief=problem_brief,
            engineering_state=engineering_state,
        )
    except ContractValidationError as e:
        raise HTTPException(status_code=422, detail=e.to_envelope()) from e
    except ValueError as e:
        raise HTTPException(status_code=409, detail={"message": str(e)}) from e
    return {
        "ok": True,
        "task_queue": task_queue.model_dump(mode="json", exclude_none=True),
        "task_packets": [
            packet.model_dump(mode="json", exclude_none=True) for packet in task_packets
        ],
    }


@router.post("/engineering/build-escalation")
async def engineering_build_escalation(req: BuildEscalationRequest) -> dict[str, Any]:
    """Create a typed escalation packet from verification/conflict artifacts."""
    try:
        escalation = build_escalation_packet(
            engineering_state=req.engineering_state,
            verification_report=req.verification_report,
            problem_brief_ref=req.problem_brief_ref,
            verification_report_ref=req.verification_report_ref,
        )
    except ContractValidationError as e:
        raise HTTPException(status_code=422, detail=e.to_envelope()) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"message": str(e)}) from e
    return {"ok": True, "escalation_packet": escalation.model_dump(mode="json", exclude_none=True)}
