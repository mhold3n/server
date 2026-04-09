"""Tests for the runtime-linked engineering knowledge pool."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.control_plane.knowledge_pool import (
    load_knowledge_pool,
    load_minutes_inventory,
    resolve_stack,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE_ROOT = REPO_ROOT / "knowledge" / "coding-tools"
EXCLUDED_PATH = REPO_ROOT / "KNOWLEGE MINUTES EXCLUDED.md"


def _copy_knowledge_root(tmp_path: Path) -> Path:
    target = tmp_path / "coding-tools"
    shutil.copytree(KNOWLEDGE_ROOT, target)
    return target


def _read_json(path: Path) -> list[dict] | dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: list[dict] | dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _excluded_names_from_markdown(path: Path) -> set[str]:
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("| ---") or "reason excluded" in line:
            continue
        parts = [part.strip() for part in line.strip().split("|")]
        if len(parts) >= 3 and parts[1]:
            names.add(parts[1])
    return names


def test_seed_catalog_matches_minutes_inventory() -> None:
    catalog = load_knowledge_pool()
    inventory = load_minutes_inventory()
    implemented_slugs = {
        entry["slug"]
        for entry in inventory["entries"]
        if entry["implementation_status"] == "implemented"
    }
    assert {ref.split("/")[-1] for ref in catalog.knowledge_packs} == implemented_slugs
    assert {artifact.payload.role for artifact in catalog.role_context_bundles.values()} == {
        "general",
        "coder",
        "reviewer",
    }


def test_minutes_inventory_entries_have_runtime_or_exclusion_row() -> None:
    inventory = load_minutes_inventory()
    excluded_names = _excluded_names_from_markdown(EXCLUDED_PATH)
    inventory_excluded_names = {
        entry["name"]
        for entry in inventory["entries"]
        if entry["implementation_status"] == "excluded"
    }
    for entry in inventory["entries"]:
        if entry["implementation_status"] == "implemented":
            assert entry["knowledge_pack_ref"]
            assert entry["environment_refs"]
            assert entry["excluded_reason"] is None
            continue
        assert entry["excluded_reason"]
        assert entry["name"] in excluded_names
    assert excluded_names == inventory_excluded_names


def test_resolve_stack_is_deterministic() -> None:
    problem_spec = {
        "physics": ["combustion", "chemistry", "reactor network"],
        "task_class": "thermochemistry_screening",
    }
    project_constraints = {
        "languages": ["python", "c++"],
        "integration": "linked runtime",
    }
    first = resolve_stack(problem_spec, project_constraints)
    second = resolve_stack(problem_spec, project_constraints)
    assert first == second
    assert first[0].knowledge_pack_ref == "artifact://knowledge-pack/cantera"


def test_resolve_runtime_prefers_verified_environment() -> None:
    catalog = load_knowledge_pool()
    default_env = catalog.resolve_runtime("artifact://knowledge-pack/cantera")
    assert default_env.environment_spec_id == "eng_thermochem_uv"

    docker_env = catalog.resolve_runtime(
        "artifact://knowledge-pack/cantera",
        host_profile={
            "preferred_delivery_kinds": ["docker_image", "uv_venv"],
            "verified_only": False,
        },
    )
    assert docker_env.environment_spec_id == "eng_thermochem_docker"


def test_compile_role_context_preserves_sources_across_roles() -> None:
    catalog = load_knowledge_pool()
    candidate_refs = [
        "artifact://knowledge-pack/cantera",
        "artifact://knowledge-pack/coolprop",
    ]
    general = catalog.compile_role_context(
        role="general",
        candidate_refs=candidate_refs,
        task_class="thermochemistry_screening",
        project_constraints={"languages": ["python", "c++"]},
    )
    coder = catalog.compile_role_context(
        role="coder",
        candidate_refs=candidate_refs,
        task_class="thermochemistry_screening",
        project_constraints={"languages": ["python", "c++"]},
    )
    reviewer = catalog.compile_role_context(
        role="reviewer",
        candidate_refs=candidate_refs,
        task_class="thermochemistry_screening",
        project_constraints={"languages": ["python", "c++"]},
    )
    assert general.source_artifact_refs == coder.source_artifact_refs == reviewer.source_artifact_refs
    assert general.source_hashes == coder.source_hashes == reviewer.source_hashes
    assert general.included_sections != coder.included_sections
    assert reviewer.included_sections != general.included_sections
    assert "environment ref artifact://environment-spec/eng_thermochem_uv" in general.compiled_summary


def test_cross_link_validation_flags_missing_evidence(tmp_path: Path) -> None:
    root = _copy_knowledge_root(tmp_path)
    path = root / "evidence" / "evidence-bundles.json"
    payload = _read_json(path)
    assert isinstance(payload, list)
    payload = [item for item in payload if item["payload"]["tool_id"] != "cantera"]
    _write_json(path, payload)
    with pytest.raises(ValueError, match="missing ref artifact://evidence-bundle/cantera_runtime"):
        load_knowledge_pool(root=root)


def test_cross_link_validation_flags_adapter_version_drift(tmp_path: Path) -> None:
    root = _copy_knowledge_root(tmp_path)
    path = root / "adapters" / "execution-adapter-specs.json"
    payload = _read_json(path)
    assert isinstance(payload, list)
    for item in payload:
        if item["payload"]["tool_id"] == "cantera":
            item["payload"]["supported_library_version"] = "legacy-curated"
    _write_json(path, payload)
    with pytest.raises(ValueError, match="supports library version legacy-curated"):
        load_knowledge_pool(root=root)


def test_cross_link_validation_flags_missing_environment_ref(tmp_path: Path) -> None:
    root = _copy_knowledge_root(tmp_path)
    path = root / "substrate" / "knowledge-packs.json"
    payload = _read_json(path)
    assert isinstance(payload, list)
    for item in payload:
        if item["payload"]["tool_id"] == "cantera":
            item["payload"]["environment_refs"] = ["artifact://environment-spec/missing_env"]
    _write_json(path, payload)
    with pytest.raises(ValueError, match="missing ref artifact://environment-spec/missing_env"):
        load_knowledge_pool(root=root)


def test_cross_link_validation_flags_missing_healthcheck_ref(tmp_path: Path) -> None:
    root = _copy_knowledge_root(tmp_path)
    path = root / "adapters" / "execution-adapter-specs.json"
    payload = _read_json(path)
    assert isinstance(payload, list)
    for item in payload:
        if item["payload"]["tool_id"] == "cantera":
            item["payload"]["healthcheck_refs"] = ["artifact://verification-report/missing_runtime_report"]
    _write_json(path, payload)
    with pytest.raises(ValueError, match="missing ref artifact://verification-report/missing_runtime_report"):
        load_knowledge_pool(root=root)


def test_resolve_stack_excludes_tool_outside_declared_not_for_boundary() -> None:
    catalog = load_knowledge_pool()
    results = catalog.resolve_stack(
        problem_spec={"task": "full 3d cfd field solve", "physics": ["field solve"]},
        project_constraints={"languages": ["python"]},
    )
    assert "artifact://knowledge-pack/cantera" not in {item.knowledge_pack_ref for item in results}


def test_candidate_pack_set_flags_incompatible_integration_pairing() -> None:
    catalog = load_knowledge_pool()
    errors = catalog.validate_candidate_pack_set(
        [
            "artifact://knowledge-pack/cantera",
            "artifact://knowledge-pack/pyspice",
        ]
    )
    assert any("cantera" in error and "pyspice" in error for error in errors)


def test_adapter_input_validation_flags_unit_policy_violations(tmp_path: Path) -> None:
    root = _copy_knowledge_root(tmp_path)
    path = root / "adapters" / "execution-adapter-specs.json"
    payload = _read_json(path)
    assert isinstance(payload, list)
    for item in payload:
        if item["payload"]["tool_id"] == "cantera":
            item["payload"]["typed_inputs"] = [
                {"name": "temperature", "type": "number", "required": True, "unit": "K"},
            ]
    _write_json(path, payload)
    catalog = load_knowledge_pool(root=root)
    errors = catalog.validate_adapter_inputs(
        "artifact://execution-adapter-spec/cantera_probe",
        {
            "temperature": 1200.0,
        },
    )
    assert "Unit-policy violation for input: temperature" in errors


def test_stale_decision_logs_are_rejected(tmp_path: Path) -> None:
    root = _copy_knowledge_root(tmp_path)
    path = root / "substrate" / "decision-logs.json"
    payload = _read_json(path)
    assert isinstance(payload, list)
    for item in payload:
        if item["payload"]["decision_id"] == "thermochem_cantera_coolprop_tespy_split":
            item["payload"]["status"] = "superseded"
    _write_json(path, payload)
    with pytest.raises(ValueError, match="references stale decision log"):
        load_knowledge_pool(root=root)


def test_conflicting_decision_logs_can_be_detected(tmp_path: Path) -> None:
    root = _copy_knowledge_root(tmp_path)
    path = root / "substrate" / "decision-logs.json"
    payload = _read_json(path)
    assert isinstance(payload, list)
    payload.append(
        {
            "artifact_id": "00000000-0000-4000-8000-00000000c001",
            "artifact_type": "DECISION_LOG",
            "created_at": "2026-04-08T00:00:00Z",
            "input_artifact_refs": ["artifact://knowledge-pack/cantera", "artifact://knowledge-pack/coolprop"],
            "payload": {
                "decision_id": "thermochem_cantera_coolprop_tespy_override",
                "schema_version": "1.0.0",
                "title": "Use Cantera, CoolProp, and TESPy for thermochemistry and system thermals",
                "statement": "Override the thermochemistry split with a contradictory accepted record.",
                "rationale": "Synthetic negative test",
                "chosen_refs": ["artifact://knowledge-pack/cantera"],
                "rejected_refs": ["artifact://knowledge-pack/coolprop"],
                "tradeoffs": ["Synthetic conflict"],
                "status": "accepted",
            },
            "producer": {"component": "test", "executor": "pytest"},
            "schema_version": "1.0.0",
            "status": "ACTIVE",
            "supersedes": [],
            "updated_at": "2026-04-08T00:00:00Z",
            "validation_state": "VALID",
        }
    )
    _write_json(path, payload)
    catalog = load_knowledge_pool(root=root)
    errors = catalog.validate_decision_consistency()
    assert any("thermochem_cantera_coolprop_tespy_override" in error for error in errors)


def test_verify_runtime_returns_pass_report(monkeypatch: pytest.MonkeyPatch) -> None:
    catalog = load_knowledge_pool()

    def _fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=0, stdout="OK:runtime", stderr="")

    monkeypatch.setattr("src.control_plane.knowledge_pool.subprocess.run", _fake_run)
    report = catalog.verify_runtime("artifact://environment-spec/eng_structures_uv")
    assert report.outcome.value == "PASS"
    assert report.validated_artifact_refs == ["artifact://environment-spec/eng_structures_uv"]
