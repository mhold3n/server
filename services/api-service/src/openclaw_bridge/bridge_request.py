"""Shared OpenClaw bridge request preparation for ``/api/ai/query`` and ``/query/stream``.

For agents: validates ``context.openclaw_bridge`` and merges continuity fields.
Idempotency Redis replay remains specific to the non-streaming JSON route.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel

from .validate import (
    OpenClawBridgeValidationError,
    apply_bridge_continuity_to_context,
    validate_openclaw_bridge_in_context,
)


def validate_and_merge_openclaw_bridge(req: BaseModel) -> tuple[BaseModel, str | None]:
    """Return ``(updated_req, idempotency_key)`` after schema validation and context merge.

    ``req`` must support ``.context`` and ``.model_copy(update=...)`` like ``QueryRequest``.
    """
    ctx = getattr(req, "context", None)
    idem_key: str | None = None
    if ctx is not None and isinstance(ctx, dict) and "openclaw_bridge" in ctx:
        try:
            merged_ctx = dict(ctx)
            bridge_obj = validate_openclaw_bridge_in_context(merged_ctx)
            merged_ctx = apply_bridge_continuity_to_context(merged_ctx, bridge_obj)
            req = req.model_copy(update={"context": merged_ctx})
            raw_ik = bridge_obj.get("idempotency_key")
            if isinstance(raw_ik, str) and raw_ik.strip():
                idem_key = raw_ik.strip()
        except OpenClawBridgeValidationError as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": exc.code,
                    "message": exc.message,
                    **exc.details,
                },
            ) from exc
    return req, idem_key


def extract_post_completion_events(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive optional typed events from a finished orchestrator payload (MVP).

    For agents: agent-platform today returns a single JSON response per execute;
    this helper synthesizes at most one ``pending_mode_change`` shell event when
    the final snapshot includes a structured pending mode change.
    """
    out: list[dict[str, Any]] = []
    inner = result.get("result")
    if not isinstance(inner, dict):
        return out
    pending = inner.get("pending_mode_change")
    if isinstance(pending, dict) and pending:
        out.append(
            {
                "type": "pending_mode_change",
                "payload": pending,
            }
        )
    return out
