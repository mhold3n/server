"""HTTP tests for model-runtime (MOCK_INFER, no torch)."""

from __future__ import annotations

import os
import json
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import pytest
from fastapi.testclient import TestClient

os.environ["MOCK_INFER"] = "1"

from model_runtime.app import app

RESPONSE_SCHEMA = (
    Path(__file__).resolve().parents[3]
    / "schemas"
    / "model-runtime"
    / "v1"
    / "model_runtime_response.schema.json"
)


def assert_model_runtime_response(body: dict) -> None:
    schema = json.loads(RESPONSE_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(body, schema)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_infer_general_root_and_solve_e2e(client: TestClient) -> None:
    orch = {
        "packet_id": "11111111-1111-4111-8111-111111111111",
        "packet_class": "ORCHESTRATION",
        "operation": "INTAKE",
        "objective": "Sliding block",
        "context_summary": "",
        "constraints": [],
        "expected_output": {
            "artifact_type": "PROBLEM_BRIEF",
            "schema_id": "urn:claw:schema:problem-brief:1.0",
            "cardinality": "ONE",
            "allow_partial": False,
        },
        "routing_metadata": {
            "selected_executor": "GENERAL_LOCAL",
            "selection_reason_code": "OPERATION_MATCH",
            "selection_reason_detail": "test",
            "policy_version": "v1",
            "budget_policy": {"allow_escalation": False},
        },
        "provenance": {
            "source_stage": "INTAKE",
            "parent_packet_id": None,
            "input_artifact_refs": [],
            "decision_ref": None,
        },
    }
    r = client.post("/infer/general?workflow_root=true", json=orch)
    assert r.status_code == 200
    body = r.json()
    assert_model_runtime_response(body)
    assert body["model_id_resolved"]

    solve_body = {
        "schema_version": "1.0.0",
        "assumption_profile_id": "RIGID_BLOCK_DRY_SLIDING_V1",
        "assumption_overrides": {"fluid_id": None, "viscous_enabled": False},
        "geometry": {"shape": "CUBE", "cube_side_m": 1.0},
        "block_material_id": "steel_7850",
        "surface_material_id": "concrete_rough",
        "fluid_id": None,
        "applied_force_N": 40000.0,
        "force_direction_assumption": "horizontal_in_plane",
        "displacement_m": 1.0,
    }
    s = client.post("/solve/mechanics", json=solve_body)
    assert s.status_code == 200
    rep = s.json()
    assert rep["schema_version"] == "1.0.0"
    v = client.post("/solve/verify", json=rep)
    assert v.status_code == 200
    assert v.json()["status"] == "PASS"


def test_infer_general_descendant_requires_parent(client: TestClient) -> None:
    orch = {
        "packet_id": "22222222-2222-4222-8222-222222222222",
        "packet_class": "ORCHESTRATION",
        "operation": "SYNTHESIZE",
        "objective": "x",
        "context_summary": "",
        "constraints": [],
        "expected_output": {
            "artifact_type": "PROBLEM_BRIEF",
            "schema_id": "urn:claw:schema:problem-brief:1.0",
            "cardinality": "ONE",
            "allow_partial": False,
        },
        "routing_metadata": {
            "selected_executor": "GENERAL_LOCAL",
            "selection_reason_code": "OPERATION_MATCH",
            "selection_reason_detail": "x",
            "policy_version": "v1",
            "budget_policy": {"allow_escalation": False},
        },
        "provenance": {
            "source_stage": "SYNTHESIZE",
            "parent_packet_id": None,
            "input_artifact_refs": [],
            "decision_ref": None,
        },
    }
    r = client.post("/infer/general?workflow_root=false", json=orch)
    assert r.status_code == 422


def test_infer_general_non_mock_uses_hf_runtime(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    orch = {
        "packet_id": "11111111-1111-4111-8111-111111111111",
        "packet_class": "ORCHESTRATION",
        "operation": "INTAKE",
        "objective": "Sliding block",
        "context_summary": "",
        "constraints": [],
        "expected_output": {
            "artifact_type": "PROBLEM_BRIEF",
            "schema_id": "urn:claw:schema:problem-brief:1.0",
            "cardinality": "ONE",
            "allow_partial": False,
        },
        "routing_metadata": {
            "selected_executor": "GENERAL_LOCAL",
            "selection_reason_code": "OPERATION_MATCH",
            "selection_reason_detail": "test",
            "policy_version": "v1",
            "budget_policy": {"allow_escalation": False},
        },
        "provenance": {
            "source_stage": "INTAKE",
            "parent_packet_id": None,
            "input_artifact_refs": [],
            "decision_ref": None,
        },
    }

    def fake_infer_with_hf(role: str, system_prompt: str, user_prompt: str) -> SimpleNamespace:
        assert role == "general"
        assert "orchestration_packet" in user_prompt
        return SimpleNamespace(
            latency_ms=12.0,
            prompt_tokens=7,
            completion_tokens=5,
            text='{"summary":"hf path"}',
            structured_output={"summary": "hf path"},
        )

    monkeypatch.setenv("MOCK_INFER", "0")
    monkeypatch.setattr("model_runtime.app.infer_with_hf", fake_infer_with_hf)
    r = client.post("/infer/general?workflow_root=true", json=orch)

    assert r.status_code == 200
    body = r.json()
    assert_model_runtime_response(body)
    assert body["usage"]["prompt_tokens"] == 7
    assert body["usage"]["completion_tokens"] == 5
    assert body["text"] == '{"summary":"hf path"}'
    assert body["structured_output"] == {"summary": "hf path"}


def test_infer_general_root_rejects_non_null_parent(client: TestClient) -> None:
    orch = {
        "packet_id": "11111111-1111-4111-8111-111111111111",
        "packet_class": "ORCHESTRATION",
        "operation": "INTAKE",
        "objective": "Sliding block",
        "context_summary": "",
        "constraints": [],
        "expected_output": {
            "artifact_type": "PROBLEM_BRIEF",
            "schema_id": "urn:claw:schema:problem-brief:1.0",
            "cardinality": "ONE",
            "allow_partial": False,
        },
        "routing_metadata": {
            "selected_executor": "GENERAL_LOCAL",
            "selection_reason_code": "OPERATION_MATCH",
            "selection_reason_detail": "test",
            "policy_version": "v1",
            "budget_policy": {"allow_escalation": False},
        },
        "provenance": {
            "source_stage": "INTAKE",
            "parent_packet_id": "22222222-2222-4222-8222-222222222222",
            "input_artifact_refs": [],
            "decision_ref": None,
        },
    }
    r = client.post("/infer/general?workflow_root=true", json=orch)
    assert r.status_code == 422


def test_infer_general_omitted_input_artifact_refs_fails_schema(client: TestClient) -> None:
    orch = {
        "packet_id": "11111111-1111-4111-8111-111111111111",
        "packet_class": "ORCHESTRATION",
        "operation": "INTAKE",
        "objective": "Sliding block",
        "context_summary": "",
        "constraints": [],
        "expected_output": {
            "artifact_type": "PROBLEM_BRIEF",
            "schema_id": "urn:claw:schema:problem-brief:1.0",
            "cardinality": "ONE",
            "allow_partial": False,
        },
        "routing_metadata": {
            "selected_executor": "GENERAL_LOCAL",
            "selection_reason_code": "OPERATION_MATCH",
            "selection_reason_detail": "test",
            "policy_version": "v1",
            "budget_policy": {"allow_escalation": False},
        },
        "provenance": {
            "source_stage": "INTAKE",
            "parent_packet_id": None,
            # input_artifact_refs omitted on purpose
            "decision_ref": None,
        },
    }
    r = client.post("/infer/general?workflow_root=true", json=orch)
    assert r.status_code == 422


def test_infer_multimodal_structured_output(client: TestClient) -> None:
    from uuid import uuid4

    pid = str(uuid4())
    tp = {
        "task_packet_id": pid,
        "schema_version": "1.0.0",
        "status": "PENDING",
        "task_type": "MULTIMODAL_EXTRACTION",
        "title": "t",
        "objective": "extract",
        "input_artifact_refs": ["artifact://document_extract/x"],
        "required_outputs": [
            {"artifact_type": "DOCUMENT_EXTRACT", "schema_version": "1.0.0"},
        ],
        "acceptance_criteria": ["c1"],
        "budget_policy": {"allow_escalation": False},
        "routing_metadata": {
            "requested_by": "test",
            "selected_executor": "multimodal_model",
            "reason": "test",
            "router_policy_version": "1",
        },
        "provenance": {"source_stage": "task_generation"},
        "created_at": "2026-04-07T12:00:00Z",
        "updated_at": "2026-04-07T12:00:00Z",
    }
    r = client.post("/infer/multimodal", json=tp)
    assert r.status_code == 200
    body = r.json()
    assert_model_runtime_response(body)
    assert "structured_output" in body
    assert body["structured_output"]["extract_kind"] == "mock_v1"
