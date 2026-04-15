"""Tests for ``openclaw_bridge.stream_adapter`` (typed SSE + cancel_ack JSON)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException
from jsonschema import Draft202012Validator
from src.openclaw_bridge.stream_adapter import (
    build_cancel_ack_dict,
    format_sse_data_line,
    iter_query_stream_events,
)
from src.routes.ai import QueryRequest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_PATH = _REPO_ROOT / "schemas/openclaw-bridge/v1/events/stream-event.schema.json"


@pytest.fixture(scope="module")
def stream_schema_validator() -> Draft202012Validator:
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _parse_sse_data_lines(s: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for block in s.split("\n\n"):
        for line in block.split("\n"):
            if line.startswith("data:"):
                txt = line[5:].strip()
                if txt:
                    out.append(json.loads(txt))
    return out


@pytest.mark.asyncio
async def test_iter_query_stream_events_mvp_order_and_schema(
    stream_schema_validator: Draft202012Validator,
) -> None:
    async def pipe(_req: Any) -> dict[str, Any]:
        return {
            "workflow_id": "wf_test",
            "result": {
                "referential_state": {"engineering_session_id": "eng1", "run_id": "run1"},
                "final_response": "ok",
            },
        }

    chunks: list[str] = []
    req = QueryRequest(prompt="hi")
    async for c in iter_query_stream_events(
        req_merged=req,
        execute_pipeline=pipe,
        extract_post_completion_events_fn=lambda _r: [],
    ):
        chunks.append(c)
    text = "".join(chunks)
    events = _parse_sse_data_lines(text)
    assert [e["type"] for e in events] == ["run.started", "run.completed"]
    for ev in events:
        stream_schema_validator.validate(ev)


@pytest.mark.asyncio
async def test_iter_query_stream_events_resume_prefix_and_schema(
    stream_schema_validator: Draft202012Validator,
) -> None:
    async def pipe(_req: Any) -> dict[str, Any]:
        return {"result": {"final_response": "x"}}

    req = QueryRequest(
        prompt="hi",
        context={"engineering_session_id": "sess-a", "openclaw_bridge": {}},
    )
    chunks: list[str] = []
    async for c in iter_query_stream_events(
        req_merged=req,
        execute_pipeline=pipe,
        extract_post_completion_events_fn=lambda _r: [],
        last_event_id="3",
        event_cursor="opaque-cursor-1",
    ):
        chunks.append(c)
    events = _parse_sse_data_lines("".join(chunks))
    assert events[0]["type"] == "resume.ack"
    assert events[0]["payload"]["last_event_id"] == "3"
    assert events[0]["payload"]["event_cursor"] == "opaque-cursor-1"
    assert events[0]["payload"]["engineering_session_id"] == "sess-a"
    stream_schema_validator.validate(events[0])


@pytest.mark.asyncio
async def test_iter_query_stream_events_run_failed_schema(
    stream_schema_validator: Draft202012Validator,
) -> None:

    async def boom(_req: Any) -> dict[str, Any]:
        raise HTTPException(status_code=422, detail="bad")

    chunks: list[str] = []
    async for c in iter_query_stream_events(
        req_merged=QueryRequest(prompt="x"),
        execute_pipeline=boom,
        extract_post_completion_events_fn=lambda _r: [],
    ):
        chunks.append(c)
    events = _parse_sse_data_lines("".join(chunks))
    assert [e["type"] for e in events] == ["run.started", "run.failed"]
    stream_schema_validator.validate(events[1])


def test_build_cancel_ack_dict_matches_schema(
    stream_schema_validator: Draft202012Validator,
) -> None:
    ack = build_cancel_ack_dict(workflow_id="wf_cancel_1", event_id=9)
    stream_schema_validator.validate(ack)


def test_format_sse_data_line_includes_envelope() -> None:
    line = format_sse_data_line(1, {"type": "run.started", "payload": {}})
    assert line.startswith("data:")
    obj = json.loads(line.split("\n", 1)[0][5:].strip())
    assert obj["version"] == "1.0.0"
    assert obj["event_id"] == "1"
    assert "ts" in obj
