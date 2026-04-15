"""Typed SSE adapter for ``POST /api/ai/query/stream`` (OpenClaw bridge Phase 3).

For agents: centralizes SSE framing and event ordering. Emits only JSON objects
intended to match ``schemas/openclaw-bridge/v1/events/stream-event.schema.json``.
No raw LangGraph / orchestrator log lines.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

ExecutePipeline = Callable[[Any], Awaitable[dict[str, Any]]]
PostCompletionFn = Callable[[dict[str, Any]], list[dict[str, Any]]]


def stream_event_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_sse_data_line(event_id: int, body: dict[str, Any]) -> str:
    """One SSE ``data:`` line (including trailing blank line)."""
    payload = {
        **body,
        "version": "1.0.0",
        "event_id": str(event_id),
        "ts": body.get("ts") or stream_event_ts(),
    }
    return f"data: {json.dumps(payload, default=str)}\n\n"


def engineering_session_id_from_request(req: Any) -> str | None:
    """Best-effort read of ``context.engineering_session_id`` for resume.ack payloads."""
    ctx = getattr(req, "context", None)
    if not isinstance(ctx, dict):
        return None
    raw = ctx.get("engineering_session_id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    bridge = ctx.get("openclaw_bridge")
    if isinstance(bridge, dict):
        b = bridge.get("engineering_session_id")
        if isinstance(b, str) and b.strip():
            return b.strip()
    return None


def build_cancel_ack_dict(*, workflow_id: str, event_id: int = 1) -> dict[str, Any]:
    """JSON object matching the ``cancel.ack`` stream-event shape (non-SSE HTTP use)."""
    return {
        "type": "cancel.ack",
        "version": "1.0.0",
        "event_id": str(event_id),
        "ts": stream_event_ts(),
        "payload": {"workflow_id": workflow_id},
    }


async def iter_query_stream_events(
    *,
    req_merged: Any,
    execute_pipeline: ExecutePipeline,
    extract_post_completion_events_fn: PostCompletionFn,
    last_event_id: str | None = None,
    event_cursor: str | None = None,
) -> AsyncIterator[str]:
    """Yield SSE chunks for one query/stream request (MVP single-shot execute)."""
    eid = 0
    lid = last_event_id.strip() if isinstance(last_event_id, str) and last_event_id.strip() else ""
    cur = event_cursor.strip() if isinstance(event_cursor, str) and event_cursor.strip() else ""
    if lid or cur:
        eid += 1
        resume_payload: dict[str, Any] = {}
        if lid:
            resume_payload["last_event_id"] = lid
        if cur:
            resume_payload["event_cursor"] = cur
        eng = engineering_session_id_from_request(req_merged)
        if eng:
            resume_payload["engineering_session_id"] = eng
        yield format_sse_data_line(
            eid,
            {"type": "resume.ack", "payload": resume_payload},
        )

    eid += 1
    yield format_sse_data_line(
        eid,
        {
            "type": "run.started",
            "payload": {
                "transport": "sse_mvp",
                "note": "single_shot_execute_until_streaming_backend",
            },
        },
    )
    try:
        result = await execute_pipeline(req_merged)
    except HTTPException as he:
        eid += 1
        detail = he.detail
        msg = detail if isinstance(detail, str) else json.dumps(detail, default=str)
        yield format_sse_data_line(
            eid,
            {
                "type": "run.failed",
                "payload": {"code": str(he.status_code), "message": msg},
            },
        )
        return

    wf_id = result.get("workflow_id") if isinstance(result, dict) else None
    inner = result.get("result") if isinstance(result, dict) else {}
    eng_sid = None
    run_id = None
    if isinstance(inner, dict):
        rs = inner.get("referential_state")
        if isinstance(rs, dict):
            v = rs.get("engineering_session_id")
            eng_sid = v if isinstance(v, str) else None
            v2 = rs.get("run_id")
            run_id = v2 if isinstance(v2, str) else None

    eid += 1
    yield format_sse_data_line(
        eid,
        {
            "type": "run.completed",
            "workflow_id": wf_id,
            "engineering_session_id": eng_sid,
            "run_id": run_id,
            "payload": {"cached": False},
        },
    )
    if isinstance(result, dict):
        for extra in extract_post_completion_events_fn(result):
            eid += 1
            yield format_sse_data_line(eid, extra)
