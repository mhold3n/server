"""Core handler for POST /api/ai/tool-query."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

from birtha_tool_model.observability import ToolModelMetrics, log_lane_event, metrics
from birtha_tool_model.paths import tool_model_schema_dir
from birtha_tool_model.registry import assert_class_b

# Validators loaded once
_VALIDATORS: tuple[Draft202012Validator, Draft202012Validator] | None = None


def _validators() -> tuple[Draft202012Validator, Draft202012Validator]:
    global _VALIDATORS
    if _VALIDATORS is not None:
        return _VALIDATORS
    base = tool_model_schema_dir()
    with (base / "tool-query-request.schema.json").open(encoding="utf-8") as f:
        req_schema = json.load(f)
    with (base / "tool-query-response.schema.json").open(encoding="utf-8") as f:
        res_schema = json.load(f)
    _VALIDATORS = (
        Draft202012Validator(req_schema),
        Draft202012Validator(res_schema),
    )
    return _VALIDATORS


def _validate_request(body: dict[str, Any]) -> str | None:
    """Return error message if request JSON invalid."""
    v = _validators()[0]
    try:
        v.validate(body)
    except jsonschema.ValidationError as e:
        return str(e.message)
    return None


def _provenance(
    *,
    tool_name: str,
    tool_call_id: str,
    model_used: str,
) -> dict[str, Any]:
    return {
        "origin": "openclaw_tool",
        "tool_name": tool_name,
        "tool_call_id": tool_call_id,
        "model_used": model_used,
        "lane": "tool_model",
        "confidence_mode": "preliminary",
        "mutation_rights": "none",
        "authoritative": False,
        "requires_validation": True,
    }


def process_tool_query(body: dict[str, Any]) -> dict[str, Any]:
    """
    Process a tool-model request. Does not call external LLMs unless ``BIRTHA_TOOL_MODEL_MOCK=1``.

    Returns a response dict matching ``tool-query-response.schema.json``.
    """
    m: ToolModelMetrics = metrics()
    m.requests += 1

    err = _validate_request(body)
    if err:
        m.rejected_schema += 1
        log_lane_event("request_schema_invalid", extra={"detail": err[:200]})
        return {
            "result_type": "tool_result_rejected",
            "error_code": "schema_validation_failed",
            "message": err,
        }

    tool_name = str(body["tool_name"])
    bridge = body.get("openclaw_bridge") or {}
    correlation_id = None
    if isinstance(bridge, dict):
        correlation_id = bridge.get("correlation_id") or bridge.get("request_id")

    ok, reason = assert_class_b(tool_name)
    if not ok:
        m.rejected_class += 1
        log_lane_event(
            "tool_class_rejected",
            tool_name=tool_name,
            correlation_id=str(correlation_id) if correlation_id else None,
            extra={"reason": reason},
        )
        code = "unknown_tool" if reason == "unknown_tool" else "tool_class_forbidden"
        msg = (
            "Tool is not registered for the tool-model lane"
            if code == "unknown_tool"
            else "Tool class must not use POST /api/ai/tool-query (use local shell or governed ingress)"
        )
        return {
            "result_type": "tool_result_rejected",
            "error_code": code,
            "message": msg,
            "detail": {"reason": reason},
        }

    tool_call_id = str(bridge.get("tool_call_id") or uuid.uuid4())
    model_used = os.environ.get("BIRTHA_TOOL_MODEL_NAME", "tool-model-stub")

    if os.environ.get("BIRTHA_TOOL_MODEL_MOCK") == "1":
        m.structured_ok += 1
        log_lane_event(
            "mock_structured_result",
            tool_name=tool_name,
            correlation_id=str(correlation_id) if correlation_id else None,
        )
        return {
            "result_type": "tool_result_structured",
            "provenance": _provenance(
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                model_used=model_used,
            ),
            "payload": {
                "echo_goal": body.get("tool_goal"),
                "mock": True,
            },
        }

    # Production default: escalate to governed path — no silent LLM without configured backend.
    m.escalations += 1
    log_lane_event(
        "escalate_governed",
        tool_name=tool_name,
        correlation_id=str(correlation_id) if correlation_id else None,
    )
    out: dict[str, Any] = {
        "result_type": "tool_result_needs_governed_escalation",
        "reason_code": "policy_requires_governed_run",
        "handoff_hint": {
            "suggested_ingress": "POST /api/ai/query",
            "tool_name": tool_name,
            "tool_goal": body.get("tool_goal"),
        },
    }
    prov = _provenance(
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        model_used=model_used,
    )
    out["provenance"] = prov
    return out
