"""Tests for the runtime-linked engineering knowledge pool."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from domain_engineering import core as engineering_module
from response_control_framework.knowledge_pool import (
    load_knowledge_pool,
    load_minutes_inventory,
    lookup_knowledge_packs,
    resolve_stack,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE_ROOT = REPO_ROOT / "services" / "domain-engineering" / "src" / "domain_engineering" / "data" / "coding-tools"
EXCLUDED_PATH = REPO_ROOT / "KNOWLEGE MINUTES EXCLUDED.md"
ACQUISITION_DOSSIERS_JSON_PATH = (
    KNOWLEDGE_ROOT / "substrate" / "deferred-acquisition-dossiers.json"
)
PACKAGE_COMPLETION_LEDGER_PATH = (
    KNOWLEDGE_ROOT / "substrate" / "package-completion-ledger.json"
)
PACKAGE_PROMOTION_HISTORY_PATH = (
    KNOWLEDGE_ROOT / "substrate" / "package-promotion-history.json"
)


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
        if len(parts) >= 3 and parts[1] and parts[1].lower() != "name":
            names.add(parts[1])
    return names


def test_seed_catalog_matches_phase3_inventory_and_synthetic_packs() -> None:
    catalog = load_knowledge_pool()
    inventory = load_minutes_inventory()
    inventory_pack_refs = {
        entry["knowledge_pack_ref"]
        for entry in inventory["entries"]
        if entry["knowledge_pack_ref"]
    }
    assert inventory_pack_refs <= set(catalog.knowledge_packs)
    synthetic_pack_refs = set(catalog.knowledge_packs) - inventory_pack_refs
    assert synthetic_pack_refs == {
        "artifact://knowledge-pack/petsc_family",
        "artifact://knowledge-pack/trilinos_family",
        "artifact://knowledge-pack/sparse_direct_family",
        "artifact://knowledge-pack/coinhsl_family",
        "artifact://knowledge-pack/nlp_time_chem_family",
        "artifact://knowledge-pack/geometry_native_family",
    }
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
        assert entry["knowledge_pack_ref"]
        assert entry["phase2_link_status"] in {
            "recommendable",
            "detailed_linked_runtime_gated",
            "detailed_linked_parent_gated",
            "detailed_linked_manual",
        }
        assert entry["phase3_completion_status"] in {
            "promoted",
            "queued",
            "smoke_verified",
            "blocked_runtime",
            "blocked_smoke",
            "blocked_external",
        }
        assert entry["phase3_primary_runtime_ref"].startswith("artifact://environment-spec/")
        assert entry["phase3_smoke_case_ref"].startswith("package-smoke://")
        assert isinstance(entry["phase3_parent_completion_refs"], list)
        assert isinstance(entry["promotion_ready"], bool)
        if entry["implementation_status"] == "implemented":
            assert entry["environment_refs"]
            assert entry["excluded_reason"] is None
            assert entry["phase_state"] == "linked"
            assert entry["phase2_link_status"] == "recommendable"
            assert entry["alias_resolution_kind"] in {
                "self",
                "substituted_by_canonical_pack",
            }
            assert entry["phase3_completion_status"] == "promoted"
            assert entry["promotion_ready"] is True
            continue
        assert entry["excluded_reason"]
        assert entry["name"] in excluded_names
        assert entry["promotion_ready"] is False
    assert excluded_names == inventory_excluded_names


def test_excluded_inventory_entries_have_recovery_metadata() -> None:
    inventory = load_minutes_inventory()
    excluded_entries = [entry for entry in inventory["entries"] if entry["implementation_status"] == "excluded"]
    assert excluded_entries
    for entry in excluded_entries:
        assert entry["module_ref"] == f"minutes-module://{entry['slug']}"
        assert entry["knowledge_pack_ref"].startswith("artifact://knowledge-pack/")
        assert entry["install_method_category"].startswith("I")
        assert entry["kb_build_method_category"].startswith("K")
        assert entry["install_batch"].startswith("phase1_batch")
        assert entry["kb_build_batch"].startswith("phase2_batch")
        assert entry["phase2_link_status"] in {
            "recommendable",
            "detailed_linked_runtime_gated",
            "detailed_linked_parent_gated",
            "detailed_linked_manual",
        }
        assert entry["phase3_completion_status"] in {
            "queued",
            "smoke_verified",
            "blocked_runtime",
            "blocked_smoke",
            "blocked_external",
        }
        assert entry["alias_resolution_kind"] in {
            "self",
            "substituted_by_canonical_pack",
        }
        assert isinstance(entry["canonical_tool_name"], str)
        assert isinstance(entry["parent_runtime_refs"], list)
        assert isinstance(entry["blocked_by_refs"], list)
        assert isinstance(entry["manual_acquisition_required"], bool)
        assert isinstance(entry["cli_install_channel"], str)
        assert entry["cli_phase1_status"] in {
            "ready",
            "installed",
            "blocked_by_parent_runtime",
            "knowledge_only",
            "manual_acquisition_required",
        }
        assert entry["user_intervention_class"] in {
            "not_required",
            "website_download",
            "proprietary_license",
            "proprietary_runtime",
        }
        assert entry["phase_state"] in {
            "planned",
            "installing",
            "installed",
            "kb_linking",
            "linked",
            "deferred",
        }
        assert entry["promotion_ready"] is False
        if entry["install_method_category"] == "I6_deferred_external_manual":
            assert entry["manual_acquisition_required"] is True
            assert entry["phase_target"] == "next_sprint"
            assert entry["phase_state"] == "deferred"
            assert entry["phase2_link_status"] == "detailed_linked_manual"
            assert entry["phase3_completion_status"] == "blocked_external"
        else:
            assert entry["phase_target"] in {"phase1", "phase3b"}


def test_recovery_plan_metadata_covers_all_install_and_kb_categories() -> None:
    inventory = load_minutes_inventory()
    recovery_plan = inventory["recovery_plan"]
    install_categories = {item["id"] for item in recovery_plan["install_method_categories"]}
    kb_categories = {item["id"] for item in recovery_plan["kb_build_method_categories"]}
    excluded_entries = [entry for entry in inventory["entries"] if entry["implementation_status"] == "excluded"]
    assert {entry["install_method_category"] for entry in excluded_entries} <= install_categories
    assert {entry["kb_build_method_category"] for entry in excluded_entries} <= kb_categories


def test_host_companion_dependency_metadata_matches_plan() -> None:
    inventory = load_minutes_inventory()
    by_slug = {entry["slug"]: entry for entry in inventory["entries"]}
    assert by_slug["petsc4py"]["blocked_by_refs"] == ["minutes-module://petsc"]
    assert by_slug["petsc_ksp"]["blocked_by_refs"] == ["minutes-module://petsc"]
    assert by_slug["trilinos_belos"]["blocked_by_refs"] == ["minutes-module://trilinos"]
    assert by_slug["ompython"]["blocked_by_refs"] == ["minutes-module://openmodelica"]
    assert by_slug["medcoupling"]["blocked_by_refs"] == ["minutes-module://salome"]


def test_cli_phase1_metadata_distinguishes_ready_and_manual_modules() -> None:
    inventory = load_minutes_inventory()
    by_slug = {entry["slug"]: entry for entry in inventory["entries"]}
    assert by_slug["picogk_shapekernel"]["install_method_category"] == "I2_containerized_native_backend_family"
    assert by_slug["picogk_shapekernel"]["cli_install_channel"] == "dotnet_nuget"
    assert by_slug["picogk_shapekernel"]["manual_acquisition_required"] is False
    assert by_slug["picogk_shapekernel"]["phase_target"] == "completed"
    assert by_slug["picogk_shapekernel"]["phase_state"] == "linked"
    assert by_slug["picogk_shapekernel"]["phase2_link_status"] == "recommendable"
    assert by_slug["picogk_shapekernel"]["phase3_completion_status"] == "promoted"
    assert by_slug["picogk_shapekernel"]["promotion_ready"] is True
    assert by_slug["picogk_shapekernel"]["environment_refs"] == ["artifact://environment-spec/eng_dotnet_sdk"]
    assert by_slug["compas"]["phase_state"] == "linked"
    assert by_slug["compas"]["acquisition_status"] == "verified_in_knowledge_runtime"
    assert by_slug["compas"]["phase2_link_status"] == "recommendable"
    assert by_slug["compas"]["phase3_completion_status"] == "promoted"
    assert "artifact://environment-spec/eng_geometry_uv" in by_slug["compas"]["environment_refs"]
    assert by_slug["rhino_common"]["phase_state"] == "linked"
    assert by_slug["rhino_common"]["cli_install_channel"] == "host_app_cli"
    assert by_slug["rhino_common"]["phase2_link_status"] == "recommendable"
    assert by_slug["rhino_common"]["phase3_completion_status"] == "promoted"
    assert by_slug["rhino_common"]["environment_refs"] == ["artifact://environment-spec/eng_rhino_host"]
    assert by_slug["ipopt"]["environment_refs"] == ["artifact://environment-spec/eng_ipopt_onemkl_docker"]
    assert by_slug["ipopt"]["phase2_link_status"] == "recommendable"
    assert by_slug["ipopt"]["phase3_completion_status"] == "promoted"
    assert by_slug["ipopt"]["phase_target"] == "completed"
    assert by_slug["ipopt"]["phase_state"] == "linked"
    assert by_slug["pardiso"]["manual_acquisition_required"] is False
    assert by_slug["pardiso"]["cli_install_channel"] == "docker_build_with_onemkl"
    assert by_slug["pardiso"]["phase2_link_status"] == "recommendable"
    assert by_slug["pardiso"]["phase3_completion_status"] == "promoted"
    assert by_slug["pardiso"]["knowledge_pack_ref"] == "artifact://knowledge-pack/onemkl"
    assert by_slug["pardiso"]["alias_resolution_kind"] == "substituted_by_canonical_pack"
    assert by_slug["ompython"]["phase_state"] == "linked"
    assert by_slug["ompython"]["acquisition_status"] == "verified_in_knowledge_runtime"
    assert by_slug["ompython"]["phase2_link_status"] == "recommendable"
    assert by_slug["ompython"]["phase3_completion_status"] == "promoted"
    assert by_slug["porepy"]["phase3_completion_status"] == "promoted"
    assert by_slug["porepy"]["phase2_link_status"] == "recommendable"
    assert by_slug["femm"]["user_intervention_class"] == "website_download"
    assert by_slug["femm"]["cli_install_channel"] == "wine_installer_after_download"
    assert by_slug["femm"]["phase2_link_status"] == "detailed_linked_manual"
    assert by_slug["femm"]["phase3_completion_status"] == "blocked_external"


def test_excluded_markdown_is_grouped_by_install_and_kb_method() -> None:
    content = EXCLUDED_PATH.read_text(encoding="utf-8")
    assert "## Remaining User Intervention Required" in content
    assert "## By Install Method" in content
    assert "## By Knowledge Build Method" in content
    assert "### I6 deferred_external_manual -> K6 acquisition_deferred_pack" in content
    assert "### K6 acquisition_deferred_pack" in content
    assert "### I1 containerized_native_solver_platform -> K1 executable_solver_platform_pack" not in content
    assert "| PicoGK / ShapeKernel |" not in content
    assert "| PARDISO |" not in content
    assert "| RhinoCommon |" not in content
    assert "| FEMM |" in content


def test_deferred_acquisition_dossiers_cover_manual_modules() -> None:
    payload = _read_json(ACQUISITION_DOSSIERS_JSON_PATH)
    assert isinstance(payload, dict)
    entries = payload["entries"]
    assert len(entries) == 3
    assert {entry["slug"] for entry in entries} == {
        "femm",
        "pyleecan",
        "ma87",
    }


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


def test_phase2_alias_rows_resolve_to_canonical_pack() -> None:
    inventory = load_minutes_inventory()
    by_slug = {entry["slug"]: entry for entry in inventory["entries"]}
    pardiso = by_slug["pardiso"]
    assert pardiso["knowledge_pack_ref"] == "artifact://knowledge-pack/onemkl"
    assert pardiso["alias_resolution_kind"] == "substituted_by_canonical_pack"
    assert pardiso["canonical_tool_name"] == "Intel oneMKL"
    assert pardiso["phase3_parent_completion_refs"] == []


def test_lookup_knowledge_packs_supports_aliases_but_keeps_runtime_gates() -> None:
    hits = lookup_knowledge_packs("pardiso")
    assert hits
    first = hits[0]
    assert first.knowledge_pack_ref == "artifact://knowledge-pack/onemkl"
    assert first.runtime_gated is False
    assert first.matched_terms == ("pardiso",)


def test_top_level_compiled_context_summaries_exclude_runtime_gated_phase2_packs() -> None:
    payload = _read_json(KNOWLEDGE_ROOT / "compiled" / "general-context.json")
    assert isinstance(payload, dict)
    summary = payload["payload"]["compiled_summary"]
    assert "RhinoCommon" in summary
    assert "CGNS" in summary
    assert "Intel oneMKL" in summary
    assert "Geometry Native Family" not in summary
    assert "CGAL" in summary
    assert "OpenCAMLib" in summary


def test_phase2_compiled_contexts_include_aliases_and_runtime_gates() -> None:
    payload = _read_json(
        KNOWLEDGE_ROOT / "compiled" / "phase2" / "install_phase1_batch1f_onemkl_family_general.json"
    )
    assert isinstance(payload, dict)
    summary = payload["payload"]["compiled_summary"]
    assert "Intel oneMKL" in summary
    assert "Aliases: PARDISO." in summary
    assert "Runtime eng-ipopt-onemkl/docker_image" in summary
    assert "verification refs artifact://verification-report/" in summary


def test_phase2_generated_batch_context_files_exist() -> None:
    phase2_root = KNOWLEDGE_ROOT / "compiled" / "phase2"
    assert (phase2_root / "family_k2_backend_families_general.json").exists()
    assert (phase2_root / "install_phase1_batch1f_onemkl_family_general.json").exists()
    assert (phase2_root / "kb_phase2_batch_k6_deferred_acquisition_reviewer.json").exists()


def test_phase3_completion_ledger_covers_every_recovery_module() -> None:
    payload = _read_json(PACKAGE_COMPLETION_LEDGER_PATH)
    assert isinstance(payload, dict)
    entries = payload["entries"]
    assert len(entries) == 76
    assert {entry["module_slug"] for entry in entries} == {
        entry["slug"]
        for entry in load_minutes_inventory()["entries"]
        if entry["slug"] in {
            "openfoam",
            "calculix",
            "code_saturne",
            "su2",
            "code_aster",
            "openwam",
            "opensmokepp",
            "openmodelica",
            "kratos_multiphysics",
            "moose",
            "fenicsx",
            "dealii",
            "hermes",
            "dakota",
            "project_chrono",
            "mbdyn",
            "salome",
            "paraview",
            "petsc",
            "petsc_ksp",
            "petsc_gamg",
            "slepc",
            "hypre",
            "primme",
            "trilinos",
            "trilinos_belos",
            "trilinos_ifpack2",
            "trilinos_muelu",
            "mumps",
            "superlu",
            "superlu_dist",
            "suitesparse",
            "cholmod",
            "umfpack",
            "klu",
            "strumpack",
            "ipopt",
            "sundials",
            "tchem",
            "ma57",
            "ma77",
            "ma86",
            "ma87",
            "ma97",
            "cgal",
            "opencamlib",
            "pardiso",
            "picogk_shapekernel",
            "dymos",
            "mphys",
            "idaes",
            "optas",
            "simpy",
            "compas",
            "simpeg",
            "pyphs",
            "openpnm",
            "porepy",
            "rmg_py",
            "ray",
            "botorch",
            "nevergrad",
            "petsc4py",
            "pyoptsparse",
            "precice",
            "ompython",
            "pyfmi",
            "medcoupling",
            "vtk",
            "rhino_common",
            "cgns",
            "exodus_ii",
            "fmi_fmus",
            "modelica_standard_library",
            "femm",
            "pyleecan",
        }
    }
    by_slug = {entry["module_slug"]: entry for entry in entries}
    assert by_slug["compas"]["status"] == "promoted"
    assert by_slug["ompython"]["status"] == "promoted"
    assert by_slug["ipopt"]["status"] == "promoted"
    assert by_slug["porepy"]["status"] == "promoted"
    assert by_slug["pyphs"]["status"] == "promoted"
    assert by_slug["femm"]["status"] == "blocked_external"
    assert by_slug["pardiso"]["completion_kind"] == "alias"
    assert by_slug["pyoptsparse"]["parent_package_refs"] == ["artifact://knowledge-pack/ipopt"]
    assert by_slug["openmodelica"]["child_package_refs"] == sorted(
        [
            "artifact://knowledge-pack/modelica_standard_library",
            "artifact://knowledge-pack/ompython",
            "artifact://knowledge-pack/pyfmi",
        ]
    )
    assert by_slug["compas"]["smoke_command"].startswith(
        "python scripts/run_knowledge_package_smoke.py --module-slug compas"
    )
    assert by_slug["strumpack"]["status"] == "promoted"
    assert by_slug["strumpack"]["last_failure_stage"] is None
    assert by_slug["tchem"]["status"] == "promoted"
    assert by_slug["tchem"]["last_failure_stage"] is None
    assert by_slug["rmg_py"]["status"] == "promoted"
    assert by_slug["rmg_py"]["last_failure_stage"] is None
    assert by_slug["ipopt"]["last_attempted_at"]
    assert by_slug["ipopt"]["last_log_path"]


def test_phase3_promotion_history_tracks_closed_recovery_rows() -> None:
    payload = _read_json(PACKAGE_PROMOTION_HISTORY_PATH)
    assert isinstance(payload, dict)
    entries = payload["entries"]
    promoted_slugs = {
        entry["module_slug"]
        for entry in _read_json(PACKAGE_COMPLETION_LEDGER_PATH)["entries"]
        if entry["status"] == "promoted"
    }
    assert len(entries) == len(promoted_slugs)
    assert {entry["module_slug"] for entry in entries} == promoted_slugs


def test_top_level_compiled_context_pack_refs_match_promoted_inventory() -> None:
    inventory = load_minutes_inventory()
    promoted_pack_refs = {
        entry["knowledge_pack_ref"]
        for entry in inventory["entries"]
        if entry["promotion_ready"]
    }
    payload = _read_json(KNOWLEDGE_ROOT / "compiled" / "general-context.json")
    assert isinstance(payload, dict)
    compiled_pack_refs = {
        ref
        for ref in payload["payload"]["source_artifact_refs"]
        if ref.startswith("artifact://knowledge-pack/")
    }
    assert compiled_pack_refs == promoted_pack_refs


def test_phase3_generated_context_files_exist() -> None:
    phase3_root = KNOWLEDGE_ROOT / "compiled" / "phase3"
    assert (phase3_root / "package_pardiso_general.json").exists()
    assert (phase3_root / "package_femm_reviewer.json").exists()
    assert (phase3_root / "parent_ipopt_general.json").exists()
    assert (phase3_root / "parent_openmodelica_coder.json").exists()


def test_phase3_package_contexts_include_gate_reasons() -> None:
    payload = _read_json(KNOWLEDGE_ROOT / "compiled" / "phase3" / "package_pardiso_general.json")
    assert isinstance(payload, dict)
    summary = payload["payload"]["compiled_summary"]
    assert "Intel oneMKL" in summary
    assert "Aliases: PARDISO." in summary
    assert "Runtime gate:" in summary


def test_phase3_parent_contexts_include_parent_and_child_packages() -> None:
    payload = _read_json(KNOWLEDGE_ROOT / "compiled" / "phase3" / "parent_ipopt_general.json")
    assert isinstance(payload, dict)
    summary = payload["payload"]["compiled_summary"]
    assert "IPOPT" in summary
    assert "pyOptSparse" in summary


def test_phase2_linked_packs_meet_detail_requirements() -> None:
    catalog = load_knowledge_pool()
    inventory = load_minutes_inventory()
    checked_pack_refs: set[str] = set()
    for entry in inventory["entries"]:
        if entry["implementation_status"] != "excluded":
            continue
        pack_ref = entry["knowledge_pack_ref"]
        if pack_ref in checked_pack_refs:
            continue
        checked_pack_refs.add(pack_ref)
        pack = catalog.knowledge_packs[pack_ref].payload
        recipe = catalog.recipe_objects[pack.recipe_refs[0]].payload
        evidence = catalog.evidence_bundles[pack.evidence_refs[0]].payload
        assert len(pack.core_objects) >= 3
        assert len(pack.anti_patterns) >= 2
        assert len(recipe.touched_objects) >= 3
        assert len(recipe.acceptance_tests) >= 3
        assert len(evidence.reviewer_checklist) >= 3


def test_engineering_knowledge_catalog_cache_invalidates_on_file_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _copy_knowledge_root(tmp_path)
    engineering_module.reset_engineering_sessions_for_tests()
    monkeypatch.setattr(engineering_module, "_knowledge_pool_root", lambda: root)
    first = engineering_module._knowledge_catalog()
    second = engineering_module._knowledge_catalog()
    assert first is second

    path = root / "compiled" / "general-context.json"
    payload = _read_json(path)
    assert isinstance(payload, dict)
    payload["payload"]["compiled_summary"] += "\ncache invalidation marker"
    _write_json(path, payload)

    third = engineering_module._knowledge_catalog()
    assert third is not first


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

    monkeypatch.setattr("response_control_framework.knowledge_pool.subprocess.run", _fake_run)
    report = catalog.verify_runtime("artifact://environment-spec/eng_structures_uv")
    assert report.outcome.value == "PASS"
    assert report.validated_artifact_refs == ["artifact://environment-spec/eng_structures_uv"]


def test_docker_environments_have_default_container_gui_sessions() -> None:
    catalog = load_knowledge_pool()
    docker_envs = [
        (ref, artifact.payload)
        for ref, artifact in catalog.environment_specs.items()
        if artifact.payload.delivery_kind == "docker_image"
        and not artifact.payload.environment_spec_id.endswith("_gui")
    ]
    assert docker_envs
    for env_ref, env in docker_envs:
        assert env.gui_capability_state in {
            "PLANNED_CONTAINER_GUI",
            "VERIFIED_CONTAINER_GUI",
            "BLOCKED_CONTAINER_GUI",
        }
        assert env.default_gui_session_ref
        assert env.default_gui_session_ref in env.gui_session_refs
        gui = catalog.gui_session_specs[env.default_gui_session_ref].payload
        assert gui.base_environment_ref == env_ref
        assert gui.display_protocol == "novnc_web"
        assert gui.control_provider == "openclaw_browser"
        assert gui.security_policy.bind_host == "127.0.0.1"
        assert gui.security_policy.allow_host_desktop is False


def test_resolve_gui_session_allows_planned_sessions_when_requested() -> None:
    catalog = load_knowledge_pool()
    gui = catalog.resolve_gui_session(
        "artifact://environment-spec/eng_paraview_docker",
        {"verified_only": False},
    )
    assert gui.gui_session_spec_id == "eng_paraview_gui"
    assert gui.openclaw_entry_url.startswith("http://127.0.0.1:{novnc_port}/")
    if not catalog._gui_session_has_passing_verification(
        "artifact://gui-session-spec/eng_paraview_gui"
    ):
        with pytest.raises(ValueError, match="No GUI session matched"):
            catalog.resolve_gui_session("artifact://environment-spec/eng_paraview_docker")


def test_verify_gui_session_returns_pass_report(monkeypatch: pytest.MonkeyPatch) -> None:
    catalog = load_knowledge_pool()

    def _fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=0, stdout="OK:gui", stderr="")

    monkeypatch.setattr("response_control_framework.knowledge_pool.subprocess.run", _fake_run)
    report = catalog.verify_gui_session("artifact://gui-session-spec/eng_paraview_gui")
    assert report.outcome.value == "PASS"
    assert report.validated_artifact_refs == [
        "artifact://gui-session-spec/eng_paraview_gui",
        "artifact://environment-spec/eng_paraview_gui",
    ]
