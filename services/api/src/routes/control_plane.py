"""
Internal control-plane contract endpoints: validation, structure routing bridge.

For agents: used by agent-platform LangGraph nodes and operators; not a public IDE surface.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..control_plane.errors import ContractValidationError
from ..control_plane.structure_bridge import classify_user_input
from ..control_plane.validation import validate_task_packet_json

router = APIRouter(prefix="/api/control-plane", tags=["control-plane"])


class ValidateTaskPacketRequest(BaseModel):
    """Raw task_packet JSON to validate."""

    task_packet: dict[str, Any]


class StructureClassifyRequest(BaseModel):
    user_input: str = Field(..., min_length=1)
    request_id: str | None = None


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
