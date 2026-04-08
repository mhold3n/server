"""Tests for control-plane schemas, validation, lifecycle, and API routes."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from src.control_plane.contracts import (
    ArtifactStatus,
    TaskPacketStatus,
    TaskType,
)
from src.control_plane.errors import ContractValidationError
from src.control_plane.lifecycle import (
    assert_artifact_transition,
    assert_task_packet_transition,
)
from src.control_plane.validation import (
    get_schema_store,
    validate_engineering_state_json,
    validate_problem_brief_json,
    validate_routing_policy_json,
    validate_task_packet_json,
    validate_task_queue_json,
    validate_typed_artifact_json,
)
from src.devplane.models import ArtifactRecord, CostLedgerEntry


def _minimal_task_packet_dict() -> dict:
    return {
        "task_packet_id": str(uuid4()),
        "schema_version": "1.0.0",
        "status": "PENDING",
        "task_type": "CODEGEN",
        "title": "t",
        "objective": "o",
        "input_artifact_refs": ["artifact://requirements_set/x"],
        "required_outputs": [{"artifact_type": "CODE_PATCH", "schema_version": "1.0.0"}],
        "acceptance_criteria": ["c1"],
        "budget_policy": {"allow_escalation": False},
        "routing_metadata": {
            "requested_by": "control_plane",
            "selected_executor": "coding_model",
            "reason": "test",
            "router_policy_version": "1",
        },
        "provenance": {"source_stage": "task_generation"},
        "created_at": "2026-04-07T12:00:00Z",
        "updated_at": "2026-04-07T12:00:00Z",
    }


def test_validate_task_packet_json_round_trip() -> None:
    raw = _minimal_task_packet_dict()
    tp = validate_task_packet_json(raw)
    assert tp.task_packet_id == UUID(raw["task_packet_id"])
    assert tp.task_type is TaskType.CODEGEN


def test_validate_task_packet_json_rejects_bad_enum() -> None:
    raw = _minimal_task_packet_dict()
    raw["status"] = "NOT_A_STATUS"
    with pytest.raises(ContractValidationError) as ei:
        validate_task_packet_json(raw)
    assert ei.value.error_code == "SCHEMA_VALIDATION_FAILED"


def test_task_packet_pydantic_invariant_escalation_review() -> None:
    raw = _minimal_task_packet_dict()
    raw["task_type"] = "ESCALATION_REVIEW"
    raw["budget_policy"] = {"allow_escalation": False}
    with pytest.raises(ContractValidationError):
        validate_task_packet_json(raw)


def test_task_packet_validation_type_requires_requirements() -> None:
    raw = _minimal_task_packet_dict()
    raw["task_type"] = "VALIDATION"
    raw["validation_requirements"] = []
    with pytest.raises(ContractValidationError):
        validate_task_packet_json(raw)


def test_lifecycle_task_packet_illegal() -> None:
    with pytest.raises(ContractValidationError):
        assert_task_packet_transition(
            from_status=TaskPacketStatus.COMPLETED,
            to_status=TaskPacketStatus.RUNNING,
        )


def test_lifecycle_artifact_illegal() -> None:
    with pytest.raises(ContractValidationError):
        assert_artifact_transition(
            from_status=ArtifactStatus.SUPERSEDED,
            to_status=ArtifactStatus.ACTIVE,
        )


def test_artifact_record_legacy() -> None:
    a = ArtifactRecord(name="n", path="/p", kind="k")
    assert a.kind == "k"


def test_artifact_record_typed_minimal() -> None:
    now = datetime.now(UTC)
    a = ArtifactRecord(
        artifact_id=str(uuid4()),
        artifact_type="VERIFICATION_REPORT",
        schema_version="1.0.0",
        artifact_status="ACTIVE",
        validation_state="VALID",
        producer={"component": "c", "executor": "e"},
        payload={},
        created_at=now,
        updated_at=now,
    )
    assert a.artifact_type == "VERIFICATION_REPORT"


def test_artifact_record_rejects_partial() -> None:
    with pytest.raises(ValueError):
        ArtifactRecord(name="only")


def test_control_plane_validate_route(test_client: TestClient) -> None:
    r = test_client.post(
        "/api/control-plane/validate/task-packet",
        json={"task_packet": _minimal_task_packet_dict()},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True


def test_control_plane_validate_route_invalid(test_client: TestClient) -> None:
    bad = _minimal_task_packet_dict()
    del bad["acceptance_criteria"]
    r = test_client.post(
        "/api/control-plane/validate/task-packet",
        json={"task_packet": bad},
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error_code"] == "SCHEMA_VALIDATION_FAILED"


def test_structure_classify_route(test_client: TestClient) -> None:
    r = test_client.post(
        "/api/control-plane/structure/classify",
        json={"user_input": "compute Reynolds number for pipe flow"},
    )
    assert r.status_code in (200, 502)
    if r.status_code == 200:
        body = r.json()
        assert body["ok"] is True
        assert "domain" in body["task_spec"]


def test_golden_fixture_file_matches_schema() -> None:
    root = Path(__file__).resolve().parents[3]
    fix = root / "schemas" / "control-plane" / "v1" / "fixtures" / "task-packet" / "valid-minimal.json"
    data = json.loads(fix.read_text(encoding="utf-8"))
    validate_task_packet_json(data)


def test_golden_problem_brief_round_trip() -> None:
    root = Path(__file__).resolve().parents[3]
    fix = root / "schemas" / "control-plane" / "v1" / "fixtures" / "problem-brief" / "valid-minimal.json"
    data = json.loads(fix.read_text(encoding="utf-8"))
    pb = validate_problem_brief_json(data)
    assert pb.title


def test_golden_task_queue_round_trip() -> None:
    root = Path(__file__).resolve().parents[3]
    fix = root / "schemas" / "control-plane" / "v1" / "fixtures" / "task-queue" / "valid-minimal.json"
    data = json.loads(fix.read_text(encoding="utf-8"))
    validate_task_queue_json(data)


def test_golden_engineering_state_round_trip() -> None:
    root = Path(__file__).resolve().parents[3]
    fix = (
        root
        / "schemas"
        / "control-plane"
        / "v1"
        / "fixtures"
        / "engineering-state"
        / "valid-minimal.json"
    )
    data = json.loads(fix.read_text(encoding="utf-8"))
    validate_engineering_state_json(data)


def test_golden_routing_policy_round_trip() -> None:
    root = Path(__file__).resolve().parents[3]
    fix = root / "schemas" / "control-plane" / "v1" / "fixtures" / "routing-policy" / "valid-minimal.json"
    data = json.loads(fix.read_text(encoding="utf-8"))
    validate_routing_policy_json(data)


def test_cost_ledger_entry_model() -> None:
    e = CostLedgerEntry(component="test", tokens_in=1, tokens_out=2)
    assert e.component == "test"


def test_schema_registry_loads() -> None:
    store = get_schema_store()
    assert "https://birtha.local/schemas/control-plane/v1/task-packet.schema.json" in store


def test_validate_typed_artifact_envelope() -> None:
    now = "2026-04-07T12:00:00Z"
    raw = {
        "artifact_id": str(uuid4()),
        "artifact_type": "VERIFICATION_REPORT",
        "schema_version": "1.0.0",
        "status": "ACTIVE",
        "validation_state": "VALID",
        "producer": {"component": "verification_node", "executor": "deterministic_validator"},
        "input_artifact_refs": [],
        "supersedes": [],
        "payload": {"summary": "ok"},
        "created_at": now,
        "updated_at": now,
    }
    validate_typed_artifact_json(raw)


def test_append_cost_ledger_and_run_event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cost ledger persists on dossier and run via append_run_event / append_cost_ledger."""
    from src.devplane.models import (
        ProjectCreateRequest,
        RunEventRequest,
        TaskCreateRequest,
        TaskRunLaunchRequest,
    )
    from src.devplane.service import DevPlaneService

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# x\n", encoding="utf-8")
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True, env=env)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"],
        cwd=repo,
        check=True,
        capture_output=True,
        env=env,
    )
    subprocess.run(
        ["git", "config", "user.name", "t"],
        cwd=repo,
        check=True,
        capture_output=True,
        env=env,
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, env=env)
    subprocess.run(["git", "commit", "-m", "i"], cwd=repo, check=True, capture_output=True, env=env)

    root = tmp_path / "devplane"
    root.mkdir()
    ctrl = tmp_path / "control"
    ctrl.mkdir()
    svc = DevPlaneService(
        db_path=tmp_path / "db.sqlite3",
        devplane_root=root,
        control_plane_root=ctrl,
        default_remote="origin",
    )
    monkeypatch.setattr(
        svc.planner,
        "build_questions",
        lambda *args, **kwargs: [],
    )
    pr = svc.register_project(
        ProjectCreateRequest(name="ledger", canonical_repo_path=str(repo)),
    )
    task = svc.submit_task(
        TaskCreateRequest(project_id=pr.project_id, user_intent="work"),
    )
    run = svc.launch_task(task.task_id, TaskRunLaunchRequest())
    svc.append_run_event(
        run.run_id,
        RunEventRequest(
            cost_ledger=[CostLedgerEntry(component="c1", tokens_in=1, tokens_out=2)],
        ),
    )
    assert len(svc.get_task(task.task_id).dossier.cost_ledger) == 1
    assert len(svc.get_run(run.run_id).cost_ledger) == 1

    svc.append_cost_ledger(
        task.task_id,
        entry=CostLedgerEntry(component="c2", tokens_in=5),
        run_id=run.run_id,
    )
    assert len(svc.get_task(task.task_id).dossier.cost_ledger) == 2

    typed_id = str(uuid4())
    svc.append_run_event(
        run.run_id,
        RunEventRequest(
            artifacts=[
                ArtifactRecord(
                    artifact_id=typed_id,
                    artifact_type="VERIFICATION_REPORT",
                    schema_version="1.0.0",
                    producer={"component": "test"},
                    payload={"outcome": "PASS"},
                ),
            ],
        ),
    )
    dossier = svc.get_task(task.task_id).dossier
    assert any(
        row.get("artifact_id") == typed_id for row in dossier.typed_artifacts
    )
