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
from src.control_plane.engineering import (
    build_task_queue,
    derive_engineering_state,
    intake_engineering_request,
    reset_engineering_sessions_for_tests,
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


def _load_fixture(relative_path: str) -> dict:
    root = Path(__file__).resolve().parents[3]
    path = root / relative_path
    return json.loads(path.read_text(encoding="utf-8"))


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
    data = _load_fixture(
        "schemas/control-plane/v1/fixtures/task-packet/valid-minimal.json"
    )
    validate_task_packet_json(data)


def test_golden_problem_brief_round_trip() -> None:
    data = _load_fixture(
        "schemas/control-plane/v1/fixtures/problem-brief/valid-minimal.json"
    )
    pb = validate_problem_brief_json(data)
    assert pb.problem_statement.need
    assert pb.design_space.responses[0].variable_id


def test_golden_task_queue_round_trip() -> None:
    data = _load_fixture(
        "schemas/control-plane/v1/fixtures/task-queue/valid-minimal.json"
    )
    validate_task_queue_json(data)


def test_golden_engineering_state_round_trip() -> None:
    data = _load_fixture(
        "schemas/control-plane/v1/fixtures/engineering-state/valid-minimal.json"
    )
    state = validate_engineering_state_json(data)
    assert state.ready_for_task_decomposition is True


def test_golden_routing_policy_round_trip() -> None:
    data = _load_fixture(
        "schemas/control-plane/v1/fixtures/routing-policy/valid-minimal.json"
    )
    validate_routing_policy_json(data)


def test_cost_ledger_entry_model() -> None:
    e = CostLedgerEntry(component="test", tokens_in=1, tokens_out=2)
    assert e.component == "test"


def test_schema_registry_loads() -> None:
    store = get_schema_store()
    assert "https://birtha.local/schemas/control-plane/v1/task-packet.schema.json" in store


def test_problem_brief_rejects_missing_engineering_fields() -> None:
    data = _load_fixture(
        "schemas/control-plane/v1/fixtures/problem-brief/valid-minimal.json"
    )
    del data["success_criteria"]
    with pytest.raises(ContractValidationError):
        validate_problem_brief_json(data)


def test_engineering_state_derivation_is_idempotent_and_permutation_invariant() -> None:
    data = _load_fixture(
        "schemas/control-plane/v1/fixtures/problem-brief/valid-minimal.json"
    )
    pb = validate_problem_brief_json(data)
    derived_a = derive_engineering_state(pb).model_dump(mode="json")
    derived_b = derive_engineering_state(pb).model_dump(mode="json")
    for payload in (derived_a, derived_b):
        payload.pop("engineering_state_id", None)
        payload.pop("updated_at", None)
    assert derived_a == derived_b

    permuted = _load_fixture(
        "schemas/control-plane/v1/fixtures/problem-brief/valid-minimal.json"
    )
    permuted["constraints"] = list(reversed(permuted["constraints"]))
    permuted["inputs"] = list(reversed(permuted["inputs"]))
    permuted["deliverables"] = list(reversed(permuted["deliverables"]))
    state_a = derive_engineering_state(validate_problem_brief_json(data)).model_dump(mode="json")
    state_b = derive_engineering_state(validate_problem_brief_json(permuted)).model_dump(mode="json")
    assert sorted(item["id"] for item in state_a["constraints"]) == sorted(
        item["id"] for item in state_b["constraints"]
    )
    assert sorted(item["issue_id"] for item in state_a["open_issues"]) == sorted(
        item["issue_id"] for item in state_b["open_issues"]
    )
    assert sorted(item["criterion_id"] for item in state_a["verification_intent"]) == sorted(
        item["criterion_id"] for item in state_b["verification_intent"]
    )


def test_task_queue_generation_requires_ready_engineering_state() -> None:
    problem_brief = validate_problem_brief_json(
        _load_fixture("schemas/control-plane/v1/fixtures/problem-brief/valid-minimal.json")
    )
    state = derive_engineering_state(problem_brief).model_copy(
        update={"ready_for_task_decomposition": False}
    )
    with pytest.raises(ValueError):
        build_task_queue(problem_brief=problem_brief, engineering_state=state)


def test_control_plane_engineering_intake_route_requires_clarification(
    test_client: TestClient,
) -> None:
    reset_engineering_sessions_for_tests()
    response = test_client.post(
        "/api/control-plane/engineering/intake",
        json={"user_input": "Help with the repo"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "CLARIFICATION_REQUIRED"
    assert body["clarification_questions"]


def test_control_plane_engineering_intake_route_builds_governing_artifacts(
    test_client: TestClient,
) -> None:
    reset_engineering_sessions_for_tests()
    response = test_client.post(
        "/api/control-plane/engineering/intake",
        json={
            "user_input": "Implement a governed repository change",
            "task_plan": {
                "project_id": "proj_x",
                "objective": "Implement a governed repository change",
                "constraints": ["Only touch the isolated workspace"],
                "acceptance_criteria": ["Verification commands pass"],
                "implementation_outline": ["Update the targeted files"],
                "verification_plan": ["pytest -q"],
                "delegation_hints": [],
                "work_items": [],
                "verification_blocks": [],
                "planned_branch": "birtha/example"
            },
            "project_context": {
                "project_id": "proj_x",
                "project_name": "Example Repo"
            }
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "READY"
    assert body["problem_brief_valid"] is True
    assert body["ready_for_task_decomposition"] is True
    assert body["task_queue"]
    assert body["task_packets"]


def test_control_plane_build_task_queue_route_blocks_when_state_not_ready(
    test_client: TestClient,
) -> None:
    problem_brief = validate_problem_brief_json(
        _load_fixture("schemas/control-plane/v1/fixtures/problem-brief/valid-minimal.json")
    )
    engineering_state = derive_engineering_state(problem_brief).model_dump(mode="json")
    engineering_state["ready_for_task_decomposition"] = False
    response = test_client.post(
        "/api/control-plane/engineering/build-task-queue",
        json={
            "problem_brief": problem_brief.model_dump(mode="json", exclude_none=True),
            "engineering_state": engineering_state,
        },
    )
    assert response.status_code == 409


def test_control_plane_build_escalation_route_returns_typed_packet(
    test_client: TestClient,
) -> None:
    engineering_state = derive_engineering_state(
        validate_problem_brief_json(
            _load_fixture("schemas/control-plane/v1/fixtures/problem-brief/valid-minimal.json")
        )
    ).model_dump(mode="json")
    response = test_client.post(
        "/api/control-plane/engineering/build-escalation",
        json={
            "engineering_state": engineering_state,
            "problem_brief_ref": engineering_state["problem_brief_ref"],
            "verification_report": {
                "verification_report_id": str(uuid4()),
                "schema_version": "1.0.0",
                "outcome": "ESCALATE",
                "blocking_findings": [
                    {
                        "code": "ENGINEERING_GATE_BLOCKED",
                        "severity": "high",
                        "artifact_ref": engineering_state["problem_brief_ref"],
                    }
                ],
                "validated_artifact_refs": [engineering_state["problem_brief_ref"]],
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["escalation_packet"]["reason"] in {"AMBIGUITY", "CONFLICT", "HIGH_IMPACT_REVIEW"}


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
