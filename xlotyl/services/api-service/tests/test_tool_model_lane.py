"""Tests for the tool-model lane handler."""

from __future__ import annotations

import json
import os
from pathlib import Path

import jsonschema
import pytest
from jsonschema import Draft202012Validator

from birtha_tool_model.handler import process_tool_query
from birtha_tool_model.paths import tool_model_schema_dir
from birtha_tool_model.registry import load_registry, tool_class


def _response_validator() -> Draft202012Validator:
    base = tool_model_schema_dir()
    with (base / "tool-query-response.schema.json").open(encoding="utf-8") as f:
        schema = json.load(f)
    return Draft202012Validator(schema)


def _minimal_request(tool_name: str = "summarize_snippet") -> dict:
    return {
        "tool_name": tool_name,
        "tool_version": "1.0.0",
        "tool_goal": "Summarize the snippet",
        "input_payload": {"text": "hello"},
        "openclaw_bridge": {"idempotency_key": "k1", "tool_call_id": "tc1"},
    }


def test_registry_loads() -> None:
    reg = load_registry()
    assert reg["version"] == "1"
    assert tool_class("summarize_snippet") == "B"
    assert tool_class("engineering_analysis") == "C"


def test_class_a_rejected() -> None:
    body = _minimal_request("format_markdown")
    out = process_tool_query(body)
    assert out["result_type"] == "tool_result_rejected"
    assert out["error_code"] == "tool_class_forbidden"


def test_class_c_rejected() -> None:
    body = _minimal_request("engineering_analysis")
    out = process_tool_query(body)
    assert out["result_type"] == "tool_result_rejected"


def test_class_b_escalates_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BIRTHA_TOOL_MODEL_MOCK", raising=False)
    body = _minimal_request("summarize_snippet")
    out = process_tool_query(body)
    assert out["result_type"] == "tool_result_needs_governed_escalation"
    _response_validator().validate(out)


def test_class_b_mock_structured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIRTHA_TOOL_MODEL_MOCK", "1")
    body = _minimal_request("summarize_snippet")
    out = process_tool_query(body)
    assert out["result_type"] == "tool_result_structured"
    assert out["provenance"]["lane"] == "tool_model"
    assert out["provenance"]["authoritative"] is False
    _response_validator().validate(out)


def test_invalid_request() -> None:
    body = {"tool_name": "x"}
    out = process_tool_query(body)
    assert out["result_type"] == "tool_result_rejected"
    assert out["error_code"] == "schema_validation_failed"


def test_fastapi_route() -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from birtha_tool_model.router import get_tool_query_router

    app = FastAPI()
    app.include_router(get_tool_query_router())
    client = TestClient(app)
    body = _minimal_request()
    resp = client.post("/api/ai/tool-query", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert "result_type" in data
