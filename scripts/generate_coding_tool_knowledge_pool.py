#!/usr/bin/env python3
"""Generate the runtime-linked engineering knowledge pool artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = REPO_ROOT / "knowledge" / "coding-tools"
RUNTIME_ROOT = OUTPUT_ROOT / "runtime"
GUI_ROOT = OUTPUT_ROOT / "gui"
EXCLUDED_PATH = REPO_ROOT / "KNOWLEGE MINUTES EXCLUDED.md"
ACQUISITION_DOSSIERS_JSON_PATH = OUTPUT_ROOT / "substrate" / "deferred-acquisition-dossiers.json"
ACQUISITION_DOSSIERS_MD_PATH = OUTPUT_ROOT / "DEFERRED_ACQUISITION_DOSSIERS.md"
PACKAGE_COMPLETION_LEDGER_PATH = OUTPUT_ROOT / "substrate" / "package-completion-ledger.json"
PACKAGE_PROMOTION_HISTORY_PATH = OUTPUT_ROOT / "substrate" / "package-promotion-history.json"
SEED_TS = "2026-04-08T00:00:00Z"
PRODUCER = {"component": "knowledge_pool.seed", "executor": "curation_seed_builder"}


def implemented(
    *,
    slug: str,
    name: str,
    category: str,
    module_class: str,
    bindings: list[str],
    solves: list[str],
    best_for: list[str],
    not_for: list[str],
    source_refs: list[str],
    runtime_profile: str,
    import_target: str,
    related: list[str] | None = None,
) -> dict:
    return {
        "slug": slug,
        "name": name,
        "category": category,
        "module_class": module_class,
        "bindings": bindings,
        "solves": solves,
        "best_for": best_for,
        "not_for": not_for,
        "source_refs": source_refs,
        "runtime_profile": runtime_profile,
        "import_target": import_target,
        "related": related or [],
        "implementation_status": "implemented",
    }


def excluded(
    *,
    slug: str,
    name: str,
    category: str,
    module_class: str,
    source_refs: list[str],
    reason: str,
    executable: bool = True,
) -> dict:
    return {
        "slug": slug,
        "name": name,
        "category": category,
        "module_class": module_class,
        "source_refs": source_refs,
        "implementation_status": "excluded",
        "excluded_reason": reason,
        "executable": executable,
    }


def minutes_module_ref(slug: str) -> str:
    return f"minutes-module://{slug}"


INSTALL_METHOD_CATEGORIES: dict[str, dict[str, str]] = {
    "I1_containerized_native_solver_platform": {
        "title": "I1 containerized_native_solver_platform",
        "kb_build_method_category": "K1_executable_solver_platform_pack",
        "description": "Containerized native solver and platform applications with executable runtime surfaces.",
    },
    "I2_containerized_native_backend_family": {
        "title": "I2 containerized_native_backend_family",
        "kb_build_method_category": "K2_backend_family_pack",
        "description": "Containerized native backend families and kernel libraries that should be built once and reused by dependents.",
    },
    "I3_python_first_venv_package": {
        "title": "I3 python_first_venv_package",
        "kb_build_method_category": "K3_python_framework_pack",
        "description": "Python-first packages installed into shared uv environments by compatible family.",
    },
    "I4_host_companion_wrapper": {
        "title": "I4 host_companion_wrapper",
        "kb_build_method_category": "K4_companion_host_bound_pack",
        "description": "Host-bound wrappers and companions that inherit their installation path from a verified parent runtime.",
    },
    "I5_knowledge_only_standard": {
        "title": "I5 knowledge_only_standard",
        "kb_build_method_category": "K5_standard_spec_pack",
        "description": "Standards and exchange formats modeled as knowledge artifacts with validators and mappings, not installs.",
    },
    "I6_deferred_external_manual": {
        "title": "I6 deferred_external_manual",
        "kb_build_method_category": "K6_acquisition_deferred_pack",
        "description": "Modules blocked on user-supplied source, licenses, proprietary runtimes, or interactive/manual acquisition.",
    },
}

KB_BUILD_METHOD_CATEGORIES: dict[str, dict[str, str]] = {
    "K1_executable_solver_platform_pack": {
        "title": "K1 executable_solver_platform_pack",
        "description": "Executable application and solver platform packs with runtime-linked recipes, adapters, and evidence.",
    },
    "K2_backend_family_pack": {
        "title": "K2 backend_family_pack",
        "description": "Backend family packs with shared runtime evidence and child overlays for tightly related kernels.",
    },
    "K3_python_framework_pack": {
        "title": "K3 python_framework_pack",
        "description": "API-centric Python package packs with import probes, minimal recipes, and framework-specific failure signatures.",
    },
    "K4_companion_host_bound_pack": {
        "title": "K4 companion_host_bound_pack",
        "description": "Companion packs that must link to a verified parent runtime and compatibility evidence.",
    },
    "K5_standard_spec_pack": {
        "title": "K5 standard_spec_pack",
        "description": "Knowledge-only standard packs with validators, schema maps, examples, and host/runtime mappings.",
    },
    "K6_acquisition_deferred_pack": {
        "title": "K6 acquisition_deferred_pack",
        "description": "Placeholder packs for externally acquired modules, recording capability, constraints, and acquisition prerequisites.",
    },
}

RECOVERY_DEFAULTS = {
    "phase1_priority": "foundations_first",
    "standards_policy": "knowledge_only_artifacts",
    "manual_install_policy": "defer_only_proprietary_or_website_email_delivered_installs",
    "phase1_cli_policy": "promote_all_non_proprietary_cli_installables_into_phase1_batches",
    "pyfmi_default_host": minutes_module_ref("openmodelica"),
    "pyoptsparse_default_backend": minutes_module_ref("ipopt"),
    "precice_default_solver_pair": [minutes_module_ref("openfoam"), minutes_module_ref("calculix")],
    "vtk_default_host": minutes_module_ref("paraview"),
}

INSTALL_BATCH_DEFINITIONS = [
    {
        "id": "phase1_batch1a_petsc_family",
        "phase": "phase1",
        "order": 1,
        "install_method_category": "I2_containerized_native_backend_family",
        "title": "Batch 1A: PETSc family",
        "description": "Build the PETSc-centered backend family first so dependent wrappers and eigensolvers inherit one native base.",
    },
    {
        "id": "phase1_batch1b_trilinos_family",
        "phase": "phase1",
        "order": 2,
        "install_method_category": "I2_containerized_native_backend_family",
        "title": "Batch 1B: Trilinos family",
        "description": "Build the Trilinos family after PETSc to cover the second major backend lineage.",
    },
    {
        "id": "phase1_batch1c_sparse_direct_family",
        "phase": "phase1",
        "order": 3,
        "install_method_category": "I2_containerized_native_backend_family",
        "title": "Batch 1C: Sparse-direct family",
        "description": "Build sparse direct and factorization backends that later solver platforms can reuse.",
    },
    {
        "id": "phase1_batch1d_nlp_time_chem_family",
        "phase": "phase1",
        "order": 4,
        "install_method_category": "I2_containerized_native_backend_family",
        "title": "Batch 1D: IPOPT/SUNDIALS/TChem family",
        "description": "Build the nonlinear optimization, time integration, and chemistry-kernel family.",
    },
    {
        "id": "phase1_batch1e_geometry_native_family",
        "phase": "phase1",
        "order": 5,
        "install_method_category": "I2_containerized_native_backend_family",
        "title": "Batch 1E: Geometry native family",
        "description": "Build low-level geometry-native libraries after the numerical backend families are frozen.",
    },
    {
        "id": "phase1_batch1f_onemkl_family",
        "phase": "phase1",
        "order": 6,
        "install_method_category": "I2_containerized_native_backend_family",
        "title": "Batch 1F: Intel oneMKL family",
        "description": "Build the Intel oneMKL-backed sparse and nonlinear backend container path after the open NLP family is frozen.",
    },
    {
        "id": "phase1_batch2a_solver_platforms_first_wave",
        "phase": "phase1",
        "order": 7,
        "install_method_category": "I1_containerized_native_solver_platform",
        "title": "Batch 2A: Core solver/platform first wave",
        "description": "Install the first-wave seed stack and coupling-adjacent platforms.",
    },
    {
        "id": "phase1_batch2b_solver_platforms_second_wave",
        "phase": "phase1",
        "order": 8,
        "install_method_category": "I1_containerized_native_solver_platform",
        "title": "Batch 2B: Core solver/platform second wave",
        "description": "Install the second-wave platforms after the first-wave solver path is stable.",
    },
    {
        "id": "phase1_batch3a_petsc_wrapper",
        "phase": "phase1",
        "order": 9,
        "install_method_category": "I4_host_companion_wrapper",
        "title": "Batch 3A: PETSc companion wrappers",
        "description": "Install PETSc-bound wrappers only after the PETSc family is green.",
    },
    {
        "id": "phase1_batch3b_nlp_wrapper",
        "phase": "phase1",
        "order": 10,
        "install_method_category": "I4_host_companion_wrapper",
        "title": "Batch 3B: NLP companion wrappers",
        "description": "Install wrappers that depend on the chosen nonlinear optimization backend family.",
    },
    {
        "id": "phase1_batch3c_coupling_wrapper",
        "phase": "phase1",
        "order": 11,
        "install_method_category": "I4_host_companion_wrapper",
        "title": "Batch 3C: Coupling wrappers",
        "description": "Install coupling wrappers once their paired solver platforms are verified.",
    },
    {
        "id": "phase1_batch3d_modelica_wrapper",
        "phase": "phase1",
        "order": 12,
        "install_method_category": "I4_host_companion_wrapper",
        "title": "Batch 3D: Modelica wrappers",
        "description": "Install OpenModelica-bound wrappers after the Modelica host runtime is verified.",
    },
    {
        "id": "phase1_batch3e_fmu_wrapper",
        "phase": "phase1",
        "order": 13,
        "install_method_category": "I4_host_companion_wrapper",
        "title": "Batch 3E: FMU wrappers",
        "description": "Install FMU wrappers after the chosen FMU host path is frozen.",
    },
    {
        "id": "phase1_batch3f_salome_wrapper",
        "phase": "phase1",
        "order": 14,
        "install_method_category": "I4_host_companion_wrapper",
        "title": "Batch 3F: SALOME companions",
        "description": "Install SALOME-bound translators after the SALOME platform is verified.",
    },
    {
        "id": "phase1_batch3g_visualization_wrapper",
        "phase": "phase1",
        "order": 15,
        "install_method_category": "I4_host_companion_wrapper",
        "title": "Batch 3G: Visualization companions",
        "description": "Install visualization companions after the visualization host stack is verified.",
    },
    {
        "id": "phase1_batch3h_rhino_host_wrapper",
        "phase": "phase1",
        "order": 16,
        "install_method_category": "I4_host_companion_wrapper",
        "title": "Batch 3H: Rhino host companions",
        "description": "Install Rhino-bound scripting and API companions after the local Rhino host runtime is verified.",
    },
    {
        "id": "phase1_batch4a_openmdao_adjacent",
        "phase": "phase1",
        "order": 17,
        "install_method_category": "I3_python_first_venv_package",
        "title": "Batch 4A: OpenMDAO-adjacent Python frameworks",
        "description": "Install OpenMDAO-adjacent Python frameworks in one shared uv environment.",
    },
    {
        "id": "phase1_batch4b_process_system",
        "phase": "phase1",
        "order": 18,
        "install_method_category": "I3_python_first_venv_package",
        "title": "Batch 4B: Process/system Python frameworks",
        "description": "Install process and system-model frameworks in one shared uv environment.",
    },
    {
        "id": "phase1_batch4c_inverse_physics_domain",
        "phase": "phase1",
        "order": 19,
        "install_method_category": "I3_python_first_venv_package",
        "title": "Batch 4C: Inverse-physics/domain Python frameworks",
        "description": "Install domain and inverse-physics frameworks in one shared uv environment.",
    },
    {
        "id": "phase1_batch4d_distributed_ml_reserve",
        "phase": "phase1",
        "order": 20,
        "install_method_category": "I3_python_first_venv_package",
        "title": "Batch 4D: Distributed/ML/reserve Python frameworks",
        "description": "Install distributed and ML-oriented reserve frameworks in one shared uv environment.",
    },
    {
        "id": "phase1_batch5_standards",
        "phase": "phase1",
        "order": 21,
        "install_method_category": "I5_knowledge_only_standard",
        "title": "Batch 5: Standards",
        "description": "Build knowledge-only validators, mappings, and examples for standards and exchange formats.",
    },
    {
        "id": "phase1_batch6_deferred_external_manual",
        "phase": "next_sprint",
        "order": 22,
        "install_method_category": "I6_deferred_external_manual",
        "title": "Batch 6: Deferred external/manual",
        "description": "Do not install in this sprint; prepare acquisition dossiers for the next sprint.",
    },
]

KB_BUILD_BATCH_DEFINITIONS = [
    {
        "id": "phase2_batch_k1_solver_platforms",
        "phase": "phase2",
        "order": 1,
        "kb_build_method_category": "K1_executable_solver_platform_pack",
        "title": "Phase 2 K1: Solver/platform packs",
        "description": "Build executable solver platform packs with runtime-linked recipes, adapters, and evidence.",
    },
    {
        "id": "phase2_batch_k2_backend_families",
        "phase": "phase2",
        "order": 2,
        "kb_build_method_category": "K2_backend_family_pack",
        "title": "Phase 2 K2: Backend family packs",
        "description": "Build one family pack per backend lineage, then add child overlays.",
    },
    {
        "id": "phase2_batch_k3_python_frameworks",
        "phase": "phase2",
        "order": 3,
        "kb_build_method_category": "K3_python_framework_pack",
        "title": "Phase 2 K3: Python framework packs",
        "description": "Build API-centric Python framework packs with import probes, recipes, and failure signatures.",
    },
    {
        "id": "phase2_batch_k4_host_companions",
        "phase": "phase2",
        "order": 4,
        "kb_build_method_category": "K4_companion_host_bound_pack",
        "title": "Phase 2 K4: Host companion packs",
        "description": "Build companion packs tied to verified parent runtimes and compatibility evidence.",
    },
    {
        "id": "phase2_batch_k5_standards",
        "phase": "phase2",
        "order": 5,
        "kb_build_method_category": "K5_standard_spec_pack",
        "title": "Phase 2 K5: Standard/spec packs",
        "description": "Build knowledge-only standard packs with validators, schema maps, and host mappings.",
    },
    {
        "id": "phase2_batch_k6_deferred_acquisition",
        "phase": "next_sprint",
        "order": 6,
        "kb_build_method_category": "K6_acquisition_deferred_pack",
        "title": "Phase 2 K6: Deferred acquisition packs",
        "description": "Build placeholder packs for externally acquired modules after acquisition prerequisites are met.",
    },
]


RUNTIME_PROFILES: list[dict] = [
    {
        "id": "eng_geometry_uv",
        "runtime_profile": "eng-geometry",
        "delivery_kind": "uv_venv",
        "module_ids": ["gmsh", "cadquery", "occt", "meshio", "compas"],
        "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
        "manifest_format": "requirements_txt",
        "manifest_path": "knowledge/coding-tools/runtime/uv/eng-geometry.requirements.txt",
        "runtime_locator": ".cache/knowledge-envs/eng-geometry",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_geometry_uv",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_geometry_uv --imports cadquery gmsh OCP meshio compas",
        "launcher_ref": "knowledge/coding-tools/runtime/launchers/eng-geometry.sh",
        "requirements": ["cadquery", "gmsh", "meshio", "compas"],
        "verification_enabled": True,
        "notes": ["Companion local geometry runtime for scripted CAD, meshing, translation, and geometry-side Python frameworks."],
    },
    {
        "id": "eng_geometry_docker",
        "runtime_profile": "eng-geometry",
        "delivery_kind": "docker_image",
        "module_ids": ["gmsh", "cadquery", "occt", "meshio", "compas"],
        "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
        "manifest_format": "dockerfile",
        "manifest_path": "knowledge/coding-tools/runtime/docker/eng-geometry.Dockerfile",
        "runtime_locator": "birtha/knowledge-eng-geometry:1.0.0",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_geometry_docker",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_geometry_docker",
        "launcher_ref": "knowledge/coding-tools/runtime/launchers/eng-geometry-container.sh",
        "requirements": [],
        "verification_enabled": False,
        "notes": ["Canonical Docker manifest for geometry modules; not verified in this workspace."],
    },
    {
        "id": "eng_thermochem_uv",
        "runtime_profile": "eng-thermochem",
        "delivery_kind": "uv_venv",
        "module_ids": ["cantera", "coolprop", "tespy"],
        "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
        "manifest_format": "requirements_txt",
        "manifest_path": "knowledge/coding-tools/runtime/uv/eng-thermochem.requirements.txt",
        "runtime_locator": ".cache/knowledge-envs/eng-thermochem",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_thermochem_uv",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_thermochem_uv --imports cantera CoolProp tespy",
        "launcher_ref": "knowledge/coding-tools/runtime/launchers/eng-thermochem.sh",
        "requirements": ["cantera", "coolprop", "tespy"],
        "verification_enabled": True,
        "notes": ["Companion local thermochemistry runtime for combustion and property tools."],
    },
    {
        "id": "eng_thermochem_docker",
        "runtime_profile": "eng-thermochem",
        "delivery_kind": "docker_image",
        "module_ids": ["cantera", "coolprop", "tespy"],
        "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
        "manifest_format": "dockerfile",
        "manifest_path": "knowledge/coding-tools/runtime/docker/eng-thermochem.Dockerfile",
        "runtime_locator": "birtha/knowledge-eng-thermochem:1.0.0",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_thermochem_docker",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_thermochem_docker",
        "launcher_ref": "knowledge/coding-tools/runtime/launchers/eng-thermochem-container.sh",
        "requirements": [],
        "verification_enabled": False,
        "notes": ["Canonical Docker manifest for thermochemistry modules; not verified in this workspace."],
    },
    {
        "id": "eng_mdo_uv",
        "runtime_profile": "eng-mdo",
        "delivery_kind": "uv_venv",
        "module_ids": [
            "casadi",
            "pymoo",
            "ortools",
            "pyomo",
            "openturns",
            "smt",
            "salib",
            "openmdao",
            "cvxpy",
            "jmetalpy",
            "enoppy",
            "dymos",
            "mphys",
            "optas",
            "nevergrad",
            "botorch"
        ],
        "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
        "manifest_format": "requirements_txt",
        "manifest_path": "knowledge/coding-tools/runtime/uv/eng-mdo.requirements.txt",
        "runtime_locator": ".cache/knowledge-envs/eng-mdo",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_mdo_uv",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_mdo_uv --imports casadi pymoo ortools pyomo.environ openturns smt SALib openmdao.api cvxpy jmetal enoppy dymos mphys optas nevergrad botorch",
        "launcher_ref": "knowledge/coding-tools/runtime/launchers/eng-mdo.sh",
        "requirements": [
            "casadi",
            "pymoo",
            "ortools",
            "pyomo",
            "openturns",
            "smt",
            "SALib",
            "openmdao",
            "cvxpy",
            "jmetalpy",
            "enoppy",
            "dymos",
            "mphys",
            "optas",
            "nevergrad",
            "botorch"
        ],
        "verification_enabled": True,
        "verification_reasons": [
            "Runtime profile eng-mdo passed its linked import health check during this sprint.",
            "cvxpy loaded with OR-Tools compatibility warnings for GLOP/PDLP on OR-Tools 9.15.6755; core imports still completed successfully.",
            "The shared MDO runtime now includes the Phase 1 CLI-installable OpenMDAO-adjacent and black-box optimization packages from the excluded tracker.",
        ],
        "notes": ["Companion local MDO runtime for optimization, UQ, and design-space tooling."],
    },
    {
        "id": "eng_mdo_docker",
        "runtime_profile": "eng-mdo",
        "delivery_kind": "docker_image",
        "module_ids": [
            "casadi",
            "pymoo",
            "ortools",
            "pyomo",
            "openturns",
            "smt",
            "salib",
            "openmdao",
            "cvxpy",
            "jmetalpy",
            "enoppy",
            "dymos",
            "mphys",
            "optas",
            "nevergrad",
            "botorch"
        ],
        "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
        "manifest_format": "dockerfile",
        "manifest_path": "knowledge/coding-tools/runtime/docker/eng-mdo.Dockerfile",
        "runtime_locator": "birtha/knowledge-eng-mdo:1.0.0",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_mdo_docker",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_mdo_docker",
        "launcher_ref": "knowledge/coding-tools/runtime/launchers/eng-mdo-container.sh",
        "requirements": [],
        "verification_enabled": False,
        "notes": ["Canonical Docker manifest for MDO modules; not verified in this workspace."],
    },
    {
        "id": "eng_structures_uv",
        "runtime_profile": "eng-structures",
        "delivery_kind": "uv_venv",
        "module_ids": ["fipy", "simpeg", "openpnm"],
        "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
        "manifest_format": "requirements_txt",
        "manifest_path": "knowledge/coding-tools/runtime/uv/eng-structures.requirements.txt",
        "runtime_locator": ".cache/knowledge-envs/eng-structures",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_structures_uv",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_structures_uv --imports fipy simpeg openpnm",
        "launcher_ref": "knowledge/coding-tools/runtime/launchers/eng-structures.sh",
        "requirements": ["fipy", "simpeg", "openpnm"],
        "verification_enabled": True,
        "verification_reasons": [
            "Runtime profile eng-structures passed its linked import health check during this sprint.",
            "The structures/domain runtime now includes the Phase 1 CLI-installable inverse-physics and porous-domain Python packages from the excluded tracker.",
        ],
        "notes": ["Companion local lightweight structures/PDE runtime for custom transport models and inverse/domain-specific Python packages."],
    },
    {
        "id": "eng_structures_docker",
        "runtime_profile": "eng-structures",
        "delivery_kind": "docker_image",
        "module_ids": ["fipy", "simpeg", "openpnm"],
        "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
        "manifest_format": "dockerfile",
        "manifest_path": "knowledge/coding-tools/runtime/docker/eng-structures.Dockerfile",
        "runtime_locator": "birtha/knowledge-eng-structures:1.0.0",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_structures_docker",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_structures_docker",
        "launcher_ref": "knowledge/coding-tools/runtime/launchers/eng-structures-container.sh",
        "requirements": [],
        "verification_enabled": False,
        "notes": ["Canonical Docker manifest for lightweight structures runtime; not verified in this workspace."],
    },
    {
        "id": "eng_system_uv",
        "runtime_profile": "eng-system",
        "delivery_kind": "uv_venv",
        "module_ids": ["pyspice", "fmpy", "idaes", "ompython", "simpy", "pyphs"],
        "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
        "manifest_format": "requirements_txt",
        "manifest_path": "knowledge/coding-tools/runtime/uv/eng-system.requirements.txt",
        "runtime_locator": ".cache/knowledge-envs/eng-system",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_system_uv",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_system_uv --imports PySpice fmpy idaes OMPython simpy pyphs",
        "launcher_ref": "knowledge/coding-tools/runtime/launchers/eng-system.sh",
        "requirements": [
            "PySpice",
            "fmpy",
            "idaes-pse",
            "ompython",
            "simpy",
            "numpy",
            "scipy",
            "sympy",
            "networkx",
            "progressbar2",
            "matplotlib",
            "h5py",
            "pyphs",
        ],
        "verification_enabled": True,
        "verification_reasons": [
            "Runtime profile eng-system passed its linked import health check during this sprint.",
            "The system/process runtime now includes the Phase 1 CLI-installable process-system Python packages from the excluded tracker.",
        ],
        "notes": ["Companion local system-model runtime for circuit, FMU, Modelica-adjacent, and process-system execution libraries."],
    },
    {
        "id": "eng_system_docker",
        "runtime_profile": "eng-system",
        "delivery_kind": "docker_image",
        "module_ids": ["pyspice", "fmpy", "idaes", "ompython", "simpy", "pyfmi"],
        "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
        "manifest_format": "dockerfile",
        "manifest_path": "knowledge/coding-tools/runtime/docker/eng-system.Dockerfile",
        "runtime_locator": "birtha/knowledge-eng-system:1.0.0",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_system_docker",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_system_docker",
        "launcher_ref": "knowledge/coding-tools/runtime/launchers/eng-system-container.sh",
        "requirements": [],
        "verification_enabled": False,
        "notes": ["Canonical Docker manifest for system modules; not verified in this workspace."],
    },
    {
        "id": "eng_backbone_uv",
        "runtime_profile": "eng-backbone",
        "delivery_kind": "uv_venv",
        "module_ids": ["pint", "unyt", "xarray", "h5py", "zarr", "dask", "parsl", "pybind11", "nanobind", "mpi4py", "ray", "vtk"],
        "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
        "manifest_format": "requirements_txt",
        "manifest_path": "knowledge/coding-tools/runtime/uv/eng-backbone.requirements.txt",
        "runtime_locator": ".cache/knowledge-envs/eng-backbone",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_backbone_uv",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_backbone_uv --imports pint unyt xarray h5py zarr dask parsl pybind11 nanobind mpi4py ray vtk",
        "launcher_ref": "knowledge/coding-tools/runtime/launchers/eng-backbone.sh",
        "requirements": ["pint", "unyt", "xarray", "h5py", "zarr", "dask", "parsl", "pybind11", "nanobind", "mpi4py", "ray", "vtk"],
        "verification_enabled": True,
        "verification_reasons": [
            "Runtime profile eng-backbone passed its linked import health check during this sprint.",
            "The backbone runtime now includes the Phase 1 CLI-installable distributed and visualization-side Python packages from the excluded tracker.",
        ],
        "notes": ["Companion local backbone runtime for units, arrays, orchestration, native bridges, and visualization/distributed support packages."],
    },
    {
        "id": "eng_backbone_docker",
        "runtime_profile": "eng-backbone",
        "delivery_kind": "docker_image",
        "module_ids": ["pint", "unyt", "xarray", "h5py", "zarr", "dask", "parsl", "pybind11", "nanobind", "mpi4py", "ray", "vtk", "precice"],
        "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
        "manifest_format": "dockerfile",
        "manifest_path": "knowledge/coding-tools/runtime/docker/eng-backbone.Dockerfile",
        "runtime_locator": "birtha/knowledge-eng-backbone:1.0.0",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_backbone_docker",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_backbone_docker",
        "launcher_ref": "knowledge/coding-tools/runtime/launchers/eng-backbone-container.sh",
        "requirements": [],
        "verification_enabled": False,
        "notes": ["Canonical Docker manifest for backbone modules; not verified in this workspace."],
    },
    {
        "id": "eng_dotnet_sdk",
        "runtime_profile": "eng-dotnet",
        "delivery_kind": "dotnet_toolchain",
        "module_ids": ["unitsnet", "mathnet_numerics", "picogk"],
        "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
        "manifest_format": "csproj",
        "manifest_path": "knowledge/coding-tools/runtime/dotnet/eng-dotnet/KnowledgeDotnetRuntime.csproj",
        "runtime_locator": "knowledge/coding-tools/runtime/dotnet/eng-dotnet/bin/Release/net9.0",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_dotnet_sdk",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_dotnet_sdk --dotnet-probe",
        "launcher_ref": "knowledge/coding-tools/runtime/launchers/eng-dotnet.sh",
        "requirements": [],
        "verification_enabled": True,
        "verification_reasons": [
            "Runtime profile eng-dotnet passed its linked health check during this sprint.",
            "The probe runs with DOTNET_ROLL_FORWARD=Major so the net9.0 test project can execute on the installed host runtime.",
            "The .NET runtime now restores and loads PicoGK from NuGet so geometry-kernel CLI installs can move through Phase 1 without manual acquisition.",
        ],
        "notes": ["Companion dotnet runtime for implemented engineering support libraries and CLI-installable geometry kernels."],
    },
    {
        "id": "eng_ipopt_onemkl_docker",
        "runtime_profile": "eng-ipopt-onemkl",
        "delivery_kind": "docker_image",
        "module_ids": ["ipopt", "coinhsl", "onemkl", "ma57", "ma77", "ma86", "ma97"],
        "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
        "manifest_format": "dockerfile",
        "manifest_path": "knowledge/coding-tools/runtime/docker/eng-ipopt-onemkl.Dockerfile",
        "runtime_locator": "birtha/knowledge-eng-ipopt-onemkl:1.0.0",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_ipopt_onemkl_docker",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_ipopt_onemkl_docker --container-command bash -lc 'pkg-config --exists ipopt && test -d /opt/vendor/coinhsl-src && test -f /opt/intel/oneapi/mkl/latest/lib/libmkl_rt.so && echo OK:ipopt,hsl,onemkl'",
        "launcher_ref": "knowledge/coding-tools/runtime/launchers/eng-ipopt-onemkl-container.sh",
        "requirements": [],
        "verification_enabled": False,
        "dockerfile_lines": [
            "FROM ubuntu:24.04",
            "SHELL [\"/bin/bash\", \"-lc\"]",
            "WORKDIR /workspace",
            "RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates wget gpg build-essential cmake ninja-build pkg-config git gfortran python3 python3-pip coinor-libipopt-dev && rm -rf /var/lib/apt/lists/*",
            "RUN wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor > /usr/share/keyrings/oneapi-archive-keyring.gpg && echo \"deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main\" > /etc/apt/sources.list.d/oneAPI.list && apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends intel-oneapi-mkl intel-oneapi-mkl-devel && rm -rf /var/lib/apt/lists/*",
            "COPY HSL/coinhsl-2024.05.15 /opt/vendor/coinhsl-src",
            "COPY HSL/CoinHSL.v2024.5.15.aarch64-apple-darwin-libgfortran5 /opt/vendor/coinhsl-prebuilt-darwin",
            "RUN test -f /opt/vendor/coinhsl-src/README && test -d /opt/vendor/coinhsl-src/ma57 && test -d /opt/vendor/coinhsl-src/hsl_ma77 && test -d /opt/vendor/coinhsl-src/hsl_ma86 && test -d /opt/vendor/coinhsl-src/hsl_ma97",
            "RUN test -f /opt/intel/oneapi/mkl/latest/lib/libmkl_rt.so",
            "CMD [\"bash\"]",
            "",
        ],
        "notes": [
            "Canonical Docker staging path for the open IPOPT backend with Intel oneMKL and locally provided HSL sources.",
            "This environment supersedes the earlier licensed-PARDISO acquisition path for the excluded-module recovery plan.",
        ],
    },
    {
        "id": "eng_rhino_host",
        "runtime_profile": "eng-rhino",
        "delivery_kind": "host_app",
        "module_ids": ["rhino8", "rhinocode", "yak", "rhino_common"],
        "supported_host_platforms": ["darwin-arm64"],
        "manifest_format": "other",
        "manifest_path": "knowledge/coding-tools/runtime/host/eng-rhino.manifest.txt",
        "runtime_locator": "/Applications/Rhino 8.app",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_rhino_host",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_rhino_host",
        "launcher_ref": "knowledge/coding-tools/runtime/launchers/eng-rhino.sh",
        "requirements": [],
        "verification_enabled": True,
        "verification_reasons": [
            "The local Rhino 8 host runtime is installed on this machine and the checked-in launcher resolves to the RhinoCode CLI.",
            "The RhinoCode CLI returned its version successfully during this sprint, so the host scripting path is directly linked to the knowledge base.",
            "Rhino's official scripting docs support Grasshopper Python and C# scripting, and RhinoCommon is available as a cross-platform NuGet package on Mac.",
        ],
        "verification_detail": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_rhino_host",
        "notes": [
            "Verified host-app runtime for Rhino 8 scripting via the local RhinoCode CLI and Yak tooling.",
            "Use this runtime for RhinoCommon- and Grasshopper-adjacent scripting paths that are bound to the installed Rhino host.",
        ],
    },
    {
        "id": "eng_wine_docker",
        "runtime_profile": "eng-wine",
        "delivery_kind": "docker_image",
        "module_ids": ["wine64", "cabextract", "unzip"],
        "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
        "manifest_format": "dockerfile",
        "manifest_path": "knowledge/coding-tools/runtime/docker/eng-wine.Dockerfile",
        "runtime_locator": "birtha/knowledge-eng-wine:1.0.0",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_wine_docker",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_wine_docker --container-command wine64 --version",
        "launcher_ref": "knowledge/coding-tools/runtime/launchers/eng-wine-container.sh",
        "requirements": [],
        "verification_enabled": True,
        "verification_reasons": [
            "Runtime profile eng-wine passed its linked health check during this sprint.",
            "The canonical Docker runtime installs wine64 so Windows-oriented CLI installers can be hosted in a repeatable knowledge-base environment.",
        ],
        "verification_detail": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_wine_docker --container-command wine64 --version",
        "dockerfile_lines": [
            "FROM python:3.11-slim-bookworm",
            "WORKDIR /workspace",
            "RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wine64 cabextract unzip && ln -s /usr/lib/wine/wine64 /usr/local/bin/wine64 && ln -s /usr/lib/wine/wineserver64 /usr/local/bin/wineserver64 && rm -rf /var/lib/apt/lists/*",
            "RUN wine64 --version",
            'CMD [\"python\"]',
            "",
        ],
        "notes": ["Canonical wine-backed Docker runtime for website-delivered Windows installers and FEMM-style tooling."],
    },
]


IMPLEMENTED_MODULES = [
    implemented(
        slug="cantera",
        name="Cantera",
        category="thermofluids_chemistry",
        module_class="application",
        bindings=["C++", "Python"],
        solves=["Combustion chemistry, equilibrium, reactor networks, and 1D flames"],
        best_for=["Thermochemistry screening and reaction-system prototyping"],
        not_for=["Full 3D CFD field solves"],
        source_refs=["minutes://table1#L300"],
        runtime_profile="eng_thermochem",
        import_target="cantera",
        related=["coolprop", "tespy"],
    ),
    implemented(
        slug="casadi",
        name="CasADi",
        category="optimization_uq_backbone",
        module_class="framework",
        bindings=["C++", "Python"],
        solves=["Differentiable design, control, and reduced-order models"],
        best_for=["Gradient-based model assembly with explicit derivatives"],
        not_for=["Non-differentiable black-box search"],
        source_refs=["minutes://table1#L302"],
        runtime_profile="eng_mdo",
        import_target="casadi",
        related=["openmdao", "pymoo"],
    ),
    implemented(
        slug="pymoo",
        name="pymoo",
        category="optimization_uq_backbone",
        module_class="framework",
        bindings=["Python"],
        solves=["Multi-objective black-box trade studies"],
        best_for=["Evolutionary search when derivatives are absent or misleading"],
        not_for=["Sparse gradient-dominated NLP solves"],
        source_refs=["minutes://table1#L304"],
        runtime_profile="eng_mdo",
        import_target="pymoo",
        related=["openmdao", "casadi"],
    ),
    implemented(
        slug="gmsh",
        name="Gmsh",
        category="geometry_manufacturing",
        module_class="application",
        bindings=["C++", "C", "Python"],
        solves=["Scripted mesh generation from parametric geometry"],
        best_for=["Deterministic geometry-to-mesh pipelines"],
        not_for=["Detailed CAD repair of messy legacy geometry"],
        source_refs=["minutes://table1#L305"],
        runtime_profile="eng_geometry",
        import_target="gmsh",
        related=["cadquery", "occt", "meshio"],
    ),
    implemented(
        slug="cadquery",
        name="CadQuery",
        category="geometry_manufacturing",
        module_class="framework",
        bindings=["Python"],
        solves=["Parametric CAD tied to design variables"],
        best_for=["Scripted geometry generation for optimization loops"],
        not_for=["Turnkey repair of arbitrary imported CAD"],
        source_refs=["minutes://table1#L306"],
        runtime_profile="eng_geometry",
        import_target="cadquery",
        related=["gmsh", "occt", "meshio"],
    ),
    implemented(
        slug="occt",
        name="Open CASCADE (OCCT)",
        category="geometry_manufacturing",
        module_class="runtime_kernel",
        bindings=["C++", "Python"],
        solves=["Kernel-level B-rep operations, exchange, and solid modeling"],
        best_for=["Geometry kernels beneath scripted CAD workflows"],
        not_for=["High-level workflow orchestration"],
        source_refs=["minutes://table1#L307"],
        runtime_profile="eng_geometry",
        import_target="OCP",
        related=["cadquery", "gmsh"],
    ),
    implemented(
        slug="ortools",
        name="OR-Tools",
        category="geometry_manufacturing",
        module_class="framework",
        bindings=["C++", "Python", "C#"],
        solves=["Job-shop scheduling, routing, packing, and production planning"],
        best_for=["Discrete logistics and factory-side constraints"],
        not_for=["Continuous physics simulation"],
        source_refs=["minutes://table1#L310"],
        runtime_profile="eng_mdo",
        import_target="ortools",
        related=["pyomo"],
    ),
    implemented(
        slug="pyomo",
        name="Pyomo",
        category="geometry_manufacturing",
        module_class="framework",
        bindings=["Python"],
        solves=["Mixed-integer plant design, dispatch, and scheduling"],
        best_for=["Discrete optimization with explicit algebraic models"],
        not_for=["Field-resolved PDE simulation"],
        source_refs=["minutes://table1#L311"],
        runtime_profile="eng_mdo",
        import_target="pyomo.environ",
        related=["ortools", "cvxpy"],
    ),
    implemented(
        slug="coolprop",
        name="CoolProp",
        category="thermofluids_chemistry",
        module_class="runtime_kernel",
        bindings=["C++", "Python", "C#"],
        solves=["Property evaluation across thermal and system models"],
        best_for=["Consistent fluid-property lookup inside system studies"],
        not_for=["Plant-level orchestration"],
        source_refs=["minutes://table1#L317"],
        runtime_profile="eng_thermochem",
        import_target="CoolProp",
        related=["cantera", "tespy"],
    ),
    implemented(
        slug="tespy",
        name="TESPy",
        category="thermofluids_chemistry",
        module_class="framework",
        bindings=["Python"],
        solves=["Heat-recovery, cooling-loop, and cycle-network studies"],
        best_for=["Thermal system architecture and network-level balances"],
        not_for=["Detailed 3D field simulation"],
        source_refs=["minutes://table1#L318"],
        runtime_profile="eng_thermochem",
        import_target="tespy",
        related=["cantera", "coolprop"],
    ),
    implemented(
        slug="fipy",
        name="FiPy",
        category="structures_pde",
        module_class="framework",
        bindings=["Python"],
        solves=["Diffusion, transport, and material submodels in Python"],
        best_for=["Fast custom PDE submodels"],
        not_for=["Large-scale production multiphysics solves"],
        source_refs=["minutes://table1#L323"],
        runtime_profile="eng_structures",
        import_target="fipy",
        related=["openmdao"],
    ),
    implemented(
        slug="pyspice",
        name="PySpice",
        category="electrics_dynamics_system",
        module_class="framework",
        bindings=["Python"],
        solves=["Power electronics, sensing, and control interface studies"],
        best_for=["Circuit and interface logic around larger engineering systems"],
        not_for=["Field-based electromagnetic solves"],
        source_refs=["minutes://table1#L328"],
        runtime_profile="eng_system",
        import_target="PySpice",
        related=["fmpy"],
    ),
    implemented(
        slug="openturns",
        name="OpenTURNS",
        category="optimization_uq_backbone",
        module_class="framework",
        bindings=["C++", "Python"],
        solves=["Probabilistic modeling, reliability, sensitivity, and metamodeling"],
        best_for=["UQ once the deterministic loop is stable"],
        not_for=["Raw high-fidelity simulation"],
        source_refs=["minutes://table1#L332"],
        runtime_profile="eng_mdo",
        import_target="openturns",
        related=["salib", "smt", "openmdao"],
    ),
    implemented(
        slug="smt",
        name="SMT",
        category="optimization_uq_backbone",
        module_class="framework",
        bindings=["Python"],
        solves=["Surrogate modeling and design of experiments"],
        best_for=["Expensive solver loops that need response surfaces"],
        not_for=["Standalone optimization orchestration"],
        source_refs=["minutes://table1#L333"],
        runtime_profile="eng_mdo",
        import_target="smt",
        related=["openturns", "salib", "openmdao"],
    ),
    implemented(
        slug="salib",
        name="SALib",
        category="optimization_uq_backbone",
        module_class="framework",
        bindings=["Python"],
        solves=["Global sensitivity analysis"],
        best_for=["Low-friction sensitivity screening"],
        not_for=["High-fidelity field solving"],
        source_refs=["minutes://table1#L334"],
        runtime_profile="eng_mdo",
        import_target="SALib",
        related=["openturns", "smt"],
    ),
    implemented(
        slug="openmdao",
        name="OpenMDAO",
        category="workflow_coupling",
        module_class="framework",
        bindings=["Python"],
        solves=["MDO orchestration, derivatives, solvers, and workflow graphs"],
        best_for=["Explicit multidisciplinary model graphs"],
        not_for=["Ad hoc shell-script orchestration"],
        source_refs=["minutes://table2#L346"],
        runtime_profile="eng_mdo",
        import_target="openmdao.api",
        related=["casadi", "pymoo", "openturns", "smt", "fmpy"],
    ),
    implemented(
        slug="fmpy",
        name="FMPy",
        category="workflow_coupling",
        module_class="integration_layer",
        bindings=["Python"],
        solves=["Python-side execution of FMUs"],
        best_for=["Operationalizing FMI artifacts inside Python workflows"],
        not_for=["Replacing the FMU-producing toolchain"],
        source_refs=["minutes://table2#L350"],
        runtime_profile="eng_system",
        import_target="fmpy",
        related=["openmdao"],
    ),
    implemented(
        slug="meshio",
        name="meshio",
        category="workflow_coupling",
        module_class="translator",
        bindings=["Python"],
        solves=["Mesh and field format translation"],
        best_for=["Unblocking multi-format geometry and mesh handoff"],
        not_for=["Physics solution"],
        source_refs=["minutes://table2#L353"],
        runtime_profile="eng_geometry",
        import_target="meshio",
        related=["gmsh", "cadquery", "occt"],
    ),
    implemented(
        slug="pint",
        name="Pint",
        category="workflow_coupling",
        module_class="runtime_kernel",
        bindings=["Python"],
        solves=["Dimensional consistency across Python workflows"],
        best_for=["Explicit engineering units discipline"],
        not_for=["Native solver execution by itself"],
        source_refs=["minutes://table2#L355"],
        runtime_profile="eng_backbone",
        import_target="pint",
        related=["unyt", "unitsnet"],
    ),
    implemented(
        slug="unyt",
        name="unyt",
        category="workflow_coupling",
        module_class="runtime_kernel",
        bindings=["Python"],
        solves=["Unit-aware arrays and quantities"],
        best_for=["Array-heavy physics data with explicit units"],
        not_for=["Standalone orchestration"],
        source_refs=["minutes://table2#L355"],
        runtime_profile="eng_backbone",
        import_target="unyt",
        related=["pint", "unitsnet"],
    ),
    implemented(
        slug="xarray",
        name="xarray",
        category="workflow_coupling",
        module_class="framework",
        bindings=["Python"],
        solves=["Labeled array storage and post-processing"],
        best_for=["Structured multidimensional results"],
        not_for=["Native solver kernels"],
        source_refs=["minutes://table2#L356"],
        runtime_profile="eng_backbone",
        import_target="xarray",
        related=["h5py", "zarr"],
    ),
    implemented(
        slug="h5py",
        name="h5py",
        category="workflow_coupling",
        module_class="runtime_kernel",
        bindings=["Python"],
        solves=["Large dataset storage and hierarchical I/O"],
        best_for=["Deterministic binary result persistence"],
        not_for=["Semantic model graphs"],
        source_refs=["minutes://table2#L356"],
        runtime_profile="eng_backbone",
        import_target="h5py",
        related=["xarray", "zarr"],
    ),
    implemented(
        slug="zarr",
        name="Zarr",
        category="workflow_coupling",
        module_class="runtime_kernel",
        bindings=["Python"],
        solves=["Chunked labeled dataset storage"],
        best_for=["Scalable result storage for larger studies"],
        not_for=["Simulation orchestration"],
        source_refs=["minutes://table2#L356"],
        runtime_profile="eng_backbone",
        import_target="zarr",
        related=["xarray", "h5py"],
    ),
    implemented(
        slug="dask",
        name="Dask",
        category="workflow_coupling",
        module_class="integration_layer",
        bindings=["Python"],
        solves=["Distributed parameter sweeps and workflow scaling"],
        best_for=["Larger studies that outgrow one process"],
        not_for=["Replacing domain solvers"],
        source_refs=["minutes://table2#L357"],
        runtime_profile="eng_backbone",
        import_target="dask",
        related=["parsl", "openmdao"],
    ),
    implemented(
        slug="parsl",
        name="Parsl",
        category="workflow_coupling",
        module_class="integration_layer",
        bindings=["Python"],
        solves=["Distributed execution of workflows and campaigns"],
        best_for=["Campaign-style parallel engineering studies"],
        not_for=["In-process numerical kernels"],
        source_refs=["minutes://table2#L357"],
        runtime_profile="eng_backbone",
        import_target="parsl",
        related=["dask"],
    ),
    implemented(
        slug="pybind11",
        name="pybind11",
        category="workflow_coupling",
        module_class="translator",
        bindings=["C++", "Python"],
        solves=["Native C++ to Python bindings"],
        best_for=["Custom kernel exposure without opaque CLI glue"],
        not_for=["High-level workflow orchestration"],
        source_refs=["minutes://table2#L358"],
        runtime_profile="eng_backbone",
        import_target="pybind11",
        related=["nanobind"],
    ),
    implemented(
        slug="nanobind",
        name="nanobind",
        category="workflow_coupling",
        module_class="translator",
        bindings=["C++", "Python"],
        solves=["Lean C++ to Python bindings"],
        best_for=["Modern native bridge surfaces"],
        not_for=["Task-level orchestration"],
        source_refs=["minutes://table2#L358"],
        runtime_profile="eng_backbone",
        import_target="nanobind",
        related=["pybind11"],
    ),
    implemented(
        slug="mpi4py",
        name="mpi4py",
        category="workflow_coupling",
        module_class="integration_layer",
        bindings=["Python", "MPI"],
        solves=["MPI control from Python workflows"],
        best_for=["Coordinating MPI-backed native codes from Python"],
        not_for=["Replacing MPI-native solver performance tuning"],
        source_refs=["minutes://table2#L359"],
        runtime_profile="eng_backbone",
        import_target="mpi4py",
        related=["dask", "parsl"],
    ),
    implemented(
        slug="cvxpy",
        name="CVXPY",
        category="optimization_uq_backbone",
        module_class="framework",
        bindings=["Python"],
        solves=["Convex optimization DSLs for embedded control and surrogate constraints"],
        best_for=["Convex subproblems inside larger engineering flows"],
        not_for=["General non-convex field simulation"],
        source_refs=["minutes://section1#L92", "minutes://section3#L108"],
        runtime_profile="eng_mdo",
        import_target="cvxpy",
        related=["pyomo", "openmdao"],
    ),
    implemented(
        slug="jmetalpy",
        name="jMetalPy",
        category="optimization_uq_backbone",
        module_class="framework",
        bindings=["Python"],
        solves=["Multi-objective metaheuristics"],
        best_for=["Alternative black-box search strategies"],
        not_for=["Gradient-based NLP"],
        source_refs=["minutes://section3#L99"],
        runtime_profile="eng_mdo",
        import_target="jmetal",
        related=["pymoo"],
    ),
    implemented(
        slug="enoppy",
        name="ENOPPY",
        category="optimization_uq_backbone",
        module_class="framework",
        bindings=["Python"],
        solves=["Engineering optimization benchmark problems"],
        best_for=["Testing optimizer robustness against engineering-style constraints"],
        not_for=["Production simulation"],
        source_refs=["minutes://section3#L106"],
        runtime_profile="eng_mdo",
        import_target="enoppy",
        related=["pymoo", "jmetalpy"],
    ),
    implemented(
        slug="unitsnet",
        name="UnitsNet",
        category="workflow_coupling",
        module_class="runtime_kernel",
        bindings=["C#"],
        solves=["Dimensional consistency in .NET workflows"],
        best_for=[".NET-side units discipline"],
        not_for=["Native solver execution by itself"],
        source_refs=["minutes://section_csharp#L290"],
        runtime_profile="eng_dotnet",
        import_target="UnitsNet",
        related=["pint", "unyt", "mathnet_numerics"],
    ),
    implemented(
        slug="mathnet_numerics",
        name="Math.NET Numerics",
        category="workflow_coupling",
        module_class="runtime_kernel",
        bindings=["C#"],
        solves=["Numerical helper routines for .NET engineering code"],
        best_for=["Numerical support around .NET-hosted workflows"],
        not_for=["High-fidelity multiphysics solving by itself"],
        source_refs=["minutes://section_csharp#L290"],
        runtime_profile="eng_dotnet",
        import_target="MathNet.Numerics",
        related=["unitsnet"],
    ),
]


INSTALLED_RUNTIME_LINK_PENDING_REASON = (
    "installed and import-verified in the knowledge runtime, but runtime-linked "
    "knowledge artifacts have not been built in this sprint"
)
INSTALLED_RUNTIME_LINK_PARENT_PENDING_REASON = (
    "installed and import-verified in the knowledge runtime, but the parent host "
    "runtime and runtime-linked knowledge artifacts have not been fully built in this sprint"
)
INSTALLED_DOTNET_RUNTIME_LINK_PENDING_REASON = (
    "installed and runtime-verified in the shared .NET knowledge runtime, but "
    "runtime-linked knowledge artifacts have not been built in this sprint"
)
PLANNED_IPOPT_ONEMKL_CONTAINER_REASON = (
    "canonical Docker path is defined for open IPOPT with staged local HSL inputs "
    "and Intel oneMKL, but the container build has not been verified in this sprint"
)
PLANNED_HSL_BACKEND_CONTAINER_REASON = (
    "local HSL source is staged for containerized backend packaging, but the canonical "
    "Docker build has not been verified in this sprint"
)
PLANNED_ONEMKL_SUBSTITUTE_REASON = (
    "licensed PARDISO acquisition has been replaced with an Intel oneMKL container path, "
    "but that canonical Docker build has not been verified in this sprint"
)
INSTALLED_RHINO_HOST_PENDING_REASON = (
    "installed and CLI-verified in the Rhino 8 host runtime, but runtime-linked "
    "knowledge artifacts have not been built in this sprint"
)


EXCLUDED_MODULES = [
    excluded(slug="openfoam", name="OpenFOAM", category="seed_stack", module_class="application", source_refs=["minutes://table1#L298"], reason="no viable canonical Docker runtime verified in this sprint"),
    excluded(slug="calculix", name="CalculiX", category="seed_stack", module_class="application", source_refs=["minutes://table1#L299"], reason="no viable canonical Docker runtime verified in this sprint"),
    excluded(slug="picogk_shapekernel", name="PicoGK / ShapeKernel", category="seed_stack", module_class="application", source_refs=["minutes://table1#L301"], reason=INSTALLED_DOTNET_RUNTIME_LINK_PENDING_REASON),
    excluded(slug="ipopt", name="IPOPT", category="seed_stack", module_class="runtime_kernel", source_refs=["minutes://table1#L303"], reason=PLANNED_IPOPT_ONEMKL_CONTAINER_REASON),
    excluded(slug="opencamlib", name="OpenCAMLib", category="geometry_manufacturing", module_class="runtime_kernel", source_refs=["minutes://table1#L308"], reason="no reliable isolated runtime was verified in this sprint"),
    excluded(slug="cgal", name="CGAL", category="geometry_manufacturing", module_class="runtime_kernel", source_refs=["minutes://table1#L309"], reason="no viable isolated runtime package was verified in this sprint"),
    excluded(slug="su2", name="SU2", category="thermofluids_chemistry", module_class="application", source_refs=["minutes://table1#L312"], reason="no viable canonical Docker runtime was verified in this sprint"),
    excluded(slug="code_saturne", name="code_saturne", category="thermofluids_chemistry", module_class="application", source_refs=["minutes://table1#L313"], reason="no viable canonical Docker runtime was verified in this sprint"),
    excluded(slug="openwam", name="OpenWAM", category="thermofluids_chemistry", module_class="application", source_refs=["minutes://table1#L314"], reason="no isolated runtime package was verified in this sprint"),
    excluded(slug="opensmokepp", name="OpenSMOKE++", category="thermofluids_chemistry", module_class="application", source_refs=["minutes://table1#L315"], reason="no isolated runtime package was verified in this sprint"),
    excluded(slug="tchem", name="TChem", category="thermofluids_chemistry", module_class="runtime_kernel", source_refs=["minutes://table1#L316"], reason="HPC chemistry runtime was not verified in this sprint"),
    excluded(slug="idaes", name="IDAES", category="thermofluids_chemistry", module_class="framework", source_refs=["minutes://table1#L319"], reason=INSTALLED_RUNTIME_LINK_PENDING_REASON),
    excluded(slug="fenicsx", name="FEniCSx", category="structures_pde", module_class="framework", source_refs=["minutes://table1#L320"], reason="no isolated runtime package was verified in this sprint"),
    excluded(slug="dealii", name="deal.II", category="structures_pde", module_class="framework", source_refs=["minutes://section2#L67"], reason="no isolated runtime package was verified in this sprint"),
    excluded(slug="hermes", name="Hermes", category="structures_pde", module_class="framework", source_refs=["minutes://section2#L75"], reason="no isolated runtime package was verified in this sprint"),
    excluded(slug="kratos_multiphysics", name="Kratos Multiphysics", category="structures_pde", module_class="framework", source_refs=["minutes://table1#L321"], reason="no viable canonical Docker runtime was verified in this sprint"),
    excluded(slug="moose", name="MOOSE", category="structures_pde", module_class="framework", source_refs=["minutes://table1#L322"], reason="no viable canonical Docker runtime was verified in this sprint"),
    excluded(slug="code_aster", name="Code_Aster", category="structures_pde", module_class="application", source_refs=["minutes://table1#L324"], reason="no viable canonical Docker runtime was verified in this sprint"),
    excluded(slug="project_chrono", name="Project Chrono", category="electrics_dynamics_system", module_class="framework", source_refs=["minutes://table1#L325"], reason="no reliable isolated runtime package was verified in this sprint"),
    excluded(slug="pyleecan", name="PYLEECAN", category="electrics_dynamics_system", module_class="application", source_refs=["minutes://table1#L326"], reason="package depends on a URL-only swat-em source that was not locked into a canonical isolated runtime in this sprint"),
    excluded(slug="femm", name="FEMM", category="electrics_dynamics_system", module_class="application", source_refs=["minutes://table1#L327"], reason="website-delivered Windows installer has not yet been mirrored into the wine-backed canonical runtime"),
    excluded(slug="openmodelica", name="OpenModelica", category="electrics_dynamics_system", module_class="application", source_refs=["minutes://table1#L329"], reason="no canonical headless Modelica toolchain was verified in this sprint"),
    excluded(slug="ompython", name="OMPython", category="electrics_dynamics_system", module_class="integration_layer", source_refs=["minutes://table1#L329"], reason=INSTALLED_RUNTIME_LINK_PARENT_PENDING_REASON),
    excluded(slug="modelica_standard_library", name="Modelica Standard Library", category="electrics_dynamics_system", module_class="standard", source_refs=["minutes://table1#L329"], reason="depends on a verified Modelica host that was not packaged in this sprint", executable=False),
    excluded(slug="pyoptsparse", name="pyOptSparse", category="optimization_uq_backbone", module_class="framework", source_refs=["minutes://table1#L330"], reason="depends on the open IPOPT plus oneMKL/HSL container path that has not been verified in this sprint"),
    excluded(slug="dakota", name="Dakota", category="optimization_uq_backbone", module_class="application", source_refs=["minutes://table1#L331"], reason="no isolated runtime package was verified in this sprint"),
    excluded(slug="petsc", name="PETSc", category="optimization_uq_backbone", module_class="runtime_kernel", source_refs=["minutes://table1#L335"], reason="HPC native runtime was not verified in this sprint"),
    excluded(slug="petsc4py", name="petsc4py", category="optimization_uq_backbone", module_class="integration_layer", source_refs=["minutes://table1#L335"], reason="depends on PETSc runtime that was not verified in this sprint"),
    excluded(slug="sundials", name="SUNDIALS", category="optimization_uq_backbone", module_class="runtime_kernel", source_refs=["minutes://table1#L336"], reason="native solver stack was not verified in this sprint"),
    excluded(slug="mphys", name="MPhys", category="workflow_coupling", module_class="integration_layer", source_refs=["minutes://table2#L347"], reason=INSTALLED_RUNTIME_LINK_PENDING_REASON),
    excluded(slug="precice", name="preCICE", category="workflow_coupling", module_class="integration_layer", source_refs=["minutes://table2#L348"], reason="no viable canonical Docker runtime was verified in this sprint"),
    excluded(slug="fmi_fmus", name="FMI / FMUs", category="workflow_coupling", module_class="standard", source_refs=["minutes://table2#L349"], reason="standard/specification, not a standalone runtime installation", executable=False),
    excluded(slug="pyfmi", name="PyFMI", category="workflow_coupling", module_class="integration_layer", source_refs=["minutes://table2#L350"], reason="native FMI backend was not verified in this sprint"),
    excluded(slug="salome", name="SALOME", category="workflow_coupling", module_class="application", source_refs=["minutes://table2#L352"], reason="GUI-heavy platform was not packaged in this sprint"),
    excluded(slug="medcoupling", name="MEDCoupling", category="workflow_coupling", module_class="translator", source_refs=["minutes://table2#L353"], reason="native SALOME dependency stack was not verified in this sprint"),
    excluded(slug="cgns", name="CGNS", category="workflow_coupling", module_class="standard", source_refs=["minutes://table2#L354"], reason="standard/format, not a standalone runtime installation", executable=False),
    excluded(slug="exodus_ii", name="Exodus II", category="workflow_coupling", module_class="standard", source_refs=["minutes://table2#L354"], reason="standard/format, not a standalone runtime installation", executable=False),
    excluded(slug="ray", name="Ray", category="workflow_coupling", module_class="integration_layer", source_refs=["minutes://table2#L357"], reason=INSTALLED_RUNTIME_LINK_PENDING_REASON),
    excluded(slug="paraview", name="ParaView", category="workflow_coupling", module_class="application", source_refs=["minutes://table2#L360"], reason="GUI-heavy visualization stack was not packaged in this sprint"),
    excluded(slug="vtk", name="VTK", category="workflow_coupling", module_class="framework", source_refs=["minutes://table2#L360"], reason=INSTALLED_RUNTIME_LINK_PARENT_PENDING_REASON),
    excluded(slug="compas", name="Compas", category="geometry_manufacturing", module_class="framework", source_refs=["minutes://section5#L147"], reason=INSTALLED_RUNTIME_LINK_PENDING_REASON),
    excluded(slug="simpeg", name="SimPEG", category="domain_specific", module_class="framework", source_refs=["minutes://section4#L125"], reason=INSTALLED_RUNTIME_LINK_PENDING_REASON),
    excluded(slug="pyphs", name="PyPHS", category="domain_specific", module_class="framework", source_refs=["minutes://section4#L132"], reason="not prioritized for this sprint"),
    excluded(slug="rhino_common", name="RhinoCommon", category="csharp_examples", module_class="framework", source_refs=["minutes://section_csharp#L290"], reason=INSTALLED_RHINO_HOST_PENDING_REASON),
    excluded(slug="mbdyn", name="MBDyn", category="reserve", module_class="application", source_refs=["minutes://table1#L338"], reason="reserve-list runtime not prioritized in this sprint"),
    excluded(slug="rmg_py", name="RMG-Py", category="reserve", module_class="application", source_refs=["minutes://table1#L338"], reason="reserve-list runtime not prioritized in this sprint"),
    excluded(slug="simpy", name="SimPy", category="reserve", module_class="framework", source_refs=["minutes://table1#L338"], reason=INSTALLED_RUNTIME_LINK_PENDING_REASON),
    excluded(slug="botorch", name="BoTorch", category="reserve", module_class="framework", source_refs=["minutes://table1#L338"], reason=INSTALLED_RUNTIME_LINK_PENDING_REASON),
    excluded(slug="nevergrad", name="Nevergrad", category="reserve", module_class="framework", source_refs=["minutes://table1#L338"], reason=INSTALLED_RUNTIME_LINK_PENDING_REASON),
    excluded(slug="openpnm", name="OpenPNM", category="reserve", module_class="framework", source_refs=["minutes://table1#L338"], reason=INSTALLED_RUNTIME_LINK_PENDING_REASON),
    excluded(slug="porepy", name="PorePy", category="reserve", module_class="framework", source_refs=["minutes://table1#L338"], reason="reserve-list runtime not prioritized in this sprint"),
    excluded(slug="optas", name="OptaS", category="optimization_uq_backbone", module_class="framework", source_refs=["minutes://section3#L114"], reason=INSTALLED_RUNTIME_LINK_PENDING_REASON),
    excluded(slug="dymos", name="Dymos", category="workflow_coupling", module_class="framework", source_refs=["minutes://section_actual_stack#L371"], reason=INSTALLED_RUNTIME_LINK_PENDING_REASON),
    excluded(slug="ma57", name="MA57", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L728"], reason=PLANNED_HSL_BACKEND_CONTAINER_REASON),
    excluded(slug="ma77", name="MA77", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L821"], reason=PLANNED_HSL_BACKEND_CONTAINER_REASON),
    excluded(slug="ma86", name="MA86", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L821"], reason=PLANNED_HSL_BACKEND_CONTAINER_REASON),
    excluded(slug="ma87", name="MA87", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L821"], reason="licensed sparse direct solver backend not packaged in this sprint"),
    excluded(slug="ma97", name="MA97", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L821"], reason=PLANNED_HSL_BACKEND_CONTAINER_REASON),
    excluded(slug="mumps", name="MUMPS", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L729"], reason="native sparse direct backend was not verified in this sprint"),
    excluded(slug="superlu", name="SuperLU", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L730"], reason="native sparse direct backend was not verified in this sprint"),
    excluded(slug="superlu_dist", name="SuperLU_DIST", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L730"], reason="native sparse direct backend was not verified in this sprint"),
    excluded(slug="pardiso", name="PARDISO", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L731"], reason=PLANNED_ONEMKL_SUBSTITUTE_REASON),
    excluded(slug="petsc_ksp", name="PETSc KSP", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L732"], reason="PETSc runtime was not verified in this sprint"),
    excluded(slug="petsc_gamg", name="PETSc GAMG", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L852"], reason="PETSc runtime was not verified in this sprint"),
    excluded(slug="trilinos", name="Trilinos", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L733"], reason="Trilinos runtime was not verified in this sprint"),
    excluded(slug="trilinos_belos", name="Trilinos Belos", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L733"], reason="Trilinos runtime was not verified in this sprint"),
    excluded(slug="hypre", name="hypre", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L734"], reason="native AMG backend was not verified in this sprint"),
    excluded(slug="suitesparse", name="SuiteSparse", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L735"], reason="native sparse factorization backend was not verified in this sprint"),
    excluded(slug="umfpack", name="UMFPACK", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L824"], reason="native sparse factorization backend was not verified in this sprint"),
    excluded(slug="cholmod", name="CHOLMOD", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L824"], reason="native sparse factorization backend was not verified in this sprint"),
    excluded(slug="klu", name="KLU", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L824"], reason="native sparse factorization backend was not verified in this sprint"),
    excluded(slug="strumpack", name="STRUMPACK", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L825"], reason="native sparse direct backend was not verified in this sprint"),
    excluded(slug="trilinos_ifpack2", name="Trilinos Ifpack2", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L853"], reason="Trilinos runtime was not verified in this sprint"),
    excluded(slug="trilinos_muelu", name="Trilinos MueLu", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L854"], reason="Trilinos runtime was not verified in this sprint"),
    excluded(slug="slepc", name="SLEPc", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L866"], reason="PETSc-based eigensolver runtime was not verified in this sprint"),
    excluded(slug="primme", name="PRIMME", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L867"], reason="native eigensolver runtime was not verified in this sprint"),
]


def _recovery_entry(
    *,
    install_method_category: str,
    install_batch: str,
    parent_runtime_refs: list[str] | None = None,
    blocked_by_refs: list[str] | None = None,
    manual_acquisition_required: bool = False,
    acquisition_status: str = "not_required",
    phase_target: str = "phase1",
    phase_state: str = "planned",
    cli_install_channel: str = "unspecified",
    cli_phase1_status: str = "ready",
    user_intervention_class: str = "not_required",
) -> dict[str, object]:
    kb_build_method_category = INSTALL_METHOD_CATEGORIES[install_method_category]["kb_build_method_category"]
    kb_build_batch_by_method = {
        "K1_executable_solver_platform_pack": "phase2_batch_k1_solver_platforms",
        "K2_backend_family_pack": "phase2_batch_k2_backend_families",
        "K3_python_framework_pack": "phase2_batch_k3_python_frameworks",
        "K4_companion_host_bound_pack": "phase2_batch_k4_host_companions",
        "K5_standard_spec_pack": "phase2_batch_k5_standards",
        "K6_acquisition_deferred_pack": "phase2_batch_k6_deferred_acquisition",
    }
    return {
        "install_method_category": install_method_category,
        "install_batch": install_batch,
        "kb_build_method_category": kb_build_method_category,
        "kb_build_batch": kb_build_batch_by_method[kb_build_method_category],
        "phase_target": phase_target,
        "phase_state": phase_state,
        "parent_runtime_refs": parent_runtime_refs or [],
        "blocked_by_refs": blocked_by_refs or [],
        "manual_acquisition_required": manual_acquisition_required,
        "acquisition_status": acquisition_status,
        "cli_install_channel": cli_install_channel,
        "cli_phase1_status": cli_phase1_status,
        "user_intervention_class": user_intervention_class,
    }


RECOVERY_METADATA_BY_SLUG: dict[str, dict[str, object]] = {}

for slug in (
    "openfoam",
    "calculix",
    "code_saturne",
    "su2",
    "code_aster",
    "openwam",
    "opensmokepp",
    "openmodelica",
):
    RECOVERY_METADATA_BY_SLUG[slug] = _recovery_entry(
        install_method_category="I1_containerized_native_solver_platform",
        install_batch="phase1_batch2a_solver_platforms_first_wave",
        cli_install_channel="docker_build",
    )

for slug in (
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
):
    RECOVERY_METADATA_BY_SLUG[slug] = _recovery_entry(
        install_method_category="I1_containerized_native_solver_platform",
        install_batch="phase1_batch2b_solver_platforms_second_wave",
        cli_install_channel="docker_build",
    )

for slug in ("petsc", "petsc_ksp", "petsc_gamg", "slepc", "hypre", "primme"):
    RECOVERY_METADATA_BY_SLUG[slug] = _recovery_entry(
        install_method_category="I2_containerized_native_backend_family",
        install_batch="phase1_batch1a_petsc_family",
        cli_install_channel="docker_build",
    )

for slug in ("trilinos", "trilinos_belos", "trilinos_ifpack2", "trilinos_muelu"):
    RECOVERY_METADATA_BY_SLUG[slug] = _recovery_entry(
        install_method_category="I2_containerized_native_backend_family",
        install_batch="phase1_batch1b_trilinos_family",
        cli_install_channel="docker_build",
    )

for slug in ("mumps", "superlu", "superlu_dist", "suitesparse", "cholmod", "umfpack", "klu", "strumpack"):
    RECOVERY_METADATA_BY_SLUG[slug] = _recovery_entry(
        install_method_category="I2_containerized_native_backend_family",
        install_batch="phase1_batch1c_sparse_direct_family",
        cli_install_channel="docker_build",
    )

for slug in ("ipopt", "sundials", "tchem"):
    RECOVERY_METADATA_BY_SLUG[slug] = _recovery_entry(
        install_method_category="I2_containerized_native_backend_family",
        install_batch="phase1_batch1d_nlp_time_chem_family",
        cli_install_channel="docker_build",
    )
RECOVERY_METADATA_BY_SLUG["ipopt"]["cli_install_channel"] = "docker_build_with_local_hsl"

for slug in ("ma57", "ma77", "ma86", "ma97"):
    RECOVERY_METADATA_BY_SLUG[slug] = _recovery_entry(
        install_method_category="I2_containerized_native_backend_family",
        install_batch="phase1_batch1d_nlp_time_chem_family",
        cli_install_channel="docker_build_with_local_hsl",
    )

for slug in ("cgal", "opencamlib"):
    RECOVERY_METADATA_BY_SLUG[slug] = _recovery_entry(
        install_method_category="I2_containerized_native_backend_family",
        install_batch="phase1_batch1e_geometry_native_family",
        cli_install_channel="docker_build",
    )

RECOVERY_METADATA_BY_SLUG["pardiso"] = _recovery_entry(
    install_method_category="I2_containerized_native_backend_family",
    install_batch="phase1_batch1f_onemkl_family",
    cli_install_channel="docker_build_with_onemkl",
)

RECOVERY_METADATA_BY_SLUG["picogk_shapekernel"] = _recovery_entry(
    install_method_category="I2_containerized_native_backend_family",
    install_batch="phase1_batch1e_geometry_native_family",
    parent_runtime_refs=["artifact://environment-spec/eng_dotnet_sdk"],
    cli_install_channel="dotnet_nuget",
)

for slug in ("dymos", "mphys"):
    RECOVERY_METADATA_BY_SLUG[slug] = _recovery_entry(
        install_method_category="I3_python_first_venv_package",
        install_batch="phase1_batch4a_openmdao_adjacent",
        cli_install_channel="uv_pip",
    )

for slug in ("idaes", "optas", "simpy"):
    RECOVERY_METADATA_BY_SLUG[slug] = _recovery_entry(
        install_method_category="I3_python_first_venv_package",
        install_batch="phase1_batch4b_process_system",
        cli_install_channel="uv_pip",
    )

for slug in ("compas", "simpeg", "pyphs", "openpnm", "porepy", "rmg_py"):
    RECOVERY_METADATA_BY_SLUG[slug] = _recovery_entry(
        install_method_category="I3_python_first_venv_package",
        install_batch="phase1_batch4c_inverse_physics_domain",
        cli_install_channel="uv_pip",
    )

for slug in ("ray", "botorch", "nevergrad"):
    RECOVERY_METADATA_BY_SLUG[slug] = _recovery_entry(
        install_method_category="I3_python_first_venv_package",
        install_batch="phase1_batch4d_distributed_ml_reserve",
        cli_install_channel="uv_pip",
    )

RECOVERY_METADATA_BY_SLUG["petsc4py"] = _recovery_entry(
    install_method_category="I4_host_companion_wrapper",
    install_batch="phase1_batch3a_petsc_wrapper",
    parent_runtime_refs=[minutes_module_ref("petsc")],
    blocked_by_refs=[minutes_module_ref("petsc")],
    cli_install_channel="uv_pip_after_parent_runtime",
    cli_phase1_status="blocked_by_parent_runtime",
)
RECOVERY_METADATA_BY_SLUG["pyoptsparse"] = _recovery_entry(
    install_method_category="I4_host_companion_wrapper",
    install_batch="phase1_batch3b_nlp_wrapper",
    parent_runtime_refs=[RECOVERY_DEFAULTS["pyoptsparse_default_backend"]],
    blocked_by_refs=[RECOVERY_DEFAULTS["pyoptsparse_default_backend"]],
    cli_install_channel="uv_pip_after_parent_runtime",
    cli_phase1_status="blocked_by_parent_runtime",
)
RECOVERY_METADATA_BY_SLUG["precice"] = _recovery_entry(
    install_method_category="I4_host_companion_wrapper",
    install_batch="phase1_batch3c_coupling_wrapper",
    parent_runtime_refs=list(RECOVERY_DEFAULTS["precice_default_solver_pair"]),
    blocked_by_refs=list(RECOVERY_DEFAULTS["precice_default_solver_pair"]),
    cli_install_channel="docker_or_source_build_after_parent_runtime",
    cli_phase1_status="blocked_by_parent_runtime",
)
RECOVERY_METADATA_BY_SLUG["ompython"] = _recovery_entry(
    install_method_category="I4_host_companion_wrapper",
    install_batch="phase1_batch3d_modelica_wrapper",
    parent_runtime_refs=[minutes_module_ref("openmodelica")],
    blocked_by_refs=[minutes_module_ref("openmodelica")],
    cli_install_channel="uv_pip_after_parent_runtime",
    cli_phase1_status="blocked_by_parent_runtime",
)
RECOVERY_METADATA_BY_SLUG["pyfmi"] = _recovery_entry(
    install_method_category="I4_host_companion_wrapper",
    install_batch="phase1_batch3e_fmu_wrapper",
    parent_runtime_refs=[RECOVERY_DEFAULTS["pyfmi_default_host"]],
    blocked_by_refs=[RECOVERY_DEFAULTS["pyfmi_default_host"]],
    cli_install_channel="uv_pip_after_parent_runtime",
    cli_phase1_status="blocked_by_parent_runtime",
)
RECOVERY_METADATA_BY_SLUG["medcoupling"] = _recovery_entry(
    install_method_category="I4_host_companion_wrapper",
    install_batch="phase1_batch3f_salome_wrapper",
    parent_runtime_refs=[minutes_module_ref("salome")],
    blocked_by_refs=[minutes_module_ref("salome")],
    cli_install_channel="uv_pip_after_parent_runtime",
    cli_phase1_status="blocked_by_parent_runtime",
)
RECOVERY_METADATA_BY_SLUG["vtk"] = _recovery_entry(
    install_method_category="I4_host_companion_wrapper",
    install_batch="phase1_batch3g_visualization_wrapper",
    parent_runtime_refs=[RECOVERY_DEFAULTS["vtk_default_host"]],
    blocked_by_refs=[RECOVERY_DEFAULTS["vtk_default_host"]],
    cli_install_channel="uv_pip_after_parent_runtime",
    cli_phase1_status="blocked_by_parent_runtime",
)

for slug in ("cgns", "exodus_ii", "fmi_fmus"):
    RECOVERY_METADATA_BY_SLUG[slug] = _recovery_entry(
        install_method_category="I5_knowledge_only_standard",
        install_batch="phase1_batch5_standards",
        cli_install_channel="knowledge_only",
        cli_phase1_status="knowledge_only",
    )

RECOVERY_METADATA_BY_SLUG["modelica_standard_library"] = _recovery_entry(
    install_method_category="I5_knowledge_only_standard",
    install_batch="phase1_batch5_standards",
    parent_runtime_refs=[minutes_module_ref("openmodelica")],
    blocked_by_refs=[minutes_module_ref("openmodelica")],
    cli_install_channel="knowledge_only",
    cli_phase1_status="knowledge_only",
)

for slug in ("femm", "pyleecan"):
    RECOVERY_METADATA_BY_SLUG[slug] = _recovery_entry(
        install_method_category="I6_deferred_external_manual",
        install_batch="phase1_batch6_deferred_external_manual",
        manual_acquisition_required=True,
        acquisition_status="awaiting_user_inputs",
        phase_target="next_sprint",
        phase_state="deferred",
        cli_phase1_status="manual_acquisition_required",
        user_intervention_class="website_download",
    )

RECOVERY_METADATA_BY_SLUG["pyleecan"] = _recovery_entry(
    install_method_category="I6_deferred_external_manual",
    install_batch="phase1_batch6_deferred_external_manual",
    manual_acquisition_required=True,
    acquisition_status="awaiting_website_or_git_dependency_source",
    phase_target="next_sprint",
    phase_state="deferred",
    cli_install_channel="uv_pip_with_url_dependency",
    cli_phase1_status="manual_acquisition_required",
    user_intervention_class="website_download",
)
RECOVERY_METADATA_BY_SLUG["femm"] = _recovery_entry(
    install_method_category="I6_deferred_external_manual",
    install_batch="phase1_batch6_deferred_external_manual",
    manual_acquisition_required=True,
    acquisition_status="awaiting_website_downloadable_windows_installer",
    phase_target="next_sprint",
    phase_state="deferred",
    parent_runtime_refs=["artifact://environment-spec/eng_wine_docker"],
    cli_install_channel="wine_installer_after_download",
    cli_phase1_status="manual_acquisition_required",
    user_intervention_class="website_download",
)
for slug in ("ma87",):
    RECOVERY_METADATA_BY_SLUG[slug] = _recovery_entry(
        install_method_category="I6_deferred_external_manual",
        install_batch="phase1_batch6_deferred_external_manual",
        manual_acquisition_required=True,
        acquisition_status="awaiting_license_and_binary_delivery",
        phase_target="next_sprint",
        phase_state="deferred",
        cli_install_channel="licensed_binary_delivery",
        cli_phase1_status="manual_acquisition_required",
        user_intervention_class="proprietary_license",
    )
RECOVERY_METADATA_BY_SLUG["rhino_common"] = _recovery_entry(
    install_method_category="I4_host_companion_wrapper",
    install_batch="phase1_batch3h_rhino_host_wrapper",
    parent_runtime_refs=["artifact://environment-spec/eng_rhino_host"],
    cli_install_channel="host_app_cli",
)

RECOVERY_METADATA_BY_SLUG["petsc_ksp"]["parent_runtime_refs"] = [minutes_module_ref("petsc")]
RECOVERY_METADATA_BY_SLUG["petsc_ksp"]["blocked_by_refs"] = [minutes_module_ref("petsc")]
RECOVERY_METADATA_BY_SLUG["petsc_gamg"]["parent_runtime_refs"] = [minutes_module_ref("petsc")]
RECOVERY_METADATA_BY_SLUG["petsc_gamg"]["blocked_by_refs"] = [minutes_module_ref("petsc")]
RECOVERY_METADATA_BY_SLUG["slepc"]["parent_runtime_refs"] = [minutes_module_ref("petsc")]
RECOVERY_METADATA_BY_SLUG["slepc"]["blocked_by_refs"] = [minutes_module_ref("petsc")]
RECOVERY_METADATA_BY_SLUG["trilinos_belos"]["parent_runtime_refs"] = [minutes_module_ref("trilinos")]
RECOVERY_METADATA_BY_SLUG["trilinos_belos"]["blocked_by_refs"] = [minutes_module_ref("trilinos")]
RECOVERY_METADATA_BY_SLUG["trilinos_ifpack2"]["parent_runtime_refs"] = [minutes_module_ref("trilinos")]
RECOVERY_METADATA_BY_SLUG["trilinos_ifpack2"]["blocked_by_refs"] = [minutes_module_ref("trilinos")]
RECOVERY_METADATA_BY_SLUG["trilinos_muelu"]["parent_runtime_refs"] = [minutes_module_ref("trilinos")]
RECOVERY_METADATA_BY_SLUG["trilinos_muelu"]["blocked_by_refs"] = [minutes_module_ref("trilinos")]

EXCLUDED_ENVIRONMENT_REFS = {
    "picogk_shapekernel": ["artifact://environment-spec/eng_dotnet_sdk"],
    "ipopt": ["artifact://environment-spec/eng_ipopt_onemkl_docker"],
    "pyoptsparse": ["artifact://environment-spec/eng_ipopt_onemkl_docker"],
    "ma57": ["artifact://environment-spec/eng_ipopt_onemkl_docker"],
    "ma77": ["artifact://environment-spec/eng_ipopt_onemkl_docker"],
    "ma86": ["artifact://environment-spec/eng_ipopt_onemkl_docker"],
    "ma97": ["artifact://environment-spec/eng_ipopt_onemkl_docker"],
    "pardiso": ["artifact://environment-spec/eng_ipopt_onemkl_docker"],
    "compas": [
        "artifact://environment-spec/eng_geometry_uv",
        "artifact://environment-spec/eng_geometry_docker",
    ],
    "dymos": [
        "artifact://environment-spec/eng_mdo_uv",
        "artifact://environment-spec/eng_mdo_docker",
    ],
    "mphys": [
        "artifact://environment-spec/eng_mdo_uv",
        "artifact://environment-spec/eng_mdo_docker",
    ],
    "optas": [
        "artifact://environment-spec/eng_mdo_uv",
        "artifact://environment-spec/eng_mdo_docker",
    ],
    "nevergrad": [
        "artifact://environment-spec/eng_mdo_uv",
        "artifact://environment-spec/eng_mdo_docker",
    ],
    "botorch": [
        "artifact://environment-spec/eng_mdo_uv",
        "artifact://environment-spec/eng_mdo_docker",
    ],
    "idaes": [
        "artifact://environment-spec/eng_system_uv",
        "artifact://environment-spec/eng_system_docker",
    ],
    "ompython": [
        "artifact://environment-spec/eng_system_uv",
        "artifact://environment-spec/eng_system_docker",
    ],
    "simpy": [
        "artifact://environment-spec/eng_system_uv",
        "artifact://environment-spec/eng_system_docker",
    ],
    "simpeg": [
        "artifact://environment-spec/eng_structures_uv",
        "artifact://environment-spec/eng_structures_docker",
    ],
    "openpnm": [
        "artifact://environment-spec/eng_structures_uv",
        "artifact://environment-spec/eng_structures_docker",
    ],
    "ray": [
        "artifact://environment-spec/eng_backbone_uv",
        "artifact://environment-spec/eng_backbone_docker",
    ],
    "vtk": [
        "artifact://environment-spec/eng_backbone_uv",
        "artifact://environment-spec/eng_backbone_docker",
    ],
    "rhino_common": ["artifact://environment-spec/eng_rhino_host"],
}


def mark_excluded_module_installed(slug: str, *, acquisition_status: str = "verified_in_knowledge_runtime") -> None:
    metadata = RECOVERY_METADATA_BY_SLUG[slug]
    metadata["phase_state"] = "installed"
    metadata["cli_phase1_status"] = "installed"
    metadata["acquisition_status"] = acquisition_status


for slug in (
    "picogk_shapekernel",
    "compas",
    "dymos",
    "mphys",
    "optas",
    "nevergrad",
    "botorch",
    "idaes",
    "simpy",
    "simpeg",
    "openpnm",
    "ray",
):
    mark_excluded_module_installed(slug)

for slug in ("ompython", "vtk"):
    mark_excluded_module_installed(slug, acquisition_status="verified_in_knowledge_runtime_parent_pending")

mark_excluded_module_installed("rhino_common")

DEFERRED_ACQUISITION_DETAILS = {
    "femm": {
        "requested_from_user": "Provide the approved FEMM installer URL, mirrored binary, or downloaded installer artifact so it can be staged inside the wine-backed runtime.",
        "recommended_runtime_target": "wine_backed_docker_runtime",
        "next_sprint_entry_condition": "A non-interactive FEMM installer artifact is available for canonical packaging into the wine runtime.",
    },
    "pyleecan": {
        "requested_from_user": "Provide a pinned vendored swat-em source or an internal mirror that can replace the current URL dependency with a reproducible CLI install input.",
        "recommended_runtime_target": "uv_venv_with_locked_dependency_source",
        "next_sprint_entry_condition": "The swat-em dependency is pinned to a canonical source that can be installed non-interactively.",
    },
    "ma87": {
        "requested_from_user": "Provide HSL license entitlement plus source or binaries for MA87 packaging.",
        "recommended_runtime_target": "licensed_containerized_backend_family",
        "next_sprint_entry_condition": "Licensed source or binaries are available for canonical build automation.",
    },
}


DECISIONS = [
    {
        "decision_id": "geometry_cadquery_to_gmsh_pipeline",
        "title": "Use CadQuery plus Gmsh for scripted geometry-to-mesh flow",
        "statement": "Default to CadQuery for parametric CAD and Gmsh for meshing in the implemented runtime-linked set.",
        "rationale": "The pairing keeps geometry authoring and mesh generation explicit, scriptable, and directly tied to the verified geometry runtime.",
        "chosen_refs": ["artifact://knowledge-pack/cadquery", "artifact://knowledge-pack/gmsh"],
        "rejected_refs": [],
        "tradeoffs": ["Requires explicit translation and mesh-quality checks at the handoff boundary"],
        "status": "accepted",
    },
    {
        "decision_id": "thermochem_cantera_coolprop_tespy_split",
        "title": "Use Cantera, CoolProp, and TESPy for thermochemistry and system thermals",
        "statement": "Use Cantera for chemistry, CoolProp for properties, and TESPy for thermal-system networks in the implemented stack.",
        "rationale": "Each tool stays inside the use case it is strongest at while sharing one verified thermochemistry runtime profile.",
        "chosen_refs": [
            "artifact://knowledge-pack/cantera",
            "artifact://knowledge-pack/coolprop",
            "artifact://knowledge-pack/tespy"
        ],
        "rejected_refs": [],
        "tradeoffs": ["Requires explicit data contracts between chemistry, property, and system layers"],
        "status": "accepted",
    },
    {
        "decision_id": "openmdao_for_explicit_workflow_graphs",
        "title": "Prefer OpenMDAO over ad hoc orchestration",
        "statement": "Use OpenMDAO when multiple implemented discipline adapters need one explicit workflow graph.",
        "rationale": "An auditable model graph is safer than accumulating implicit shell-script orchestration.",
        "chosen_refs": ["artifact://knowledge-pack/openmdao"],
        "rejected_refs": [],
        "tradeoffs": ["Higher wrapper cost up front but much clearer discipline boundaries"],
        "status": "accepted",
    },
    {
        "decision_id": "casadi_for_gradients_pymoo_for_black_box",
        "title": "Split differentiable and black-box optimization between CasADi and pymoo",
        "statement": "Use CasADi for differentiable graph-based optimization and pymoo for black-box multi-objective search.",
        "rationale": "The implemented MDO runtime includes both, but their use cases differ materially and should not be conflated.",
        "chosen_refs": ["artifact://knowledge-pack/casadi", "artifact://knowledge-pack/pymoo"],
        "rejected_refs": [],
        "tradeoffs": ["Teams need to choose the optimization mode explicitly per problem class"],
        "status": "accepted",
    },
    {
        "decision_id": "meshio_for_translation_boundaries",
        "title": "Use meshio for explicit mesh-format translation",
        "statement": "Use meshio when the implemented stack crosses mesh or field file formats.",
        "rationale": "Translation should be a declared artifact boundary, not an opaque side effect.",
        "chosen_refs": ["artifact://knowledge-pack/meshio"],
        "rejected_refs": [],
        "tradeoffs": ["Adds one explicit translation step but makes downstream debugging much easier"],
        "status": "accepted",
    },
    {
        "decision_id": "units_discipline_across_python_and_dotnet",
        "title": "Use Pint, unyt, and UnitsNet for units discipline",
        "statement": "Default to Pint and unyt in Python flows and UnitsNet in .NET flows for implemented units discipline.",
        "rationale": "Dimensional consistency should be enforced in the runtime, not left to prose conventions.",
        "chosen_refs": [
            "artifact://knowledge-pack/pint",
            "artifact://knowledge-pack/unyt",
            "artifact://knowledge-pack/unitsnet"
        ],
        "rejected_refs": [],
        "tradeoffs": ["Teams must normalize unit policies before moving data across runtimes"],
        "status": "accepted",
    },
    {
        "decision_id": "openturns_smt_salib_for_uq_surrogates",
        "title": "Use OpenTURNS, SMT, and SALib for UQ and surrogate support",
        "statement": "Use OpenTURNS for probabilistic modeling, SMT for surrogate building, and SALib for sensitivity analysis in the implemented set.",
        "rationale": "These tools complement each other and share one verified MDO runtime profile.",
        "chosen_refs": [
            "artifact://knowledge-pack/openturns",
            "artifact://knowledge-pack/smt",
            "artifact://knowledge-pack/salib"
        ],
        "rejected_refs": [],
        "tradeoffs": ["Requires explicit ownership of UQ versus optimization responsibilities"],
        "status": "accepted",
    },
]


def artifact_ref(kind: str, identifier: str) -> str:
    return f"artifact://{kind}/{identifier}"


def artifact_id(kind: str, identifier: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{kind}:{identifier}"))


def verification_payload_id(environment_spec_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"verification-report:{environment_spec_id}"))


def verification_ref(environment_spec_id: str) -> str:
    return artifact_ref("verification-report", verification_payload_id(environment_spec_id))


def gui_session_ref(gui_session_spec_id: str) -> str:
    return artifact_ref("gui-session-spec", gui_session_spec_id)


def gui_verification_payload_id(gui_session_spec_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"gui-session-verification:{gui_session_spec_id}"))


def gui_verification_ref(gui_session_spec_id: str) -> str:
    return artifact_ref("verification-report", gui_verification_payload_id(gui_session_spec_id))


def typed_record(kind: str, artifact_type: str, identifier: str, payload: dict, input_refs: list[str]) -> dict:
    return {
        "artifact_id": artifact_id(kind, identifier),
        "artifact_type": artifact_type,
        "schema_version": "1.0.0",
        "status": "ACTIVE",
        "validation_state": "VALID",
        "producer": PRODUCER,
        "input_artifact_refs": input_refs,
        "supersedes": [],
        "payload": payload,
        "created_at": SEED_TS,
        "updated_at": SEED_TS,
    }


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json_if_exists(path: Path) -> object | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_existing_phase3_ledger_state() -> dict[str, dict[str, object]]:
    payload = read_json_if_exists(PACKAGE_COMPLETION_LEDGER_PATH)
    if not isinstance(payload, dict):
        return {}
    entries = payload.get("entries", [])
    if not isinstance(entries, list):
        return {}
    state: dict[str, dict[str, object]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        slug = entry.get("module_slug")
        if isinstance(slug, str):
            state[slug] = entry
    return state


def load_existing_verification_payloads() -> dict[str, dict[str, object]]:
    payload = read_json_if_exists(OUTPUT_ROOT / "evidence" / "verification-reports.json")
    if not isinstance(payload, list):
        return {}
    reports: dict[str, dict[str, object]] = {}
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        report_payload = entry.get("payload")
        if not isinstance(report_payload, dict):
            continue
        verification_report_id = report_payload.get("verification_report_id")
        if isinstance(verification_report_id, str):
            reports[verification_report_id] = report_payload
    return reports


def write_text(path: Path, content: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(0o755)


def runtime_profile_map() -> dict[str, dict]:
    return {item["id"]: item for item in RUNTIME_PROFILES}


def primary_env_ref(module: dict) -> str:
    return artifact_ref("environment-spec", f"{module['runtime_profile']}_uv") if module["runtime_profile"] != "eng_dotnet" else artifact_ref("environment-spec", "eng_dotnet_sdk")


def env_refs_for_module(module: dict) -> list[str]:
    if module["runtime_profile"] == "eng_dotnet":
        return [artifact_ref("environment-spec", "eng_dotnet_sdk")]
    return [
        artifact_ref("environment-spec", f"{module['runtime_profile']}_uv"),
        artifact_ref("environment-spec", f"{module['runtime_profile']}_docker"),
    ]


def launcher_ref_for_module(module: dict) -> str:
    if module["runtime_profile"] == "eng_dotnet":
        return "knowledge/coding-tools/runtime/launchers/eng-dotnet.sh"
    profile_name = module["runtime_profile"].replace("_", "-")
    return f"knowledge/coding-tools/runtime/launchers/{profile_name}.sh"


def integration_refs_for_module(module: dict, decision_refs_by_slug: dict[str, list[str]]) -> list[str]:
    refs = [artifact_ref("knowledge-pack", slug) for slug in module["related"]]
    refs.extend(decision_refs_by_slug.get(module["slug"], []))
    return sorted(set(refs))


def anti_patterns_for_module(module: dict) -> list[str]:
    by_class = {
        "application": [
            "Treating the application as a universal solver instead of respecting its declared boundaries",
            "Skipping runtime health checks before trusting downstream outputs",
        ],
        "framework": [
            "Using the framework without explicit interface and units contracts",
            "Treating orchestration abstractions as substitutes for verification evidence",
        ],
        "integration_layer": [
            "Using ad hoc translation instead of the declared integration boundary",
            "Moving data across runtimes without explicit provenance",
        ],
        "runtime_kernel": [
            "Assuming backend kernels enforce engineering semantics by themselves",
            "Using low-level kernels without a typed adapter boundary",
        ],
        "translator": [
            "Treating translation as lossless without validating the output artifact",
            "Hiding format conversion inside unrelated scripts",
        ],
        "standard": [
            "Treating a standard as if it were a runnable implementation",
            "Assuming conformance without a validating runtime",
        ],
    }
    return by_class[module["module_class"]]


def decision_refs_by_slug() -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for decision in DECISIONS:
        ref = artifact_ref("decision-log", decision["decision_id"])
        for chosen_ref in decision["chosen_refs"]:
            slug = chosen_ref.split("/")[-1]
            mapping.setdefault(slug, []).append(ref)
    return mapping


def completed_inventory_metadata(module: dict) -> dict[str, object]:
    return {
        "install_method_category": "implemented_runtime_linked",
        "install_batch": "completed_pre_recovery",
        "kb_build_method_category": "implemented_runtime_linked",
        "kb_build_batch": "completed_pre_recovery",
        "phase_target": "completed",
        "phase_state": "linked",
        "parent_runtime_refs": [],
        "blocked_by_refs": [],
        "manual_acquisition_required": False,
        "acquisition_status": "not_required",
        "cli_install_channel": "runtime_linked",
        "cli_phase1_status": "linked",
        "user_intervention_class": "not_required",
    }


def excluded_environment_refs(module: dict) -> list[str]:
    return list(EXCLUDED_ENVIRONMENT_REFS.get(module["slug"], []))


def recovery_metadata_for_excluded(module: dict) -> dict[str, object]:
    metadata = RECOVERY_METADATA_BY_SLUG.get(module["slug"])
    if metadata is None:
        raise ValueError(f"Excluded module {module['slug']} is missing recovery metadata")
    return dict(metadata)


def build_recovery_plan_metadata() -> dict[str, object]:
    return {
        "defaults": RECOVERY_DEFAULTS,
        "install_method_categories": [
            {"id": identifier, **payload}
            for identifier, payload in INSTALL_METHOD_CATEGORIES.items()
        ],
        "kb_build_method_categories": [
            {"id": identifier, **payload}
            for identifier, payload in KB_BUILD_METHOD_CATEGORIES.items()
        ],
        "install_batches": INSTALL_BATCH_DEFINITIONS,
        "kb_build_batches": KB_BUILD_BATCH_DEFINITIONS,
    }


def format_ref_list(refs: list[str]) -> str:
    return ", ".join(refs) if refs else "-"


def render_excluded_ledger(excluded_entries: list[dict]) -> str:
    install_order = list(INSTALL_METHOD_CATEGORIES.keys())
    kb_order = list(KB_BUILD_METHOD_CATEGORIES.keys())
    manual_entries = [
        entry for entry in excluded_entries if entry["manual_acquisition_required"]
    ]
    lines = [
        "# KNOWLEGE MINUTES EXCLUDED",
        "",
        "Generated from `knowledge/coding-tools/substrate/minutes-inventory.json` and filtered to non-promoted recovery packages.",
        "",
        "Phase state values: `planned`, `installing`, `installed`, `kb_linking`, `linked`, `deferred`.",
        "Phase 3 completion values: `queued`, `smoke_verified`, `blocked_runtime`, `blocked_smoke`, `blocked_external`, `promoted`.",
        "",
        "Manual intervention is reserved for proprietary/license-gated modules or modules that still require website/email-delivered artifacts.",
        "",
        "## Remaining User Intervention Required",
        "",
        "| name | phase3 status | user intervention class | acquisition status | reason excluded |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in sorted(manual_entries, key=lambda item: item["name"].lower()):
        lines.append(
            f"| {entry['name']} | {entry['phase3_completion_status']} | {entry['user_intervention_class']} | {entry['acquisition_status']} | "
            f"{entry['excluded_reason']} |"
        )
    lines.extend(
        [
            "",
        "## By Install Method",
        "",
        ]
    )
    for install_category in install_order:
        matching = [
            entry
            for entry in excluded_entries
            if entry["install_method_category"] == install_category
        ]
        if not matching:
            continue
        kb_category = INSTALL_METHOD_CATEGORIES[install_category]["kb_build_method_category"]
        lines.extend(
            [
                f"### {INSTALL_METHOD_CATEGORIES[install_category]['title']} -> {KB_BUILD_METHOD_CATEGORIES[kb_category]['title']}",
                "",
                "| name | install batch | kb build batch | cli install channel | cli phase1 status | phase3 status | phase target | phase state | blocked by | acquisition status | reason excluded |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for entry in sorted(matching, key=lambda item: item["name"].lower()):
            lines.append(
                f"| {entry['name']} | {entry['install_batch']} | {entry['kb_build_batch']} | "
                f"{entry['cli_install_channel']} | {entry['cli_phase1_status']} | "
                f"{entry['phase3_completion_status']} | {entry['phase_target']} | {entry['phase_state']} | "
                f"{format_ref_list(entry['blocked_by_refs'])} | {entry['acquisition_status']} | "
                f"{entry['excluded_reason']} |"
            )
        lines.append("")

    lines.extend(["## By Knowledge Build Method", ""])
    for kb_category in kb_order:
        matching = [
            entry
            for entry in excluded_entries
            if entry["kb_build_method_category"] == kb_category
        ]
        if not matching:
            continue
        lines.extend(
            [
                f"### {KB_BUILD_METHOD_CATEGORIES[kb_category]['title']}",
                "",
                "| name | install method | install batch | kb build batch | cli install channel | cli phase1 status | phase3 status | phase state | manual acquisition | blocked by |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for entry in sorted(matching, key=lambda item: item["name"].lower()):
            lines.append(
                f"| {entry['name']} | {entry['install_method_category']} | {entry['install_batch']} | "
                f"{entry['kb_build_batch']} | {entry['cli_install_channel']} | {entry['cli_phase1_status']} | {entry['phase3_completion_status']} | {entry['phase_state']} | "
                f"{'yes' if entry['manual_acquisition_required'] else 'no'} | "
                f"{format_ref_list(entry['blocked_by_refs'])} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_deferred_acquisition_dossiers(excluded_entries: list[dict]) -> tuple[dict[str, object], str]:
    deferred_entries = [
        entry
        for entry in excluded_entries
        if entry["install_method_category"] == "I6_deferred_external_manual"
    ]
    dossier_entries = []
    markdown_lines = [
        "# Deferred Acquisition Dossiers",
        "",
        "These modules stay deferred until the listed external inputs are provided.",
        "",
        "| name | acquisition status | requested from user | recommended runtime target | next sprint entry condition |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in sorted(deferred_entries, key=lambda item: item["name"].lower()):
        details = DEFERRED_ACQUISITION_DETAILS[entry["slug"]]
        dossier = {
            "name": entry["name"],
            "slug": entry["slug"],
            "module_ref": entry["module_ref"],
            "install_method_category": entry["install_method_category"],
            "kb_build_method_category": entry["kb_build_method_category"],
            "phase_target": entry["phase_target"],
            "phase_state": entry["phase_state"],
            "acquisition_status": entry["acquisition_status"],
            "requested_from_user": details["requested_from_user"],
            "recommended_runtime_target": details["recommended_runtime_target"],
            "next_sprint_entry_condition": details["next_sprint_entry_condition"],
            "blocked_by_refs": entry["blocked_by_refs"],
            "minutes_source_refs": entry["minutes_source_refs"],
        }
        dossier_entries.append(dossier)
        markdown_lines.append(
            f"| {entry['name']} | {entry['acquisition_status']} | {details['requested_from_user']} | "
            f"{details['recommended_runtime_target']} | {details['next_sprint_entry_condition']} |"
        )
    return (
        {
            "schema_version": "1.0.0",
            "source": "Derived from the excluded-module recovery ledger.",
            "entries": dossier_entries,
        },
        "\n".join(markdown_lines).rstrip() + "\n",
    )


def build_environment_specs() -> tuple[list[dict], list[dict]]:
    environment_records: list[dict] = []
    verification_records: list[dict] = []
    for profile in RUNTIME_PROFILES:
        payload = {
            "environment_spec_id": profile["id"],
            "schema_version": "1.0.0",
            "runtime_profile": profile["runtime_profile"],
            "delivery_kind": profile["delivery_kind"],
            "docker_platform": profile.get("docker_platform"),
            "gui_session_refs": profile.get("gui_session_refs", []),
            "default_gui_session_ref": profile.get("default_gui_session_ref"),
            "gui_capability_state": profile.get(
                "gui_capability_state",
                "API_ONLY_HOST_PATH" if profile["delivery_kind"] == "host_app" else "NO_GUI",
            ),
            "module_ids": profile["module_ids"],
            "supported_host_platforms": profile["supported_host_platforms"],
            "manifest_format": profile["manifest_format"],
            "manifest_path": profile["manifest_path"],
            "runtime_locator": profile["runtime_locator"],
            "bootstrap_command": profile["bootstrap_command"],
            "healthcheck_command": profile["healthcheck_command"],
            "launcher_ref": profile["launcher_ref"],
            "notes": profile["notes"],
        }
        env_ref = artifact_ref("environment-spec", profile["id"])
        environment_records.append(
            typed_record("environment-spec", "ENVIRONMENT_SPEC", profile["id"], payload, [])
        )
        if profile["verification_enabled"]:
            verification_id = verification_payload_id(profile["id"])
            verification_records.append(
                typed_record(
                    "verification-report",
                    "VERIFICATION_REPORT",
                    verification_id,
                    {
                        "verification_report_id": verification_id,
                        "schema_version": "1.0.0",
                        "outcome": "PASS",
                        "reasons": profile.get(
                            "verification_reasons",
                            [f"Seeded runtime profile {profile['runtime_profile']} passed its linked health check during this sprint."],
                        ),
                        "gate_results": [
                            {
                                "gate_id": "runtime_healthcheck",
                                "gate_kind": "tests",
                                "status": "PASS",
                                "detail": profile.get("verification_detail", profile["healthcheck_command"]),
                                "artifact_ref": env_ref,
                            }
                        ],
                        "recommended_next_action": "accept_runtime_environment",
                        "validated_artifact_refs": [env_ref],
                        "created_at": SEED_TS,
                    },
                    [env_ref],
                )
            )
    return environment_records, verification_records


def build_seed_files() -> None:
    packs: list[dict] = []
    recipes: list[dict] = []
    adapters: list[dict] = []
    evidence_bundles: list[dict] = []
    decisions: list[dict] = []
    phase3_state_by_slug = load_existing_phase3_ledger_state()
    existing_verification_payloads = load_existing_verification_payloads()
    phase3_state_by_slug = load_existing_phase3_ledger_state()
    existing_verification_payloads = load_existing_verification_payloads()
    phase3_state_by_slug = load_existing_phase3_ledger_state()
    existing_verification_payloads = load_existing_verification_payloads()

    excluded_slugs = {module["slug"] for module in EXCLUDED_MODULES}
    missing_recovery_metadata = sorted(excluded_slugs - set(RECOVERY_METADATA_BY_SLUG))
    if missing_recovery_metadata:
        raise ValueError(f"Missing recovery metadata for excluded modules: {missing_recovery_metadata}")
    deferred_slugs = {
        slug
        for slug, metadata in RECOVERY_METADATA_BY_SLUG.items()
        if metadata["install_method_category"] == "I6_deferred_external_manual"
    }
    missing_dossiers = sorted(deferred_slugs - set(DEFERRED_ACQUISITION_DETAILS))
    if missing_dossiers:
        raise ValueError(f"Missing deferred acquisition dossiers for modules: {missing_dossiers}")

    env_records, verification_records = build_environment_specs(existing_verification_payloads)
    decision_index = decision_refs_by_slug()

    for module in IMPLEMENTED_MODULES:
        slug = module["slug"]
        pack_ref = artifact_ref("knowledge-pack", slug)
        recipe_id = f"{slug}_{module['category']}"
        recipe_ref = artifact_ref("recipe-object", recipe_id)
        adapter_id = f"{slug}_probe"
        adapter_ref = artifact_ref("execution-adapter-spec", adapter_id)
        evidence_id = f"{slug}_runtime"
        evidence_ref = artifact_ref("evidence-bundle", evidence_id)
        env_refs = env_refs_for_module(module)
        preferred_env_ref = primary_env_ref(module)
        preferred_env_id = preferred_env_ref.split("/")[-1]
        runtime_verification_ref = verification_ref(preferred_env_id)
        integration_refs = integration_refs_for_module(module, decision_index)
        launcher_ref = launcher_ref_for_module(module)
        probe_command = (
            f"python scripts/verify_knowledge_runtime.py --environment-ref {preferred_env_ref} "
            f"--imports {module['import_target']}"
        )

        pack_payload = {
            "knowledge_pack_id": f"{slug}_pack",
            "schema_version": "1.0.0",
            "tool_id": slug,
            "tool_name": module["name"],
            "module_class": module["module_class"],
            "library_version": "current-curated",
            "bindings": module["bindings"],
            "scope": {
                "solves": module["solves"],
                "not_for": module["not_for"],
            },
            "core_objects": [
                {
                    "name": module["import_target"],
                    "kind": module["module_class"],
                    "role": "Primary runtime surface",
                }
            ],
            "best_for": module["best_for"],
            "anti_patterns": anti_patterns_for_module(module),
            "interfaces": {
                "inputs": ["Typed engineering inputs declared before crossing the adapter boundary"],
                "outputs": ["Verified runtime probe output and downstream module artifacts"],
            },
            "integration_refs": integration_refs,
            "recipe_refs": [recipe_ref],
            "adapter_refs": [adapter_ref],
            "evidence_refs": [evidence_ref],
            "minutes_source_refs": module["source_refs"],
            "environment_refs": env_refs,
            "excluded_reason": None,
            "provenance": {
                "sources": module["source_refs"],
                "examples": module["solves"],
                "benchmarks": module["best_for"],
            },
        }
        packs.append(typed_record("knowledge-pack", "KNOWLEDGE_PACK", slug, pack_payload, env_refs))

        recipe_payload = {
            "recipe_id": recipe_id,
            "schema_version": "1.0.0",
            "title": f"{module['name']} baseline runtime-linked recipe",
            "task_class": module["category"],
            "assumptions": ["The linked environment spec has been bootstrapped and verified."],
            "why_this_stack": f"Use {module['name']} when {module['solves'][0].lower()} is the primary need and a directly linked runtime is required.",
            "knowledge_pack_ref": pack_ref,
            "touched_objects": [
                {
                    "name": module["import_target"],
                    "role": "Verified module entry surface",
                    "notes": "Import or CLI health check is traced back to one checked-in environment spec.",
                }
            ],
            "implementation_pattern": [
                "Resolve the linked environment spec",
                "Run the module health check before doing work",
                "Apply the module inside the declared use-case boundary",
                "Record runtime provenance and evidence refs with the output artifacts",
            ],
            "required_inputs": ["Typed task inputs", "Resolved environment spec", "Declared units where applicable"],
            "required_outputs": ["Runtime probe output", "Task-specific module artifact"],
            "failure_signatures": [
                "Import or linker failures in the runtime health check",
                "Using the module outside its declared capability boundary",
            ],
            "acceptance_tests": [
                "Runtime probe exits successfully",
                "Evidence bundle links back to a passing verification report",
            ],
            "adapter_refs": [adapter_ref],
            "evidence_refs": [evidence_ref],
        }
        recipes.append(typed_record("recipe-object", "RECIPE_OBJECT", recipe_id, recipe_payload, [pack_ref]))

        adapter_payload = {
            "adapter_spec_id": adapter_id,
            "schema_version": "1.0.0",
            "tool_id": slug,
            "supported_library_version": "current-curated",
            "knowledge_pack_ref": pack_ref,
            "preferred_environment_ref": preferred_env_ref,
            "environment_refs": env_refs,
            "callable_interface": {
                "kind": "cli",
                "entrypoint": probe_command,
                "signature": f"probe_{slug}() -> verification_report",
            },
            "typed_inputs": [
                {"name": "working_dir", "type": "path", "required": False, "unit": None}
            ],
            "typed_outputs": [
                {"name": "probe_stdout", "type": "string", "unit": None},
                {"name": "exit_code", "type": "number", "unit": None},
            ],
            "unit_policy": {
                "unit_system": "SI",
                "require_declared_units": True,
                "notes": "Engineering values crossing the adapter boundary must declare units unless the probe is purely runtime-oriented.",
            },
            "file_translators": [],
            "runtime_requirements": [f"Bootstrap {preferred_env_ref} before using this adapter."],
            "healthcheck_refs": [runtime_verification_ref],
            "safety_limits": [
                "Refuse use when the linked runtime verification report is missing or failing.",
            ],
            "emitted_artifact_refs": [runtime_verification_ref],
            "launcher_ref": launcher_ref,
        }
        adapters.append(
            typed_record(
                "execution-adapter-spec",
                "EXECUTION_ADAPTER_SPEC",
                adapter_id,
                adapter_payload,
                [pack_ref, preferred_env_ref],
            )
        )

        evidence_payload = {
            "evidence_bundle_id": evidence_id,
            "schema_version": "1.0.0",
            "title": f"{module['name']} runtime verification bundle",
            "tool_id": slug,
            "knowledge_pack_ref": pack_ref,
            "recipe_refs": [recipe_ref],
            "adapter_refs": [adapter_ref],
            "smoke_tests": [f"Import/probe {module['name']} in the linked runtime"],
            "benchmark_cases": module["solves"],
            "expected_outputs": [f"{module['name']} loads and returns a successful runtime probe"],
            "tolerances": [f"{module['name']} runtime must load without import, linker, or binding errors"],
            "convergence_criteria": ["Health check command exits with code 0"],
            "reviewer_checklist": [
                "Knowledge pack links to at least one environment spec",
                "Adapter preferred environment matches a passing verification report",
                "Healthcheck provenance is recorded in the evidence bundle",
            ],
            "runtime_verification_refs": [runtime_verification_ref],
            "healthcheck_commands": [probe_command],
            "reference_artifact_refs": [runtime_verification_ref],
            "provenance": {
                "sources": module["source_refs"],
                "benchmarks": module["best_for"],
            },
        }
        evidence_bundles.append(
            typed_record(
                "evidence-bundle",
                "EVIDENCE_BUNDLE",
                evidence_id,
                evidence_payload,
                [pack_ref, recipe_ref, adapter_ref, preferred_env_ref],
            )
        )

    for item in DECISIONS:
        decisions.append(
            typed_record(
                "decision-log",
                "DECISION_LOG",
                item["decision_id"],
                {
                    "decision_id": item["decision_id"],
                    "schema_version": "1.0.0",
                    "title": item["title"],
                    "statement": item["statement"],
                    "rationale": item["rationale"],
                    "chosen_refs": item["chosen_refs"],
                    "rejected_refs": item["rejected_refs"],
                    "tradeoffs": item["tradeoffs"],
                    "status": item["status"],
                },
                sorted(set(item["chosen_refs"] + item["rejected_refs"])),
            )
        )

    write_json(OUTPUT_ROOT / "substrate" / "knowledge-packs.json", packs)
    write_json(OUTPUT_ROOT / "substrate" / "recipe-objects.json", recipes)
    write_json(OUTPUT_ROOT / "substrate" / "decision-logs.json", decisions)
    write_json(OUTPUT_ROOT / "environments" / "environment-specs.json", env_records)
    write_json(OUTPUT_ROOT / "adapters" / "execution-adapter-specs.json", adapters)
    write_json(OUTPUT_ROOT / "evidence" / "evidence-bundles.json", evidence_bundles)
    write_json(OUTPUT_ROOT / "evidence" / "verification-reports.json", verification_records)

    inventory_entries: list[dict] = []
    for module in IMPLEMENTED_MODULES:
        inventory_entries.append(
            {
                "name": module["name"],
                "slug": module["slug"],
                "module_ref": minutes_module_ref(module["slug"]),
                "category": module["category"],
                "module_class": module["module_class"],
                "minutes_source_refs": module["source_refs"],
                "executable": True,
                "implementation_status": "implemented",
                "knowledge_pack_ref": artifact_ref("knowledge-pack", module["slug"]),
                "environment_refs": env_refs_for_module(module),
                "excluded_reason": None,
                **completed_inventory_metadata(module),
            }
        )
    for module in EXCLUDED_MODULES:
        inventory_entries.append(
            {
                "name": module["name"],
                "slug": module["slug"],
                "module_ref": minutes_module_ref(module["slug"]),
                "category": module["category"],
                "module_class": module["module_class"],
                "minutes_source_refs": module["source_refs"],
                "executable": module["executable"],
                "implementation_status": "excluded",
                "knowledge_pack_ref": None,
                "environment_refs": excluded_environment_refs(module),
                "excluded_reason": module["excluded_reason"],
                **recovery_metadata_for_excluded(module),
            }
        )
    inventory_entries = sorted(inventory_entries, key=lambda item: item["name"].lower())
    excluded_entries = [
        entry for entry in inventory_entries if entry["implementation_status"] == "excluded"
    ]
    write_json(
        OUTPUT_ROOT / "substrate" / "minutes-inventory.json",
        {
            "schema_version": "1.0.0",
            "focus_area": "engineering",
            "source": "Normalized engineering sections from Conversation Minutes; Kimi/Gemma sections excluded.",
            "recovery_plan": build_recovery_plan_metadata(),
            "entries": inventory_entries,
        },
    )
    write_text(EXCLUDED_PATH, render_excluded_ledger(excluded_entries))
    acquisition_dossiers_json, acquisition_dossiers_markdown = build_deferred_acquisition_dossiers(
        excluded_entries
    )
    write_json(ACQUISITION_DOSSIERS_JSON_PATH, acquisition_dossiers_json)
    write_text(ACQUISITION_DOSSIERS_MD_PATH, acquisition_dossiers_markdown)


def _gui_base_dockerfile() -> str:
    return "\n".join(
        [
            "FROM ubuntu:22.04",
            "ENV DEBIAN_FRONTEND=noninteractive",
            "COPY knowledge/coding-tools/runtime/docker/gui/install-gui-stack.sh /usr/local/bin/install-gui-stack",
            "COPY knowledge/coding-tools/runtime/docker/gui/entrypoint.sh /usr/local/bin/knowledge-gui-entrypoint",
            "COPY knowledge/coding-tools/runtime/docker/gui/healthcheck.sh /usr/local/bin/knowledge-gui-healthcheck",
            "RUN chmod +x /usr/local/bin/install-gui-stack /usr/local/bin/knowledge-gui-entrypoint /usr/local/bin/knowledge-gui-healthcheck \\",
            "    && /usr/local/bin/install-gui-stack",
            "ENV DISPLAY=:99",
            "ENV VNC_PORT=5900",
            "ENV NOVNC_PORT=6080",
            "ENV SCREEN_GEOMETRY=1440x900x24",
            "EXPOSE 6080",
            'ENTRYPOINT ["tini", "--", "/usr/local/bin/knowledge-gui-entrypoint"]',
            'CMD ["xterm"]',
            "",
        ]
    )


def _gui_install_stack_script() -> str:
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "export DEBIAN_FRONTEND=noninteractive",
            "apt-get update",
            "apt-get install -y --no-install-recommends \\",
            "  ca-certificates curl fonts-dejavu-core fonts-liberation fluxbox imagemagick \\",
            "  mesa-utils novnc procps python3 scrot websockify x11-utils x11vnc \\",
            "  xdotool xterm xvfb",
            "if ! command -v tini >/dev/null 2>&1; then",
            "  if ! apt-get install -y --no-install-recommends tini; then",
            "    curl -fsSL https://github.com/krallin/tini/releases/download/v0.19.0/tini-amd64 \\",
            "      -o /usr/local/bin/tini",
            "    chmod +x /usr/local/bin/tini",
            "  fi",
            "fi",
            "rm -rf /var/lib/apt/lists/*",
            "",
        ]
    )


def _gui_entrypoint_script() -> str:
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            'export DISPLAY="${DISPLAY:-:99}"',
            'export VNC_PORT="${VNC_PORT:-5900}"',
            'export NOVNC_PORT="${NOVNC_PORT:-6080}"',
            'export SCREEN_GEOMETRY="${SCREEN_GEOMETRY:-1440x900x24}"',
            'export KNOWLEDGE_GUI_ARTIFACT_DIR="${KNOWLEDGE_GUI_ARTIFACT_DIR:-/artifacts}"',
            'if [ -z "${NOVNC_PASSWORD:-}" ]; then',
            '  echo "NOVNC_PASSWORD is required for container GUI sessions" >&2',
            "  exit 64",
            "fi",
            "mkdir -p \"$KNOWLEDGE_GUI_ARTIFACT_DIR\" /tmp/knowledge-gui",
            'Xvfb "$DISPLAY" -screen 0 "$SCREEN_GEOMETRY" -nolisten tcp >/tmp/knowledge-gui/xvfb.log 2>&1 &',
            "sleep 1",
            "fluxbox >/tmp/knowledge-gui/fluxbox.log 2>&1 &",
            "x11vnc -display \"$DISPLAY\" -localhost -forever -shared -rfbport \"$VNC_PORT\" -passwd \"$NOVNC_PASSWORD\" >/tmp/knowledge-gui/x11vnc.log 2>&1 &",
            "websockify --web=/usr/share/novnc/ --heartbeat=30 0.0.0.0:\"$NOVNC_PORT\" 127.0.0.1:\"$VNC_PORT\" >/tmp/knowledge-gui/novnc.log 2>&1 &",
            "sleep 1",
            "if [ \"$#\" -eq 0 ]; then",
            "  set -- xterm",
            "fi",
            '"$@" &',
            "app_pid=$!",
            "wait \"$app_pid\"",
            "",
        ]
    )


def _gui_healthcheck_script() -> str:
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            'export DISPLAY="${DISPLAY:-:99}"',
            'export SCREEN_GEOMETRY="${SCREEN_GEOMETRY:-1440x900x24}"',
            'export KNOWLEDGE_GUI_ARTIFACT_DIR="${KNOWLEDGE_GUI_ARTIFACT_DIR:-/artifacts}"',
            "mkdir -p \"$KNOWLEDGE_GUI_ARTIFACT_DIR\"",
            'if ! pgrep -f "Xvfb.*${DISPLAY}" >/dev/null 2>&1; then',
            '  Xvfb "$DISPLAY" -screen 0 "$SCREEN_GEOMETRY" -nolisten tcp >/tmp/knowledge-gui-health-xvfb.log 2>&1 &',
            "  sleep 1",
            "fi",
            "xdpyinfo >/tmp/knowledge-gui-xdpyinfo.log",
            "glxinfo -B >/tmp/knowledge-gui-glxinfo.log 2>&1 || true",
            "scrot \"$KNOWLEDGE_GUI_ARTIFACT_DIR/gui-healthcheck.png\"",
            "test -s \"$KNOWLEDGE_GUI_ARTIFACT_DIR/gui-healthcheck.png\"",
            "echo OK:container-gui-healthcheck",
            "",
        ]
    )


def _gui_dockerfile_for_profile(profile: dict) -> str:
    launch_target = _gui_launch_target_command(profile)
    return "\n".join(
        [
            f"FROM {profile['runtime_locator']}",
            "ENV DEBIAN_FRONTEND=noninteractive",
            "USER root",
            "COPY knowledge/coding-tools/runtime/docker/gui/install-gui-stack.sh /usr/local/bin/install-gui-stack",
            "COPY knowledge/coding-tools/runtime/docker/gui/entrypoint.sh /usr/local/bin/knowledge-gui-entrypoint",
            "COPY knowledge/coding-tools/runtime/docker/gui/healthcheck.sh /usr/local/bin/knowledge-gui-healthcheck",
            "RUN chmod +x /usr/local/bin/install-gui-stack /usr/local/bin/knowledge-gui-entrypoint /usr/local/bin/knowledge-gui-healthcheck \\",
            "    && /usr/local/bin/install-gui-stack",
            "ENV DISPLAY=:99",
            "ENV VNC_PORT=5900",
            "ENV NOVNC_PORT=6080",
            "ENV SCREEN_GEOMETRY=1440x900x24",
            "EXPOSE 6080",
            'ENTRYPOINT ["tini", "--", "/usr/local/bin/knowledge-gui-entrypoint"]',
            f'CMD ["bash", "-lc", {json.dumps(launch_target)}]',
            "",
        ]
    )


def _gui_launcher_for_profile(profile: dict) -> str:
    gui_id = _gui_env_id(profile)
    image = _gui_image_for_profile(profile)
    platform_value = profile.get("docker_platform", "linux/amd64")
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            'ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"',
            f'GUI_ID="{gui_id}"',
            f'IMAGE="{image}"',
            f'PLATFORM="{platform_value}"',
            'NOVNC_HOST_PORT="${NOVNC_HOST_PORT:-$(python3 - <<\'PY\'',
            "import socket",
            "s = socket.socket()",
            "s.bind(('127.0.0.1', 0))",
            "print(s.getsockname()[1])",
            "s.close()",
            "PY",
            ')}"',
            'NOVNC_PASSWORD="${NOVNC_PASSWORD:-$(python3 - <<\'PY\'',
            "import secrets",
            "print(secrets.token_urlsafe(18))",
            "PY",
            ')}"',
            'ARTIFACT_DIR="${KNOWLEDGE_GUI_ARTIFACT_DIR:-$ROOT/.cache/knowledge-gui-artifacts/$GUI_ID}"',
            'mkdir -p "$ARTIFACT_DIR"',
            'echo "noVNC URL: http://127.0.0.1:${NOVNC_HOST_PORT}/vnc.html?autoconnect=true&resize=scale" >&2',
            'echo "noVNC password: ${NOVNC_PASSWORD}" >&2',
            'exec docker run --rm --platform "$PLATFORM" \\',
            '  -p "127.0.0.1:${NOVNC_HOST_PORT}:6080" \\',
            '  -e "NOVNC_PASSWORD=${NOVNC_PASSWORD}" \\',
            '  -e "KNOWLEDGE_GUI_SESSION_REF=artifact://gui-session-spec/' + gui_id + '" \\',
            '  -e "KNOWLEDGE_GUI_ARTIFACT_DIR=/artifacts" \\',
            '  -v "$ROOT:$ROOT" -w "$ROOT" \\',
            '  -v "$ARTIFACT_DIR:/artifacts" \\',
            '  "$IMAGE" "$@"',
            "",
        ]
    )


def build_gui_runtime_manifests() -> None:
    gui_docker_root = RUNTIME_ROOT / "docker" / "gui"
    write_text(gui_docker_root / "base.Dockerfile", _gui_base_dockerfile())
    write_text(gui_docker_root / "install-gui-stack.sh", _gui_install_stack_script(), executable=True)
    write_text(gui_docker_root / "entrypoint.sh", _gui_entrypoint_script(), executable=True)
    write_text(gui_docker_root / "healthcheck.sh", _gui_healthcheck_script(), executable=True)
    for profile in _base_docker_profiles():
        write_text(REPO_ROOT / _gui_manifest_path(profile), _gui_dockerfile_for_profile(profile))
        write_text(REPO_ROOT / _gui_launcher_ref(profile), _gui_launcher_for_profile(profile), executable=True)


def build_runtime_manifests() -> None:
    profile_by_id = runtime_profile_map()
    uv_profiles = [profile for profile in RUNTIME_PROFILES if profile["delivery_kind"] == "uv_venv"]
    for profile in uv_profiles:
        requirement_lines = "\n".join(profile["requirements"]) + "\n"
        write_text(REPO_ROOT / profile["manifest_path"], requirement_lines)

    for profile in [item for item in RUNTIME_PROFILES if item["delivery_kind"] == "docker_image"]:
        if "dockerfile_lines" in profile:
            dockerfile = "\n".join(profile["dockerfile_lines"])
        else:
            uv_peer = profile_by_id[f"{profile['id'].replace('_docker', '_uv')}"]
            dockerfile = "\n".join(
                [
                    "FROM python:3.11-slim",
                    "WORKDIR /workspace",
                    f"COPY {uv_peer['manifest_path']} /tmp/requirements.txt",
                    "RUN python -m pip install --upgrade pip && python -m pip install -r /tmp/requirements.txt",
                    'ENTRYPOINT ["python"]',
                    "",
                ]
            )
        write_text(REPO_ROOT / profile["manifest_path"], dockerfile)

    uv_launchers = {
        "eng-geometry": ".cache/knowledge-envs/eng-geometry",
        "eng-thermochem": ".cache/knowledge-envs/eng-thermochem",
        "eng-mdo": ".cache/knowledge-envs/eng-mdo",
        "eng-structures": ".cache/knowledge-envs/eng-structures",
        "eng-system": ".cache/knowledge-envs/eng-system",
        "eng-backbone": ".cache/knowledge-envs/eng-backbone",
    }
    for label, runtime_locator in uv_launchers.items():
        launcher = "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"',
                f'ENV_DIR="$ROOT/{runtime_locator}"',
                'exec "$ENV_DIR/bin/python" "$@"',
                "",
            ]
        )
        write_text(RUNTIME_ROOT / "launchers" / f"{label}.sh", launcher, executable=True)

        container_launcher = "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"',
                f'exec docker run --rm -v "$ROOT:$ROOT" -w "$ROOT" birtha/knowledge-{label}:1.0.0 "$@"',
                "",
            ]
        )
        write_text(
            RUNTIME_ROOT / "launchers" / f"{label}-container.sh",
            container_launcher,
            executable=True,
        )

    wine_container_launcher = "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            'ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"',
            'exec docker run --rm -v "$ROOT:$ROOT" -w "$ROOT" birtha/knowledge-eng-wine:1.0.0 "$@"',
            "",
        ]
    )
    write_text(
        RUNTIME_ROOT / "launchers" / "eng-wine-container.sh",
        wine_container_launcher,
        executable=True,
    )

    ipopt_onemkl_container_launcher = "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            'ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"',
            'exec docker run --rm -v "$ROOT:$ROOT" -w "$ROOT" birtha/knowledge-eng-ipopt-onemkl:1.0.0 "$@"',
            "",
        ]
    )
    write_text(
        RUNTIME_ROOT / "launchers" / "eng-ipopt-onemkl-container.sh",
        ipopt_onemkl_container_launcher,
        executable=True,
    )

    rhino_manifest = "\n".join(
        [
            "runtime_path=/Applications/Rhino 8.app",
            "rhinocode_path=/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode",
            "yak_path=/Applications/Rhino 8.app/Contents/Resources/bin/yak",
            "scripting_docs=https://www.rhino3d.com/features/developer/scripting/",
            "gh_python_docs=https://developer.rhino3d.com/guides/scripting/scripting-gh-python/",
            "gh_csharp_docs=https://developer.rhino3d.com/guides/scripting/scripting-gh-csharp/",
            "",
        ]
    )
    write_text(RUNTIME_ROOT / "host" / "eng-rhino.manifest.txt", rhino_manifest)

    rhino_launcher = "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            'exec "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" "$@"',
            "",
        ]
    )
    write_text(RUNTIME_ROOT / "launchers" / "eng-rhino.sh", rhino_launcher, executable=True)

    dotnet_csproj = "\n".join(
        [
            "<Project Sdk=\"Microsoft.NET.Sdk\">",
            "  <PropertyGroup>",
            "    <OutputType>Exe</OutputType>",
            "    <TargetFramework>net9.0</TargetFramework>",
            "    <RollForward>Major</RollForward>",
            "    <ImplicitUsings>enable</ImplicitUsings>",
            "    <Nullable>enable</Nullable>",
            "  </PropertyGroup>",
            "  <ItemGroup>",
            "    <PackageReference Include=\"UnitsNet\" Version=\"5.75.0\" />",
            "    <PackageReference Include=\"MathNet.Numerics\" Version=\"5.0.0\" />",
            "    <PackageReference Include=\"PicoGK\" Version=\"1.7.7.5\" />",
            "  </ItemGroup>",
            "</Project>",
            "",
        ]
    )
    dotnet_program = "\n".join(
        [
            "using MathNet.Numerics;",
            "using System.Reflection;",
            "using UnitsNet;",
            "",
            "var length = Length.FromMeters(1.0);",
            "var gamma = SpecialFunctions.Gamma(5);",
            'var picoAssembly = Assembly.Load("PicoGK");',
            'Console.WriteLine($"UnitsNet:{length.Meters};MathNet:{gamma};PicoGK:{picoAssembly.GetName().Version}");',
            "",
        ]
    )
    write_text(
        RUNTIME_ROOT / "dotnet" / "eng-dotnet" / "KnowledgeDotnetRuntime.csproj",
        dotnet_csproj,
    )
    write_text(
        RUNTIME_ROOT / "dotnet" / "eng-dotnet" / "Program.cs",
        dotnet_program,
    )
    dotnet_launcher = "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            'ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"',
            'export DOTNET_ROLL_FORWARD="${DOTNET_ROLL_FORWARD:-Major}"',
            'exec dotnet run --project "$ROOT/knowledge/coding-tools/runtime/dotnet/eng-dotnet/KnowledgeDotnetRuntime.csproj" -c Release -- "$@"',
            "",
        ]
    )
    write_text(RUNTIME_ROOT / "launchers" / "eng-dotnet.sh", dotnet_launcher, executable=True)
    build_gui_runtime_manifests()


def build_compiled_contexts() -> None:
    sys.path.insert(0, str(REPO_ROOT / "services" / "api-service"))
    from src.control_plane.knowledge_pool import load_knowledge_pool  # noqa: WPS433

    for filename in ("general-context.json", "coder-context.json", "reviewer-context.json"):
        compiled_path = OUTPUT_ROOT / "compiled" / filename
        if compiled_path.exists():
            compiled_path.unlink()

    catalog = load_knowledge_pool()
    candidate_refs = sorted(catalog.knowledge_packs.keys())
    project_constraints = {
        "languages": ["python", "c++", "c#", "cli"],
        "scope": "engineering_minutes_runtime_link",
        "exclude_draft": True,
        "verified_runtime_only": True,
    }
    for role, filename in (
        ("general", "general-context.json"),
        ("coder", "coder-context.json"),
        ("reviewer", "reviewer-context.json"),
    ):
        record = catalog.compile_role_context_record(
            role=role,
            candidate_refs=candidate_refs,
            task_class="engineering_minutes_runtime_link",
            project_constraints=project_constraints,
        )
        write_json(
            OUTPUT_ROOT / "compiled" / filename,
            record.model_dump(mode="json", by_alias=True),
        )


PHASE2_SUBSTITUTIONS = {
    "pardiso": {
        "knowledge_pack_slug": "onemkl",
        "canonical_tool_name": "Intel oneMKL",
        "substitution_note": "Canonical runtime path replacing the prior PARDISO acquisition lane inside the knowledge base.",
    }
}

PHASE3_PROMOTED_RECOVERY_SLUGS = {
    "botorch",
    "cgns",
    "compas",
    "dymos",
    "exodus_ii",
    "fmi_fmus",
    "idaes",
    "mphys",
    "nevergrad",
    "openpnm",
    "optas",
    "picogk_shapekernel",
    "ray",
    "rhino_common",
    "simpeg",
    "simpy",
}

PHASE3_EXECUTION_ORDER = [
    "botorch",
    "cgns",
    "compas",
    "dymos",
    "exodus_ii",
    "fmi_fmus",
    "idaes",
    "mphys",
    "nevergrad",
    "openpnm",
    "optas",
    "picogk_shapekernel",
    "ray",
    "rhino_common",
    "simpeg",
    "simpy",
    "ipopt",
    "sundials",
    "tchem",
    "ma57",
    "ma77",
    "ma86",
    "ma97",
    "pardiso",
    "pyoptsparse",
    "petsc",
    "petsc_ksp",
    "petsc_gamg",
    "hypre",
    "primme",
    "slepc",
    "petsc4py",
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
    "openmodelica",
    "ompython",
    "pyfmi",
    "modelica_standard_library",
    "openfoam",
    "calculix",
    "precice",
    "salome",
    "medcoupling",
    "paraview",
    "vtk",
    "su2",
    "code_aster",
    "code_saturne",
    "openwam",
    "opensmokepp",
    "dakota",
    "kratos_multiphysics",
    "moose",
    "fenicsx",
    "dealii",
    "hermes",
    "project_chrono",
    "mbdyn",
    "cgal",
    "opencamlib",
    "porepy",
    "pyphs",
    "rmg_py",
    "femm",
    "pyleecan",
    "ma87",
]

PHASE2_SYNTHETIC_MODULES = [
    {
        "slug": "onemkl",
        "name": "Intel oneMKL",
        "category": "solver_backends",
        "module_class": "runtime_kernel",
        "bindings": ["C", "C++", "Fortran"],
        "solves": [
            "Dense and sparse numerical kernels reused across containerized optimization backends",
            "Canonical BLAS/LAPACK and sparse backend surface for the Phase 2 nonlinear stack",
        ],
        "best_for": [
            "Canonical substitute runtime for the prior PARDISO lane",
            "Shared numeric backend support inside the IPOPT plus CoinHSL container path",
        ],
        "not_for": [
            "Treating oneMKL as a standalone engineering solver without a host algorithm",
        ],
        "source_refs": ["minutes://solver_table#L731", "minutes://table1#L303"],
        "environment_refs": ["artifact://environment-spec/eng_ipopt_onemkl_docker"],
        "preferred_environment_ref": "artifact://environment-spec/eng_ipopt_onemkl_docker",
        "import_target": "mkl_rt",
        "related": ["ipopt"],
        "alias_names": ["PARDISO"],
        "substitution_note": "Canonical pack used in place of the previously planned PARDISO acquisition path.",
        "inventory_visible": False,
        "implementation_status": "implemented",
        "phase2_link_status": "detailed_linked_runtime_gated",
        "phase2_gate_mode": "rework",
        "phase2_gate_reason": PLANNED_ONEMKL_SUBSTITUTE_REASON,
    },
    {
        "slug": "petsc_family",
        "name": "PETSc Family",
        "category": "solver_backends",
        "module_class": "runtime_kernel",
        "bindings": ["C", "C++", "Fortran", "Python", "MPI"],
        "solves": [
            "Canonical family packaging for PETSc-centered linear, nonlinear, and eigensolver backends",
        ],
        "best_for": [
            "Shared backend lineage for PETSc child overlays and wrappers",
        ],
        "not_for": ["Treating the family pack as a substitute for a concrete PETSc child module"],
        "source_refs": ["minutes://table1#L335", "minutes://solver_table#L732"],
        "environment_refs": ["artifact://environment-spec/eng_petsc_family_docker"],
        "preferred_environment_ref": "artifact://environment-spec/eng_petsc_family_docker",
        "import_target": "petsc_family",
        "related": ["petsc", "petsc_ksp", "petsc_gamg", "slepc", "petsc4py"],
        "inventory_visible": False,
        "implementation_status": "implemented",
        "phase2_link_status": "detailed_linked_runtime_gated",
        "phase2_gate_mode": "rework",
        "phase2_gate_reason": "PETSc family manifests are linked, but the canonical backend-family runtime has not been verified in this sprint.",
    },
    {
        "slug": "trilinos_family",
        "name": "Trilinos Family",
        "category": "solver_backends",
        "module_class": "runtime_kernel",
        "bindings": ["C++", "MPI"],
        "solves": [
            "Canonical family packaging for Trilinos solver, preconditioner, and multigrid overlays",
        ],
        "best_for": [
            "Shared backend lineage for Trilinos child overlays",
        ],
        "not_for": ["Treating the family pack as a substitute for a concrete Trilinos package"],
        "source_refs": ["minutes://solver_table#L733", "minutes://solver_table#L853"],
        "environment_refs": ["artifact://environment-spec/eng_trilinos_family_docker"],
        "preferred_environment_ref": "artifact://environment-spec/eng_trilinos_family_docker",
        "import_target": "trilinos_family",
        "related": ["trilinos", "trilinos_belos", "trilinos_ifpack2", "trilinos_muelu"],
        "inventory_visible": False,
        "implementation_status": "implemented",
        "phase2_link_status": "detailed_linked_runtime_gated",
        "phase2_gate_mode": "rework",
        "phase2_gate_reason": "Trilinos family manifests are linked, but the canonical backend-family runtime has not been verified in this sprint.",
    },
    {
        "slug": "sparse_direct_family",
        "name": "Sparse Direct Family",
        "category": "solver_backends",
        "module_class": "runtime_kernel",
        "bindings": ["C", "C++", "Fortran"],
        "solves": [
            "Canonical family packaging for sparse-direct factorization and linear solve backends",
        ],
        "best_for": [
            "Shared lineage for MUMPS, SuperLU, SuiteSparse, and related child overlays",
        ],
        "not_for": ["Treating the family pack as a drop-in replacement for a named sparse-direct backend"],
        "source_refs": ["minutes://solver_table#L729", "minutes://solver_table#L735"],
        "environment_refs": ["artifact://environment-spec/eng_sparse_direct_family_docker"],
        "preferred_environment_ref": "artifact://environment-spec/eng_sparse_direct_family_docker",
        "import_target": "sparse_direct_family",
        "related": ["mumps", "superlu", "superlu_dist", "suitesparse", "cholmod", "umfpack", "klu", "strumpack"],
        "inventory_visible": False,
        "implementation_status": "implemented",
        "phase2_link_status": "detailed_linked_runtime_gated",
        "phase2_gate_mode": "rework",
        "phase2_gate_reason": "Sparse-direct family manifests are linked, but the canonical backend-family runtime has not been verified in this sprint.",
    },
    {
        "slug": "coinhsl_family",
        "name": "CoinHSL Family",
        "category": "solver_backends",
        "module_class": "runtime_kernel",
        "bindings": ["C", "Fortran"],
        "solves": [
            "Canonical family lineage for staged CoinHSL sparse-direct backends inside the IPOPT container path",
        ],
        "best_for": [
            "Shared lineage for MA57, MA77, MA86, MA87, and MA97 overlays",
        ],
        "not_for": ["Using the family lineage without respecting per-backend acquisition and packaging constraints"],
        "source_refs": ["minutes://solver_table#L728", "minutes://solver_table#L821"],
        "environment_refs": ["artifact://environment-spec/eng_ipopt_onemkl_docker"],
        "preferred_environment_ref": "artifact://environment-spec/eng_ipopt_onemkl_docker",
        "import_target": "coinhsl_family",
        "related": ["ma57", "ma77", "ma86", "ma87", "ma97", "ipopt"],
        "inventory_visible": False,
        "implementation_status": "implemented",
        "phase2_link_status": "detailed_linked_runtime_gated",
        "phase2_gate_mode": "rework",
        "phase2_gate_reason": "CoinHSL sources are staged locally, but the canonical IPOPT plus CoinHSL container has not been verified in this sprint.",
    },
    {
        "slug": "nlp_time_chem_family",
        "name": "NLP Time Chemistry Family",
        "category": "optimization_uq_backbone",
        "module_class": "runtime_kernel",
        "bindings": ["C", "C++", "Fortran"],
        "solves": [
            "Canonical family packaging for nonlinear optimization, time integration, and chemistry-side kernels",
        ],
        "best_for": [
            "Shared lineage for IPOPT, SUNDIALS, and TChem child overlays",
        ],
        "not_for": ["Treating the family pack as a replacement for a named solver runtime"],
        "source_refs": ["minutes://table1#L303", "minutes://table1#L316", "minutes://table1#L336"],
        "environment_refs": ["artifact://environment-spec/eng_nlp_time_chem_family_docker"],
        "preferred_environment_ref": "artifact://environment-spec/eng_nlp_time_chem_family_docker",
        "import_target": "nlp_time_chem_family",
        "related": ["ipopt", "sundials", "tchem"],
        "inventory_visible": False,
        "implementation_status": "implemented",
        "phase2_link_status": "detailed_linked_runtime_gated",
        "phase2_gate_mode": "rework",
        "phase2_gate_reason": "NLP, time-integration, and chemistry family manifests are linked, but the canonical family runtime has not been verified in this sprint.",
    },
    {
        "slug": "geometry_native_family",
        "name": "Geometry Native Family",
        "category": "geometry_manufacturing",
        "module_class": "runtime_kernel",
        "bindings": ["C++", "Python", "CLI"],
        "solves": [
            "Canonical family packaging for geometry-native kernels and geometry-adjacent runtime surfaces",
        ],
        "best_for": [
            "Shared lineage for CGAL, OpenCAMLib, and PicoGK/ShapeKernel overlays",
        ],
        "not_for": ["Treating the family pack as a substitute for a named geometry kernel"],
        "source_refs": ["minutes://table1#L308", "minutes://table1#L309", "minutes://table1#L301"],
        "environment_refs": ["artifact://environment-spec/eng_geometry_native_family_docker"],
        "preferred_environment_ref": "artifact://environment-spec/eng_geometry_native_family_docker",
        "import_target": "geometry_native_family",
        "related": ["cgal", "opencamlib", "picogk_shapekernel"],
        "inventory_visible": False,
        "implementation_status": "implemented",
        "phase2_link_status": "detailed_linked_runtime_gated",
        "phase2_gate_mode": "rework",
        "phase2_gate_reason": "Geometry-native family manifests are linked, but the canonical family runtime has not been verified in this sprint.",
    },
]

def _quote_for_single_shell(command: str) -> str:
    return command.replace("'", "'\"'\"'")


def _docker_healthcheck_command(env_id: str, command: str) -> str:
    return (
        f"python scripts/verify_knowledge_runtime.py --environment-ref "
        f"artifact://environment-spec/{env_id} --container-command bash -lc "
        f"'{_quote_for_single_shell(command)}'"
    )


def _conda_dockerfile_lines(packages: list[str], extra_lines: list[str] | None = None) -> list[str]:
    return [
        "FROM mambaorg/micromamba:1.5.10",
        "USER root",
        'SHELL ["bash", "-lc"]',
        "WORKDIR /workspace",
        f"RUN micromamba install -y -n base -c conda-forge {' '.join(packages)} && micromamba clean --all --yes",
        'ENV PATH="/opt/conda/bin:${PATH}"',
        "RUN ln -sf /opt/conda/bin/python /usr/local/bin/python || true",
        *(extra_lines or []),
        'CMD ["bash"]',
        "",
    ]


def _ubuntu_dockerfile_lines(
    apt_packages: list[str],
    *,
    pip_packages: list[str] | None = None,
    extra_lines: list[str] | None = None,
    base_image: str = "ubuntu:24.04",
) -> list[str]:
    packages = ["bash", "ca-certificates", *apt_packages]
    lines = [
        f"FROM {base_image}",
        'SHELL ["bash", "-lc"]',
        "WORKDIR /workspace",
        "RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "
        + " ".join(packages)
        + " && rm -rf /var/lib/apt/lists/*",
    ]
    if "python3" in packages:
        lines.append("RUN ln -sf /usr/bin/python3 /usr/local/bin/python || true")
    if pip_packages:
        lines.append(
            "RUN python3 -m pip install --break-system-packages --no-cache-dir "
            + " ".join(pip_packages)
        )
    lines.extend(extra_lines or [])
    lines.extend(['CMD ["bash"]', ""])
    return lines


def _passthrough_dockerfile_lines(
    base_image: str,
    *,
    apt_packages: list[str] | None = None,
    pip_packages: list[str] | None = None,
    extra_lines: list[str] | None = None,
) -> list[str]:
    lines = [
        f"FROM {base_image}",
        'SHELL ["bash", "-lc"]',
        "WORKDIR /workspace",
    ]
    if apt_packages:
        lines.append(
            "RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "
            + " ".join(["bash", "ca-certificates", *apt_packages])
            + " && rm -rf /var/lib/apt/lists/*"
        )
    if pip_packages:
        lines.append("RUN python3 -m pip install --break-system-packages --no-cache-dir " + " ".join(pip_packages))
    lines.extend(extra_lines or [])
    lines.extend(['CMD ["bash"]', ""])
    return lines


PHASE2_ENV_PROFILE_OVERRIDES = {
    "eng_ipopt_onemkl_docker": {
        "docker_platform": "linux/amd64",
        "runtime_gate_reason": PLANNED_IPOPT_ONEMKL_CONTAINER_REASON,
        "healthcheck_command": _docker_healthcheck_command(
            "eng_ipopt_onemkl_docker",
            "pkg-config --exists ipopt && test -d /opt/vendor/coinhsl-src && test -f /opt/intel/oneapi/mkl/latest/lib/libmkl_rt.so && echo OK:ipopt,hsl,onemkl",
        ),
        "dockerfile_lines": _passthrough_dockerfile_lines(
            "intel/oneapi-basekit:latest",
            apt_packages=[
                "python3",
                "python3-pip",
                "pkg-config",
                "git",
                "wget",
                "gpg",
                "build-essential",
                "cmake",
                "ninja-build",
                "gfortran",
                "coinor-libipopt-dev",
            ],
            extra_lines=[
                "COPY HSL/coinhsl-2024.05.15 /opt/vendor/coinhsl-src",
                "COPY HSL/CoinHSL.v2024.5.15.aarch64-apple-darwin-libgfortran5 /opt/vendor/coinhsl-prebuilt-darwin",
                "RUN test -f /opt/vendor/coinhsl-src/README && test -d /opt/vendor/coinhsl-src/ma57 && test -d /opt/vendor/coinhsl-src/hsl_ma77 && test -d /opt/vendor/coinhsl-src/hsl_ma86 && test -d /opt/vendor/coinhsl-src/hsl_ma97",
                "RUN test -f /opt/intel/oneapi/mkl/latest/lib/libmkl_rt.so",
                "RUN ln -sf /usr/bin/python3 /usr/local/bin/python || true",
            ],
        ),
    },
    "eng_petsc_family_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_petsc_family_docker",
            "python -c 'import primme,petsc4py,slepc4py; from petsc4py import PETSc; print(PETSc.Sys.getVersion())'",
        ),
        "dockerfile_lines": _conda_dockerfile_lines(
            ["python=3.11", "petsc", "petsc4py", "slepc", "slepc4py", "hypre", "mpi4py"],
            [
                "RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*",
                "RUN python -m pip install --no-cache-dir primme",
            ],
        ),
    },
    "eng_trilinos_family_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_trilinos_family_docker",
            "find /opt/conda -iname 'libtrilinos*.so*' -print -quit | grep -q . && echo OK:trilinos",
        ),
        "dockerfile_lines": _conda_dockerfile_lines(["trilinos"]),
    },
    "eng_sparse_direct_family_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_sparse_direct_family_docker",
            "find /opt/conda -iname '*mumps*' -print -quit | grep -q . && find /opt/conda -iname '*superlu*' -print -quit | grep -q . && echo OK:sparse-direct",
        ),
        "dockerfile_lines": _conda_dockerfile_lines(
            ["python=3.11", "mumps-mpi", "superlu", "superlu_dist", "suitesparse"]
        ),
    },
    "eng_nlp_time_chem_family_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_nlp_time_chem_family_docker",
            "find /opt/conda -iname '*sundials*' -print -quit | grep -q . && echo OK:nlp-time-chem",
        ),
        "dockerfile_lines": _conda_dockerfile_lines(["python=3.11", "sundials"]),
    },
    "eng_tchem_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_tchem_docker",
            "test -x /opt/tchem/bin/tchem.x && echo OK:tchem",
        ),
        "dockerfile_lines": [
            "FROM ubuntu:24.04",
            'SHELL ["bash", "-lc"]',
            "WORKDIR /workspace",
            "RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git cmake ninja-build build-essential gfortran libopenblas-dev liblapacke-dev libboost-all-dev ca-certificates && rm -rf /var/lib/apt/lists/*",
            "RUN install -d /opt/openblas/include /opt/openblas/lib && ln -sf /usr/include/x86_64-linux-gnu/openblas_config.h /opt/openblas/include/openblas_config.h && ln -sf /usr/include/x86_64-linux-gnu/cblas-openblas.h /opt/openblas/include/cblas_openblas.h && ln -sf /usr/include/lapacke.h /opt/openblas/include/lapacke.h && ln -sf /usr/lib/x86_64-linux-gnu/libopenblas.so /opt/openblas/lib/libopenblas.so && ln -sf /usr/lib/x86_64-linux-gnu/liblapacke.so /opt/openblas/lib/liblapacke.so && ln -sf /usr/lib/x86_64-linux-gnu/liblapack.so /opt/openblas/lib/liblapack.so",
            "RUN git clone --depth 1 -b yaml-cpp-0.6.3 https://github.com/jbeder/yaml-cpp.git /tmp/yaml-cpp && mkdir -p /tmp/build-yaml-cpp && cd /tmp/build-yaml-cpp && cmake -G Ninja -DCMAKE_INSTALL_PREFIX=/opt/yaml-cpp -DCMAKE_CXX_COMPILER=g++ -DCMAKE_C_COMPILER=gcc -DYAML_CPP_BUILD_TESTS=OFF -DYAML_CPP_BUILD_TOOLS=OFF /tmp/yaml-cpp && ninja install",
            "RUN git clone --depth 1 --branch 4.7.03 https://github.com/kokkos/kokkos.git /tmp/kokkos && mkdir -p /tmp/build-kokkos && cd /tmp/build-kokkos && cmake -G Ninja -DCMAKE_INSTALL_PREFIX=/opt/kokkos -DCMAKE_CXX_COMPILER=g++ -DCMAKE_CXX_FLAGS='-fopenmp -g -DKOKKOS_IMPL_PUBLIC_INCLUDE' -DKokkos_ENABLE_SERIAL=ON -DKokkos_ENABLE_OPENMP=ON -DKokkos_ENABLE_DEPRECATED_CODE=OFF /tmp/kokkos && ninja install && install -d /opt/kokkos/include/impl && cp -R /tmp/kokkos/core/src/impl/* /opt/kokkos/include/impl/ && cp /tmp/kokkos/core/src/View/Kokkos_ViewMapping.hpp /opt/kokkos/include/impl/Kokkos_ViewMapping.hpp",
            "RUN git clone --depth 1 https://github.com/sandialabs/Tines.git /tmp/Tines && python3 -c \"from pathlib import Path; p=Path('/tmp/Tines/src/core/linear-algebra/Tines_ArithTraits.hpp'); t=p.read_text(); s='#include \\\\\\\"Sacado.hpp\\\\\\\"'; r='#include <cfloat>\\\\n#include \\\\\\\"Sacado.hpp\\\\\\\"'; p.write_text(t if '#include <cfloat>' in t else t.replace(s, r, 1))\" && mkdir -p /tmp/build-tines && cd /tmp/build-tines && cmake -G Ninja -DCMAKE_INSTALL_PREFIX=/opt/tines -DCMAKE_CXX_COMPILER=g++ -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_FLAGS='-g -DKOKKOS_IMPL_PUBLIC_INCLUDE' -DCMAKE_EXE_LINKER_FLAGS='-lgfortran' -DTINES_ENABLE_DEBUG=OFF -DTINES_ENABLE_VERBOSE=OFF -DTINES_ENABLE_TEST=OFF -DTINES_ENABLE_EXAMPLE=OFF -DYAML_INSTALL_PATH=/opt/yaml-cpp -DKOKKOS_INSTALL_PATH=/opt/kokkos -DOPENBLAS_INSTALL_PATH=/opt/openblas -DLAPACKE_INSTALL_PATH=/opt/openblas /tmp/Tines/src && ninja install",
            "RUN git clone --depth 1 https://github.com/sandialabs/TChem.git /tmp/TChem && python3 -c \"from pathlib import Path; base=Path('/tmp/TChem/src'); rels=['core/TChem_Util.hpp','core/impl/TChem_Impl_Jacobian.hpp','core/impl/TChem_Impl_JacobianReduced.hpp','core/impl/TChem_Impl_RateOfProgessJacobian.hpp']; [(lambda p: p.write_text(p.read_text().replace('Kokkos::Impl::SpaceAccessibility<','Kokkos::SpaceAccessibility<').replace('::Rank','::rank')))(base / rel) for rel in rels]; p=base/'main/CMakeLists.txt'; t=p.read_text(); extra='\\nTARGET_LINK_LIBRARIES(\\${TCHEM_MAIN_EXE} /opt/openblas/lib/liblapacke.so /opt/openblas/lib/liblapack.so)\\nTARGET_LINK_LIBRARIES(\\${TCHEM_JSON_TEST_EXE} /opt/openblas/lib/liblapacke.so /opt/openblas/lib/liblapack.so)\\n'; p.write_text(t if extra in t else t + extra)\" && mkdir -p /tmp/build-tchem && cd /tmp/build-tchem && cmake -G Ninja -DCMAKE_INSTALL_PREFIX=/opt/tchem -DCMAKE_CXX_COMPILER=g++ -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_FLAGS='-DKOKKOS_IMPL_PUBLIC_INCLUDE' -DCMAKE_EXE_LINKER_FLAGS='-lgfortran' -DCMAKE_BUILD_TYPE=Release -DTCHEM_ENABLE_VERBOSE=OFF -DTCHEM_ENABLE_TEST=OFF -DTCHEM_ENABLE_EXAMPLE=OFF -DTCHEM_ENABLE_PYTHON=OFF -DTCHEM_ENABLE_MAIN=ON -DKOKKOS_INSTALL_PATH=/opt/kokkos -DTINES_INSTALL_PATH=/opt/tines /tmp/TChem/src && ninja install",
            'CMD ["bash"]',
            "",
        ],
    },
    "eng_geometry_native_family_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_geometry_native_family_docker",
            "python -c 'import CGAL, opencamlib; print(CGAL.__file__); print(opencamlib.__file__)'",
        ),
        "dockerfile_lines": _conda_dockerfile_lines(
            ["python=3.11", "cgal", "opencamlib"],
        ),
    },
    "eng_openfoam_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_openfoam_docker",
            "compgen -c | grep -Eq '(^|/)(icoFoam|simpleFoam|foamDictionary)$' && echo OK:openfoam",
        ),
        "dockerfile_lines": _ubuntu_dockerfile_lines(["openfoam"]),
    },
    "eng_calculix_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_calculix_docker",
            "command -v ccx >/dev/null || command -v ccx_2.21 >/dev/null && echo OK:calculix",
        ),
        "dockerfile_lines": _ubuntu_dockerfile_lines(["calculix-ccx"]),
    },
    "eng_openmodelica_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_openmodelica_docker",
            "omc --version",
        ),
        "dockerfile_lines": _passthrough_dockerfile_lines(
            "openmodelica/openmodelica:v1.26.3-minimal",
            apt_packages=["python3", "python3-pip"],
        ),
    },
    "eng_paraview_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_paraview_docker",
            "(paraview --version >/dev/null || pvserver --version >/dev/null) && echo OK:paraview",
        ),
        "dockerfile_lines": _ubuntu_dockerfile_lines(["paraview", "mesa-utils", "xvfb"]),
    },
    "eng_fenicsx_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_fenicsx_docker",
            "python3 -c 'import dolfinx; print(dolfinx.__version__)'",
        ),
        "dockerfile_lines": _passthrough_dockerfile_lines("ghcr.io/fenics/dolfinx/dolfinx:stable"),
    },
    "eng_dealii_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_dealii_docker",
            "test -f /usr/include/deal.II/base/config.h && echo OK:dealii",
        ),
        "dockerfile_lines": _ubuntu_dockerfile_lines(["libdeal.ii-dev"]),
    },
    "eng_kratos_multiphysics_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_kratos_multiphysics_docker",
            "python -c 'import KratosMultiphysics; print(KratosMultiphysics.__file__)'",
        ),
        "dockerfile_lines": "\n".join(
            _passthrough_dockerfile_lines(
                "python:3.11-slim",
                apt_packages=["libgomp1"],
                pip_packages=["KratosMultiphysics"],
            )
        ).splitlines(),
    },
    "eng_system_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_system_docker",
            "python -c 'import pyfmi; print(pyfmi.__file__)'",
        ),
        "dockerfile_lines": _conda_dockerfile_lines(["python=3.11", "pyfmi"]),
    },
    "eng_backbone_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_backbone_docker",
            "python -c 'import precice; print(precice.__file__)'",
        ),
        "dockerfile_lines": _conda_dockerfile_lines(["python=3.11", "precice", "pyprecice"]),
    },
    "eng_project_chrono_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_project_chrono_docker",
            "python -c 'import pychrono; print(pychrono.__version__)'",
        ),
        "dockerfile_lines": "\n".join(
            _passthrough_dockerfile_lines(
                "python:3.11-slim",
                pip_packages=["pychrono"],
            )
        ).splitlines(),
    },
    "eng_dakota_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_dakota_docker",
            "dakota --version >/dev/null && echo OK:dakota",
        ),
        "dockerfile_lines": _conda_dockerfile_lines(["dakota"]),
    },
    "eng_su2_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_su2_docker",
            "SU2_CFD -h >/dev/null && echo OK:su2",
        ),
        "dockerfile_lines": _conda_dockerfile_lines(["python=3.11", "su2"]),
    },
    "eng_code_aster_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_code_aster_docker",
            "mkdir -p /tmp/flasheur && export HOME=/tmp && as_run --version | grep -q 'as_run' && echo OK:code_aster",
        ),
        "dockerfile_lines": _passthrough_dockerfile_lines(
            "codeastersolver/codeaster-seq",
            extra_lines=["ENTRYPOINT []"],
        ),
    },
    "eng_code_saturne_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_code_saturne_docker",
            "/opt/code_saturne/bin/code_saturne help >/tmp/code_saturne_help.log 2>&1 || true; grep -q 'code_saturne <topic>' /tmp/code_saturne_help.log && echo OK:code_saturne",
        ),
        "dockerfile_lines": _passthrough_dockerfile_lines(
            "simvia/code_saturne",
            extra_lines=["ENTRYPOINT []"],
        ),
    },
    "eng_opensmokepp_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_opensmokepp_docker",
            "command -v OpenSMOKEpp_BatchReactor.sh >/dev/null && echo OK:opensmokepp",
        ),
        "dockerfile_lines": _passthrough_dockerfile_lines(
            "evamunozsalamanca/opensmokesuite21",
            extra_lines=["ENTRYPOINT []"],
        ),
    },
    "eng_openwam_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_openwam_docker",
            "test -f /opt/openwam/OpenWAM.exe && strings /opt/openwam/OpenWAM.exe | grep -q 'OpenWAM' && echo OK:openwam",
        ),
        "dockerfile_lines": [
            "FROM debian:bookworm-slim",
            'SHELL ["bash", "-lc"]',
            "WORKDIR /workspace",
            "RUN dpkg --add-architecture i386 && apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git cmake make g++ mingw-w64 wine64 xvfb xauth ca-certificates && rm -rf /var/lib/apt/lists/*",
            "RUN git clone --depth 1 https://github.com/CMT-UPV/OpenWAM.git /tmp/OpenWAM && sed -i 's/<Windows.h>/<windows.h>/' /tmp/OpenWAM/Source/TOpenWAM.cpp && cd /tmp/OpenWAM && cmake -B build -S . -DCMAKE_SYSTEM_NAME=Windows -DCMAKE_C_COMPILER=x86_64-w64-mingw32-gcc -DCMAKE_CXX_COMPILER=x86_64-w64-mingw32-g++ -DCMAKE_RC_COMPILER=x86_64-w64-mingw32-windres && cmake --build build -j2",
            "RUN exe=$(find /tmp/OpenWAM/build -iname 'OpenWAM*.exe' -print -quit) && test -n \"$exe\" && install -d /opt/openwam/probe && install -m755 \"$exe\" /opt/openwam/OpenWAM.exe && cp $(find /usr/lib/gcc/x86_64-w64-mingw32 -name 'libgcc_s_seh-1.dll' -print -quit) /opt/openwam/ && cp $(find /usr/lib/gcc/x86_64-w64-mingw32 -name 'libstdc++-6.dll' -print -quit) /opt/openwam/ && cp /usr/x86_64-w64-mingw32/lib/libwinpthread-1.dll /opt/openwam/ && : > /opt/openwam/probe/missing.wam",
            'CMD ["bash"]',
            "",
        ],
    },
    "eng_moose_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_moose_docker",
            "test -x /opt/moose/bin/moose-opt && test -x /opt/moose/bin/combined-opt && echo OK:moose",
        ),
        "dockerfile_lines": _passthrough_dockerfile_lines(
            "idaholab/moose",
            extra_lines=["ENTRYPOINT []"],
        ),
    },
    "eng_mbdyn_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_mbdyn_docker",
            "test -x /mbdyn/bin/mbdyn && echo OK:mbdyn",
        ),
        "dockerfile_lines": _passthrough_dockerfile_lines(
            "guniverse/mbdyn",
            extra_lines=["ENTRYPOINT []"],
        ),
    },
    "eng_salome_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_salome_docker",
            "salome -h | grep -q 'Usage: salome' && echo OK:salome",
        ),
        "dockerfile_lines": _passthrough_dockerfile_lines(
            "tefe/salome-meca",
            extra_lines=["ENTRYPOINT []"],
        ),
    },
    "eng_hermes_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_hermes_docker",
            "test -x /usr/local/bin/hermes_probe && echo OK:hermes",
        ),
        "dockerfile_lines": [
            "FROM ubuntu:24.04",
            'SHELL ["bash", "-lc"]',
            "WORKDIR /workspace",
            "RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git cmake ninja-build build-essential gfortran freeglut3-dev libsuitesparse-dev libglew-dev libxerces-c-dev xsdcxx libmatio-dev python3 ca-certificates && rm -rf /var/lib/apt/lists/*",
            "RUN git clone --depth 1 https://github.com/hpfem/hermes.git /tmp/hermes && cd /tmp/hermes && cp CMake.vars.example.Linux CMake.vars && python3 - <<'PY'\nfrom pathlib import Path\np=Path('/tmp/hermes/CMake.vars')\ntext=p.read_text()\nfor old,new in [('set(H2D_WITH_GLUT YES)','set(H2D_WITH_GLUT NO)'),('set(H2D_WITH_TEST_EXAMPLES YES)','set(H2D_WITH_TEST_EXAMPLES NO)')]:\n    text=text.replace(old,new)\np.write_text(text)\nPY",
            "RUN cd /tmp/hermes && cmake -B build -S . -GNinja -DCMAKE_INSTALL_PREFIX=/opt/hermes && cp build/hermes_common/include/config.h hermes_common/include/config.h && cp build/hermes2d/include/config.h hermes2d/include/config.h && ln -snf /tmp/hermes/hermes2d/xml_schemas build/hermes2d/xml_schemas && rm -rf build/hermes2d/include && ln -snf /tmp/hermes/hermes2d/include build/hermes2d/include && rm -rf build/hermes2d/src && ln -snf /tmp/hermes/hermes2d/src build/hermes2d/src && cmake --build build -j2 && cmake --install build",
            "RUN printf '%s\\n' '#!/bin/sh' 'test -f /opt/hermes/include/hermes2d/hermes2d.h' 'test -f /opt/hermes/include/hermes_common/hermes_common.h' 'find /opt/hermes -name \"libhermes2d*.so*\" -o -name \"libhermes_common*.so*\" | grep -q .' 'echo OK:hermes' >/usr/local/bin/hermes_probe && chmod +x /usr/local/bin/hermes_probe",
            'CMD ["bash"]',
            "",
        ],
    },
    "eng_strumpack_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_strumpack_docker",
            "test -x /usr/local/bin/strumpack_probe && echo OK:strumpack",
        ),
        "dockerfile_lines": [
            "FROM ubuntu:24.04",
            'SHELL ["bash", "-lc"]',
            "WORKDIR /workspace",
            "RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git cmake ninja-build build-essential gfortran libopenmpi-dev openmpi-bin libopenblas-dev liblapack-dev libscalapack-openmpi-dev libmetis-dev ca-certificates && rm -rf /var/lib/apt/lists/*",
            "RUN git clone --depth 1 https://github.com/pghysels/STRUMPACK.git /tmp/STRUMPACK && mkdir -p /tmp/build-strumpack && cd /tmp/build-strumpack && cmake -G Ninja -DCMAKE_INSTALL_PREFIX=/opt/strumpack -DSTRUMPACK_USE_MPI=OFF -DSTRUMPACK_USE_OPENMP=ON -DTPL_ENABLE_SCOTCH=OFF -DTPL_ENABLE_PTSCOTCH=OFF -DTPL_ENABLE_PARMETIS=OFF -DTPL_ENABLE_BPACK=OFF -DTPL_ENABLE_ZFP=OFF -DTPL_ENABLE_SLATE=OFF -DTPL_ENABLE_COMBBLAS=OFF /tmp/STRUMPACK && ninja install",
            "RUN printf '%s\\n' '#include <StrumpackSparseSolver.hpp>' 'int main(){return 0;}' >/tmp/strumpack_probe.cpp && g++ -I/opt/strumpack/include /tmp/strumpack_probe.cpp -o /usr/local/bin/strumpack_probe",
            'CMD ["bash"]',
            "",
        ],
    },
    "eng_rmg_py_docker": {
        "docker_platform": "linux/amd64",
        "healthcheck_command": _docker_healthcheck_command(
            "eng_rmg_py_docker",
            "python -c 'import rmgpy, arkane; print(rmgpy.__file__)'",
        ),
        "dockerfile_lines": [
            "FROM mambaorg/micromamba:1.5.10",
            "USER root",
            'SHELL ["bash", "-lc"]',
            "WORKDIR /workspace",
            "RUN micromamba install -y -n base -c conda-forge -c rmg python=3.9 rmg=3.3.0 && micromamba clean --all --yes",
            'CMD ["bash"]',
            "",
        ],
    },
    "eng_rhino_host": {
        "phase2_verified": True,
    },
}


def _phase2_slug_label(slug: str) -> str:
    return slug.replace("_", " ").replace("pp", "++")


def _phase2_family_pack_slug(slug: str, metadata: dict[str, object] | None) -> str | None:
    if slug in {"pardiso", "ipopt", "ma57", "ma77", "ma86", "ma87", "ma97"}:
        return "coinhsl_family" if slug.startswith("ma") else "nlp_time_chem_family"
    if slug in {"picogk_shapekernel", "cgal", "opencamlib"}:
        return "geometry_native_family"
    if metadata is None:
        return None
    install_batch = metadata["install_batch"]
    return {
        "phase1_batch1a_petsc_family": "petsc_family",
        "phase1_batch1b_trilinos_family": "trilinos_family",
        "phase1_batch1c_sparse_direct_family": "sparse_direct_family",
        "phase1_batch1d_nlp_time_chem_family": "nlp_time_chem_family",
        "phase1_batch1e_geometry_native_family": "geometry_native_family",
    }.get(install_batch)


def _phase2_default_bindings(module: dict, metadata: dict[str, object] | None) -> list[str]:
    if module["slug"] == "rhino_common":
        return ["C#", "Python", "CLI"]
    if module["slug"] == "openmodelica":
        return ["CLI", "Modelica"]
    if module["module_class"] == "standard":
        return ["Spec", "Schema"]
    if metadata and metadata["install_method_category"] == "I3_python_first_venv_package":
        return ["Python"]
    if module["module_class"] == "integration_layer":
        return ["Python", "CLI"]
    if module["module_class"] == "runtime_kernel":
        return ["C", "C++", "Fortran"]
    if module["module_class"] == "framework":
        return ["Python", "C++"]
    return ["CLI", "C++"]


def _phase2_domain_label(category: str) -> str:
    return {
        "seed_stack": "core engineering workflows",
        "geometry_manufacturing": "geometry and manufacturing workflows",
        "thermofluids_chemistry": "thermofluids and chemistry workflows",
        "structures_pde": "structures and PDE workflows",
        "electrics_dynamics_system": "electrical, dynamic, and system workflows",
        "optimization_uq_backbone": "optimization, UQ, and numerical-backbone workflows",
        "workflow_coupling": "workflow coupling and cross-runtime integration",
        "solver_backends": "solver-backend workflows",
        "domain_specific": "domain-specific engineering workflows",
        "reserve": "reserve engineering workflows",
        "csharp_examples": "host-side C# and scripting workflows",
    }.get(category, "engineering workflows")


def _phase2_scope_for_module(module: dict) -> tuple[list[str], list[str]]:
    if "solves" in module:
        return list(module["solves"]), list(module["not_for"])
    domain = _phase2_domain_label(module["category"])
    name = module["name"]
    module_class = module["module_class"]
    solves = {
        "application": [
            f"{name} executable workflows for {domain}",
            f"{name} case setup, launch, and output capture inside the knowledge runtime",
        ],
        "framework": [
            f"{name} API-driven workflows for {domain}",
            f"{name} model assembly and orchestration inside a typed runtime boundary",
        ],
        "integration_layer": [
            f"{name} bridges parent runtimes into typed {domain} workflows",
            f"{name} exchange boundaries and compatibility checks across linked runtimes",
        ],
        "runtime_kernel": [
            f"{name} backend kernels reused by {domain}",
            f"{name} low-level numeric or geometric primitives inside a linked execution adapter",
        ],
        "translator": [
            f"{name} explicit translation boundaries for {domain}",
            f"{name} format conversion with auditable runtime provenance",
        ],
        "standard": [
            f"{name} validation and schema mapping for {domain}",
            f"{name} typed interchange contracts across linked host runtimes",
        ],
    }[module_class]
    not_for = [
        f"Using {name} as a substitute for unrelated workflows outside {domain}",
        f"Treating {name} as implicitly verified without its linked runtime and evidence bundle",
    ]
    return solves, not_for


def _phase2_core_objects(module: dict, preferred_env_ref: str) -> list[dict[str, str]]:
    name = module["name"]
    import_target = module.get("import_target", module["slug"])
    by_class = {
        "application": [
            (f"{name} CLI", "cli_surface", "Primary executable entry surface"),
            (f"{name} case/setup artifact", "case_definition", "Canonical problem/case boundary"),
            (preferred_env_ref.split("/")[-1], "environment_spec", "Runtime carrier for the executable surface"),
        ],
        "framework": [
            (import_target, "api_surface", "Primary import or API surface"),
            (f"{name} model object", "model_surface", "Main authored object graph inside the framework"),
            (preferred_env_ref.split("/")[-1], "environment_spec", "Runtime carrier for the framework surface"),
        ],
        "integration_layer": [
            (import_target, "integration_surface", "Primary integration or wrapper entry surface"),
            (f"{name} exchange contract", "exchange_boundary", "Typed boundary crossing between runtimes"),
            (preferred_env_ref.split("/")[-1], "environment_spec", "Runtime carrier for the integration surface"),
        ],
        "runtime_kernel": [
            (import_target, "backend_surface", "Primary backend or shared-library surface"),
            (f"{name} configuration surface", "runtime_config", "Backend-specific configuration boundary"),
            (preferred_env_ref.split("/")[-1], "environment_spec", "Runtime carrier for the backend surface"),
        ],
        "translator": [
            (f"{name} reader", "reader_surface", "Declared inbound translation surface"),
            (f"{name} writer", "writer_surface", "Declared outbound translation surface"),
            (preferred_env_ref.split("/")[-1], "environment_spec", "Runtime carrier for translation tooling"),
        ],
        "standard": [
            (f"{name} schema", "schema_surface", "Primary schema or specification surface"),
            (f"{name} validator", "validation_surface", "Deterministic conformance surface"),
            (preferred_env_ref.split("/")[-1], "environment_spec", "Runtime used to validate or translate the standard"),
        ],
    }
    return [
        {"name": item[0], "kind": item[1], "role": item[2]}
        for item in by_class[module["module_class"]]
    ]


def _phase2_anti_patterns(module: dict, preferred_env_ref: str, substitution_note: str | None) -> list[str]:
    solves, not_for = _phase2_scope_for_module(module)
    patterns = [
        f"Using {module['name']} for {not_for[0].lower()}.",
        f"Skipping the linked health check and provenance capture for {preferred_env_ref}.",
    ]
    if substitution_note:
        patterns.append(
            f"Treating {module['name']} as a separate runtime from its canonical substitution path."
        )
    elif solves:
        patterns.append(
            f"Crossing the adapter boundary for {module['name']} without a typed contract tied to {solves[0].lower()}."
        )
    return patterns


def _phase2_recipe_pattern(module: dict, preferred_env_ref: str, phase2_link_status: str) -> list[str]:
    gating_step = {
        "recommendable": "Record the passing verification report before using the module output downstream",
        "detailed_linked_parent_gated": "Stop if the parent-runtime compatibility gate is still REWORK",
        "detailed_linked_manual": "Stop at the acquisition gate until the missing external artifact is staged",
    }.get(
        phase2_link_status,
        "Stop if the runtime verification report is still REWORK",
    )
    return [
        f"Resolve {preferred_env_ref} as the canonical runtime surface",
        f"Run the linked health check for {module['name']}",
        gating_step,
        f"Execute {module['name']} only inside its declared capability boundary and record the evidence refs",
    ]


def _phase2_failure_signatures(module: dict, phase2_link_status: str) -> list[str]:
    signatures = [
        f"{module['name']} import, linker, or launcher failure in the linked runtime",
        f"{module['name']} used outside its declared capability boundary",
    ]
    if phase2_link_status == "detailed_linked_parent_gated":
        signatures.append(f"Parent runtime for {module['name']} is still unresolved or incompatible")
    if phase2_link_status == "detailed_linked_manual":
        signatures.append(f"External acquisition for {module['name']} is incomplete or staged in the wrong location")
    return signatures


def _phase2_reviewer_checklist(module: dict, phase2_link_status: str) -> list[str]:
    checklist = [
        f"{module['name']} pack links to the intended environment spec(s)",
        f"{module['name']} adapter and evidence bundle reference the same runtime verification report",
        f"{module['name']} anti-patterns and failure signatures match the module class and runtime path",
    ]
    if phase2_link_status == "detailed_linked_parent_gated":
        checklist.append(f"Parent-runtime gate remains explicit for {module['name']}")
    if phase2_link_status == "detailed_linked_manual":
        checklist.append(f"Manual acquisition gate remains explicit for {module['name']}")
    return checklist


def _phase2_link_status_for_module(module: dict, metadata: dict[str, object] | None) -> str:
    if module["implementation_status"] == "implemented":
        return "recommendable"
    slug = module["slug"]
    if slug in {"cgns", "exodus_ii", "fmi_fmus"}:
        return "recommendable"
    if metadata is None:
        return "recommendable"
    if metadata["manual_acquisition_required"]:
        return "detailed_linked_manual"
    if metadata["cli_phase1_status"] == "blocked_by_parent_runtime":
        return "detailed_linked_parent_gated"
    if metadata["cli_phase1_status"] == "installed":
        return (
            "detailed_linked_parent_gated"
            if str(metadata["acquisition_status"]).endswith("parent_pending")
            else "recommendable"
        )
    if metadata["cli_phase1_status"] == "knowledge_only" and metadata["blocked_by_refs"]:
        return "detailed_linked_parent_gated"
    return "detailed_linked_runtime_gated"


def _phase2_environment_refs_map() -> dict[str, list[str]]:
    refs = {slug: list(values) for slug, values in EXCLUDED_ENVIRONMENT_REFS.items()}
    for slug in (
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
    ):
        refs.setdefault(slug, [artifact_ref("environment-spec", f"eng_{slug}_docker")])
    for slug in ("petsc", "petsc_ksp", "petsc_gamg", "slepc", "hypre", "primme", "petsc4py"):
        refs.setdefault(slug, ["artifact://environment-spec/eng_petsc_family_docker"])
    for slug in ("trilinos", "trilinos_belos", "trilinos_ifpack2", "trilinos_muelu"):
        refs.setdefault(slug, ["artifact://environment-spec/eng_trilinos_family_docker"])
    for slug in ("mumps", "superlu", "superlu_dist", "suitesparse", "cholmod", "umfpack", "klu", "strumpack"):
        refs.setdefault(slug, ["artifact://environment-spec/eng_sparse_direct_family_docker"])
    for slug in ("sundials", "tchem"):
        refs.setdefault(slug, ["artifact://environment-spec/eng_nlp_time_chem_family_docker"])
    for slug in ("cgal", "opencamlib"):
        refs.setdefault(slug, ["artifact://environment-spec/eng_geometry_native_family_docker"])
    refs.setdefault("pyoptsparse", ["artifact://environment-spec/eng_ipopt_onemkl_docker"])
    refs.setdefault(
        "precice",
        [
            "artifact://environment-spec/eng_backbone_docker",
            "artifact://environment-spec/eng_openfoam_docker",
            "artifact://environment-spec/eng_calculix_docker",
        ],
    )
    refs.setdefault("petsc4py", ["artifact://environment-spec/eng_petsc_family_docker"])
    refs.setdefault(
        "pyfmi",
        [
            "artifact://environment-spec/eng_system_docker",
            "artifact://environment-spec/eng_openmodelica_docker",
            "artifact://environment-spec/eng_system_uv",
        ],
    )
    refs.setdefault("medcoupling", ["artifact://environment-spec/eng_salome_docker"])
    refs.setdefault("pyphs", ["artifact://environment-spec/eng_system_uv", "artifact://environment-spec/eng_system_docker"])
    refs.setdefault("porepy", ["artifact://environment-spec/eng_structures_uv", "artifact://environment-spec/eng_structures_docker"])
    refs["strumpack"] = ["artifact://environment-spec/eng_strumpack_docker"]
    refs["tchem"] = ["artifact://environment-spec/eng_tchem_docker"]
    refs["rmg_py"] = ["artifact://environment-spec/eng_rmg_py_docker"]
    refs.setdefault("cgns", ["artifact://environment-spec/eng_geometry_uv", "artifact://environment-spec/eng_backbone_uv"])
    refs.setdefault("exodus_ii", ["artifact://environment-spec/eng_geometry_uv", "artifact://environment-spec/eng_backbone_uv"])
    refs.setdefault("fmi_fmus", ["artifact://environment-spec/eng_system_uv"])
    refs.setdefault("modelica_standard_library", ["artifact://environment-spec/eng_openmodelica_docker"])
    refs.setdefault("femm", ["artifact://environment-spec/eng_wine_docker"])
    refs.setdefault("pyleecan", ["artifact://environment-spec/eng_system_uv", "artifact://environment-spec/eng_system_docker"])
    refs.setdefault("ma87", ["artifact://environment-spec/eng_ipopt_onemkl_docker"])
    refs.setdefault("rhino_common", ["artifact://environment-spec/eng_rhino_host"])
    refs.setdefault("pardiso", ["artifact://environment-spec/eng_ipopt_onemkl_docker"])
    return refs


def _phase2_additional_runtime_profiles() -> list[dict]:
    profiles: list[dict] = []

    def planned_docker_profile(
        env_id: str,
        runtime_profile: str,
        module_ids: list[str],
        note: str,
    ) -> dict:
        return {
            "id": env_id,
            "runtime_profile": runtime_profile,
            "delivery_kind": "docker_image",
            "module_ids": module_ids,
            "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
            "manifest_format": "dockerfile",
            "manifest_path": f"knowledge/coding-tools/runtime/docker/{env_id}.Dockerfile",
            "runtime_locator": f"birtha/knowledge-{runtime_profile}:1.0.0",
            "bootstrap_command": f"python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/{env_id}",
            "healthcheck_command": f"python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/{env_id}",
            "launcher_ref": f"knowledge/coding-tools/runtime/launchers/{env_id.replace('_docker', '')}-container.sh",
            "requirements": [],
            "verification_enabled": False,
            "runtime_gate_reason": note,
            "notes": [note],
        }

    for slug in (
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
    ):
        profiles.append(
            planned_docker_profile(
                f"eng_{slug}_docker",
                f"eng-{slug.replace('_', '-')}",
                [slug],
                f"{_phase2_slug_label(slug).title()} runtime manifest is linked, but the canonical solver-platform runtime has not been verified in this sprint.",
            )
        )
    profiles.extend(
        [
            planned_docker_profile(
                "eng_petsc_family_docker",
                "eng-petsc-family",
                ["petsc", "petsc_ksp", "petsc_gamg", "slepc", "hypre", "primme", "petsc4py"],
                "PETSc family manifest is linked, but the canonical backend-family runtime has not been verified in this sprint.",
            ),
            planned_docker_profile(
                "eng_trilinos_family_docker",
                "eng-trilinos-family",
                ["trilinos", "trilinos_belos", "trilinos_ifpack2", "trilinos_muelu"],
                "Trilinos family manifest is linked, but the canonical backend-family runtime has not been verified in this sprint.",
            ),
            planned_docker_profile(
                "eng_sparse_direct_family_docker",
                "eng-sparse-direct-family",
                ["mumps", "superlu", "superlu_dist", "suitesparse", "cholmod", "umfpack", "klu", "strumpack"],
                "Sparse-direct family manifest is linked, but the canonical backend-family runtime has not been verified in this sprint.",
            ),
            planned_docker_profile(
                "eng_nlp_time_chem_family_docker",
                "eng-nlp-time-chem-family",
                ["ipopt", "sundials", "tchem"],
                "NLP, time-integration, and chemistry family manifest is linked, but the canonical family runtime has not been verified in this sprint.",
            ),
            planned_docker_profile(
                "eng_geometry_native_family_docker",
                "eng-geometry-native-family",
                ["cgal", "opencamlib", "picogk_shapekernel"],
                "Geometry-native family manifest is linked, but the canonical family runtime has not been verified in this sprint.",
            ),
            planned_docker_profile(
                "eng_strumpack_docker",
                "eng-strumpack",
                ["strumpack"],
                "STRUMPACK now resolves to its own dedicated source-built sparse-direct runtime.",
            ),
            planned_docker_profile(
                "eng_tchem_docker",
                "eng-tchem",
                ["tchem"],
                "TChem now resolves to its own dedicated source-built kinetics runtime.",
            ),
            planned_docker_profile(
                "eng_rmg_py_docker",
                "eng-rmg-py",
                ["rmg_py"],
                "RMG-Py now resolves to its own dedicated chemistry-model runtime.",
            ),
        ]
    )
    return profiles


def _all_runtime_profiles() -> list[dict]:
    profiles = [dict(item) for item in RUNTIME_PROFILES]
    seen = {item["id"] for item in profiles}
    for item in _phase2_additional_runtime_profiles():
        if item["id"] not in seen:
            profiles.append(item)
            seen.add(item["id"])
    for item in profiles:
        override = PHASE2_ENV_PROFILE_OVERRIDES.get(item["id"])
        if override:
            item.update(override)
        if item["delivery_kind"] == "docker_image":
            item.setdefault("docker_platform", "linux/amd64")
    return profiles


def _base_docker_profiles() -> list[dict]:
    return [
        profile
        for profile in _all_runtime_profiles()
        if profile["delivery_kind"] == "docker_image" and not profile["id"].endswith("_gui")
    ]


def _gui_env_id(profile: dict) -> str:
    return profile["id"].replace("_docker", "_gui") if profile["id"].endswith("_docker") else f"{profile['id']}_gui"


def _gui_manifest_path(profile: dict) -> str:
    return f"knowledge/coding-tools/runtime/docker/gui/{_gui_env_id(profile)}.Dockerfile"


def _gui_launcher_ref(profile: dict) -> str:
    return f"knowledge/coding-tools/runtime/launchers/gui/{_gui_env_id(profile)}.sh"


def _gui_image_for_profile(profile: dict) -> str:
    image = str(profile["runtime_locator"])
    if ":" in image:
        base, tag = image.rsplit(":", 1)
        return f"{base}-gui:{tag}"
    return f"{image}-gui"


def _gui_app_profile(profile: dict) -> str:
    env_id = profile["id"]
    modules = set(profile["module_ids"])
    if "paraview" in modules:
        return "paraview"
    if "salome" in modules:
        return "salome"
    if "openwam" in modules:
        return "openwam_wine"
    if "wine64" in modules or env_id == "eng_wine_docker":
        return "wine"
    if "openmodelica" in modules:
        return "openmodelica"
    if "vtk" in modules or env_id == "eng_backbone_docker":
        return "python_vtk"
    if "rmg_py" in modules:
        return "rmg_py"
    if {"gmsh", "cadquery", "occt"} & modules:
        return "geometry_cad"
    return "diagnostic_shell"


def _gui_launch_target_command(profile: dict) -> str:
    app_profile = _gui_app_profile(profile)
    return {
        "paraview": "paraview",
        "salome": "salome",
        "openwam_wine": "bash -lc 'wine64 /opt/openwam/OpenWAM.exe || true; tail -f /dev/null'",
        "wine": "bash -lc 'winecfg || true; tail -f /dev/null'",
        "openmodelica": "OMEdit || xterm",
        "python_vtk": "python -c 'import vtk; print(vtk.vtkVersion.GetVTKVersion())'; xterm",
        "rmg_py": "bash -lc 'python -c \"import rmgpy; print(rmgpy.__file__)\"; xterm'",
        "geometry_cad": "bash -lc 'python -c \"import cadquery, gmsh; print(\\\"geometry gui ready\\\")\"; xterm'",
        "diagnostic_shell": "xterm",
    }[app_profile]


def _gui_environment_payload(profile: dict) -> dict:
    gui_id = _gui_env_id(profile)
    gui_ref = gui_session_ref(gui_id)
    return {
        "environment_spec_id": gui_id,
        "schema_version": "1.0.0",
        "runtime_profile": f"{profile['runtime_profile']}-gui",
        "delivery_kind": "docker_image",
        "docker_platform": profile.get("docker_platform", "linux/amd64"),
        "gui_session_refs": [gui_ref],
        "default_gui_session_ref": gui_ref,
        "gui_capability_state": "PLANNED_CONTAINER_GUI",
        "module_ids": profile["module_ids"],
        "supported_host_platforms": profile["supported_host_platforms"],
        "manifest_format": "dockerfile",
        "manifest_path": _gui_manifest_path(profile),
        "runtime_locator": _gui_image_for_profile(profile),
        "bootstrap_command": f"python scripts/bootstrap_knowledge_gui_runtime.py --gui-session-ref {gui_ref}",
        "healthcheck_command": f"python scripts/verify_knowledge_gui_runtime.py --gui-session-ref {gui_ref}",
        "launcher_ref": _gui_launcher_ref(profile),
        "notes": [
            f"Sibling container GUI runtime for {profile['runtime_profile']} using noVNC and OpenClaw browser control.",
            "This GUI runtime is noncanonical for CLI execution and does not replace the base environment spec.",
        ],
    }


def _gui_session_payload(profile: dict) -> dict:
    gui_id = _gui_env_id(profile)
    gui_ref = gui_session_ref(gui_id)
    return {
        "gui_session_spec_id": gui_id,
        "schema_version": "1.0.0",
        "base_environment_ref": artifact_ref("environment-spec", profile["id"]),
        "gui_environment_ref": artifact_ref("environment-spec", gui_id),
        "module_ids": profile["module_ids"],
        "docker_image": _gui_image_for_profile(profile),
        "docker_platform": profile.get("docker_platform", "linux/amd64"),
        "display_protocol": "novnc_web",
        "control_provider": "openclaw_browser",
        "container_ports": {"bind_host": "127.0.0.1", "novnc": 6080, "vnc": 5900},
        "display_env": {"DISPLAY": ":99", "NOVNC_PORT": "6080", "VNC_PORT": "5900"},
        "launch_command": _gui_launcher_ref(profile),
        "healthcheck_command": f"python scripts/verify_knowledge_gui_runtime.py --gui-session-ref {gui_ref}",
        "openclaw_entry_url": "http://127.0.0.1:{novnc_port}/vnc.html?autoconnect=true&resize=scale",
        "artifact_output_dir": f".cache/knowledge-gui-artifacts/{gui_id}",
        "security_policy": {
            "bind_host": "127.0.0.1",
            "require_token": True,
            "network_mode": "bridge",
            "allow_host_desktop": False,
            "close_on_session_end": True,
        },
        "manifest_path": _gui_manifest_path(profile),
        "launcher_ref": _gui_launcher_ref(profile),
        "app_profile": _gui_app_profile(profile),
        "launch_target_command": _gui_launch_target_command(profile),
        "verification_ref": gui_verification_ref(gui_id),
        "notes": [
            "Agents must operate this GUI through the container noVNC endpoint and OpenClaw browser control.",
            "macOS host desktop automation, PeekabooBridge, and OS Accessibility permissions are not part of this canonical path.",
        ],
    }


def _gui_rework_verification_payload(profile: dict) -> dict:
    gui_id = _gui_env_id(profile)
    gui_ref = gui_session_ref(gui_id)
    return {
        "verification_report_id": gui_verification_payload_id(gui_id),
        "schema_version": "1.0.0",
        "outcome": "REWORK",
        "reasons": [
            f"GUI session {gui_id} is generated and linked, but the sibling noVNC/OpenClaw image has not yet been built and smoke-verified in this workspace."
        ],
        "blocking_findings": [
            {
                "code": "gui_session_not_verified",
                "severity": "medium",
                "artifact_ref": gui_ref,
            }
        ],
        "gate_results": [
            {
                "gate_id": "container_gui_healthcheck",
                "gate_kind": "tests",
                "status": "FAIL",
                "detail": f"Run python scripts/bootstrap_knowledge_gui_runtime.py --gui-session-ref {gui_ref} and then python scripts/verify_knowledge_gui_runtime.py --gui-session-ref {gui_ref}.",
                "remediation_hint": "Build the sibling GUI image and verify Xvfb, noVNC, loopback binding, screenshot capture, and OpenClaw browser access.",
                "artifact_ref": gui_ref,
            }
        ],
        "recommended_next_action": "build_and_verify_container_gui_session",
        "validated_artifact_refs": [gui_ref, artifact_ref("environment-spec", gui_id)],
        "created_at": SEED_TS,
    }


def build_gui_session_artifacts(
    existing_verification_payloads: dict[str, dict[str, object]] | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    existing_verification_payloads = existing_verification_payloads or {}
    gui_env_records: list[dict] = []
    gui_session_records: list[dict] = []
    gui_verification_records: list[dict] = []
    for profile in _base_docker_profiles():
        gui_id = _gui_env_id(profile)
        gui_payload = _gui_session_payload(profile)
        gui_env_payload = _gui_environment_payload(profile)
        gui_ref = gui_session_ref(gui_id)
        gui_env_ref = artifact_ref("environment-spec", gui_id)
        verification_id = gui_verification_payload_id(gui_id)
        verification_payload = existing_verification_payloads.get(verification_id) or _gui_rework_verification_payload(profile)
        if verification_payload.get("outcome") == "PASS":
            gui_env_payload["gui_capability_state"] = "VERIFIED_CONTAINER_GUI"
        gui_env_records.append(
            typed_record("environment-spec", "ENVIRONMENT_SPEC", gui_id, gui_env_payload, [gui_ref])
        )
        gui_session_records.append(
            typed_record(
                "gui-session-spec",
                "GUI_SESSION_SPEC",
                gui_id,
                gui_payload,
                [artifact_ref("environment-spec", profile["id"]), gui_env_ref],
            )
        )
        gui_verification_records.append(
            typed_record(
                "verification-report",
                "VERIFICATION_REPORT",
                verification_id,
                verification_payload,
                [gui_ref, gui_env_ref],
            )
        )
    return gui_env_records, gui_session_records, gui_verification_records


def _phase2_pack_verification_id(slug: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"phase2-pack-verification:{slug}"))


def _phase2_pack_verification_ref(slug: str) -> str:
    return artifact_ref("verification-report", _phase2_pack_verification_id(slug))


def _phase2_registry_module(module: dict, *, metadata: dict[str, object] | None, inventory_visible: bool) -> dict:
    link_status = _phase2_link_status_for_module(module, metadata)
    env_map = _phase2_environment_refs_map()
    if module["implementation_status"] == "implemented":
        env_refs = list(
            module.get(
                "environment_refs",
                env_refs_for_module(module) if "runtime_profile" in module else [],
            )
        )
        preferred_env_ref = module.get(
            "preferred_environment_ref",
            primary_env_ref(module) if "runtime_profile" in module else env_refs[0],
        )
        alias_names = list(module.get("alias_names", []))
        substitution_note = module.get("substitution_note")
        bindings = list(module["bindings"])
    else:
        env_refs = list(module.get("environment_refs", env_map[module["slug"]]))
        preferred_env_ref = module.get("preferred_environment_ref", env_refs[0])
        alias_names = list(module.get("alias_names", []))
        substitution_note = module.get("substitution_note")
        bindings = list(module.get("bindings", _phase2_default_bindings(module, metadata)))
    solves, not_for = _phase2_scope_for_module(module)
    canonical_pack_slug = PHASE2_SUBSTITUTIONS.get(module["slug"], {}).get("knowledge_pack_slug", module["slug"])
    return {
        "slug": module["slug"],
        "knowledge_pack_slug": canonical_pack_slug,
        "name": module["name"],
        "category": module["category"],
        "module_class": module["module_class"],
        "source_refs": list(module["source_refs"]),
        "bindings": bindings,
        "solves": solves,
        "best_for": list(module.get("best_for", [f"{module['name']} inside {_phase2_domain_label(module['category'])}"])),
        "not_for": not_for,
        "import_target": module.get("import_target", module["slug"]),
        "related": list(module.get("related", [])),
        "environment_refs": env_refs,
        "preferred_environment_ref": preferred_env_ref,
        "implementation_status": module["implementation_status"],
        "inventory_visible": inventory_visible,
        "phase2_link_status": link_status if inventory_visible else module.get("phase2_link_status", "detailed_linked_runtime_gated"),
        "phase2_gate_mode": (
            "pass"
            if (link_status == "recommendable" if inventory_visible else module.get("phase2_gate_mode") == "pass")
            else "rework"
        ),
        "phase2_gate_reason": module.get("phase2_gate_reason") or module.get("excluded_reason"),
        "alias_names": alias_names,
        "substitution_note": substitution_note,
        "family_pack_slug": _phase2_family_pack_slug(module["slug"], metadata),
        "inventory_alias_resolution_kind": (
            "substituted_by_canonical_pack"
            if module["slug"] in PHASE2_SUBSTITUTIONS
            else "self"
        ),
        "inventory_canonical_tool_name": PHASE2_SUBSTITUTIONS.get(module["slug"], {}).get("canonical_tool_name", module["name"]),
    }


def _canonical_module_registry() -> list[dict]:
    modules: list[dict] = []
    for module in IMPLEMENTED_MODULES:
        modules.append(_phase2_registry_module(module, metadata=None, inventory_visible=True))
    for module in EXCLUDED_MODULES:
        if module["slug"] == "pardiso":
            continue
        modules.append(
            _phase2_registry_module(
                module,
                metadata=recovery_metadata_for_excluded(module),
                inventory_visible=True,
            )
        )
    for module in PHASE2_SYNTHETIC_MODULES:
        modules.append(_phase2_registry_module(module, metadata=None, inventory_visible=False))
    return modules


def runtime_profile_map() -> dict[str, dict]:
    return {item["id"]: item for item in _all_runtime_profiles()}


def excluded_environment_refs(module: dict) -> list[str]:
    return list(_phase2_environment_refs_map().get(module["slug"], []))


def build_environment_specs(
    existing_verification_payloads: dict[str, dict[str, object]] | None = None,
) -> tuple[list[dict], list[dict]]:
    environment_records: list[dict] = []
    verification_records: list[dict] = []
    existing_verification_payloads = existing_verification_payloads or {}
    for profile in _all_runtime_profiles():
        payload = {
            "environment_spec_id": profile["id"],
            "schema_version": "1.0.0",
            "runtime_profile": profile["runtime_profile"],
            "delivery_kind": profile["delivery_kind"],
            "docker_platform": profile.get("docker_platform"),
            "gui_session_refs": profile.get("gui_session_refs", []),
            "default_gui_session_ref": profile.get("default_gui_session_ref"),
            "gui_capability_state": profile.get(
                "gui_capability_state",
                "API_ONLY_HOST_PATH" if profile["delivery_kind"] == "host_app" else "NO_GUI",
            ),
            "module_ids": profile["module_ids"],
            "supported_host_platforms": profile["supported_host_platforms"],
            "manifest_format": profile["manifest_format"],
            "manifest_path": profile["manifest_path"],
            "runtime_locator": profile["runtime_locator"],
            "bootstrap_command": profile["bootstrap_command"],
            "healthcheck_command": profile["healthcheck_command"],
            "launcher_ref": profile["launcher_ref"],
            "notes": profile["notes"],
        }
        env_ref = artifact_ref("environment-spec", profile["id"])
        environment_records.append(
            typed_record("environment-spec", "ENVIRONMENT_SPEC", profile["id"], payload, [])
        )
        verification_id = verification_payload_id(profile["id"])
        existing_payload = existing_verification_payloads.get(verification_id)
        if existing_payload and env_ref in existing_payload.get("validated_artifact_refs", []):
            verification_records.append(
                typed_record(
                    "verification-report",
                    "VERIFICATION_REPORT",
                    verification_id,
                    existing_payload,
                    [env_ref],
                )
            )
            continue
        if profile["verification_enabled"]:
            verification_records.append(
                typed_record(
                    "verification-report",
                    "VERIFICATION_REPORT",
                    verification_id,
                    {
                        "verification_report_id": verification_id,
                        "schema_version": "1.0.0",
                        "outcome": "PASS",
                        "reasons": profile.get(
                            "verification_reasons",
                            [f"Seeded runtime profile {profile['runtime_profile']} passed its linked health check during this sprint."],
                        ),
                        "gate_results": [
                            {
                                "gate_id": "runtime_healthcheck",
                                "gate_kind": "tests",
                                "status": "PASS",
                                "detail": profile.get("verification_detail", profile["healthcheck_command"]),
                                "artifact_ref": env_ref,
                            }
                        ],
                        "recommended_next_action": "accept_runtime_environment",
                        "validated_artifact_refs": [env_ref],
                        "created_at": SEED_TS,
                    },
                    [env_ref],
                )
            )
            continue
        reason = profile.get(
            "runtime_gate_reason",
            f"Runtime manifest exists for {profile['runtime_profile']}, but it has not been verified in this sprint.",
        )
        verification_records.append(
            typed_record(
                "verification-report",
                "VERIFICATION_REPORT",
                verification_id,
                {
                    "verification_report_id": verification_id,
                    "schema_version": "1.0.0",
                    "outcome": "REWORK",
                    "reasons": [reason],
                    "blocking_findings": [
                        {
                            "code": "runtime_verification_pending",
                            "severity": "high",
                            "artifact_ref": env_ref,
                        }
                    ],
                    "gate_results": [
                        {
                            "gate_id": "runtime_healthcheck",
                            "gate_kind": "tests",
                            "status": "FAIL",
                            "detail": profile.get("verification_detail", profile["healthcheck_command"]),
                            "remediation_hint": "Bootstrap or finish the canonical runtime build before promoting this environment.",
                            "artifact_ref": env_ref,
                        }
                    ],
                    "recommended_next_action": "repair_runtime_environment",
                    "validated_artifact_refs": [env_ref],
                    "created_at": SEED_TS,
                },
                [env_ref],
            )
        )
    return environment_records, verification_records


def _phase2_pack_verification_payload(
    module: dict,
    pack_ref: str,
    existing_verification_payloads: dict[str, dict[str, object]] | None = None,
) -> dict:
    verification_id = _phase2_pack_verification_id(module["knowledge_pack_slug"])
    validated_refs = list(module["environment_refs"])
    existing_payload = (existing_verification_payloads or {}).get(verification_id)
    if existing_payload and set(existing_payload.get("validated_artifact_refs", [])) & set(validated_refs):
        return existing_payload
    if module["phase2_gate_mode"] == "pass":
        return {
            "verification_report_id": verification_id,
            "schema_version": "1.0.0",
            "outcome": "PASS",
            "reasons": [f"{module['name']} is fully linked to a passing runtime path in this sprint."],
            "gate_results": [
                {
                    "gate_id": "phase2_pack_gate",
                    "gate_kind": "tests",
                    "status": "PASS",
                    "detail": f"Pack {module['knowledge_pack_slug']} is linked to verified runtime refs {', '.join(validated_refs)}.",
                    "artifact_ref": pack_ref,
                }
            ],
            "recommended_next_action": "accept_runtime_environment",
            "validated_artifact_refs": validated_refs,
            "created_at": SEED_TS,
        }
    return {
        "verification_report_id": verification_id,
        "schema_version": "1.0.0",
        "outcome": "REWORK",
        "reasons": [module["phase2_gate_reason"] or f"{module['name']} remains runtime-gated."],
        "blocking_findings": [
            {
                "code": "phase2_runtime_gate",
                "severity": "high",
                "artifact_ref": pack_ref,
            }
        ],
        "gate_results": [
            {
                "gate_id": "phase2_pack_gate",
                "gate_kind": "tests",
                "status": "FAIL",
                "detail": module["phase2_gate_reason"] or f"{module['name']} remains runtime-gated.",
                "remediation_hint": "Satisfy the runtime gate and regenerate the linked verification report.",
                "artifact_ref": pack_ref,
            }
        ],
        "recommended_next_action": "repair_runtime_environment",
        "validated_artifact_refs": validated_refs,
        "created_at": SEED_TS,
    }


def package_completion_ref(slug: str) -> str:
    return f"package-completion://{slug}"


def package_smoke_case_ref(slug: str) -> str:
    return f"package-smoke://{slug}"


def _phase3_pack_ref_for_slug(slug: str) -> str:
    alias_data = PHASE2_SUBSTITUTIONS.get(slug)
    identifier = alias_data["knowledge_pack_slug"] if alias_data else slug
    return artifact_ref("knowledge-pack", identifier)


def _phase3_parent_slugs_for_module(module: dict, metadata: dict[str, object] | None) -> list[str]:
    parents: list[str] = []
    if module["slug"] in PHASE2_SUBSTITUTIONS:
        alias_identifier = PHASE2_SUBSTITUTIONS[module["slug"]]["knowledge_pack_slug"]
        if alias_identifier in {item["slug"] for item in EXCLUDED_MODULES}:
            parents.append(alias_identifier)
    if metadata is None:
        return parents
    for ref in list(metadata.get("blocked_by_refs", [])) + list(metadata.get("parent_runtime_refs", [])):
        if isinstance(ref, str) and ref.startswith("minutes-module://"):
            slug = ref.split("://", 1)[1]
            if slug in {item["slug"] for item in EXCLUDED_MODULES}:
                parents.append(slug)
    return sorted(dict.fromkeys(parents))


def _phase3_completion_kind(module: dict, metadata: dict[str, object] | None) -> str:
    if module["slug"] in PHASE3_PROMOTED_RECOVERY_SLUGS:
        return "closure"
    if module["slug"] in PHASE2_SUBSTITUTIONS:
        return "alias"
    if metadata and metadata.get("manual_acquisition_required"):
        return "manual_acquisition"
    if metadata and metadata.get("install_method_category") == "I4_host_companion_wrapper":
        return "child_wrapper"
    if metadata and metadata.get("install_method_category") == "I5_knowledge_only_standard":
        return "standard_binding"
    return "root_runtime"


def _phase3_completion_status(
    module: dict,
    metadata: dict[str, object] | None,
    existing_state: dict[str, object] | None = None,
) -> str:
    if existing_state:
        status = existing_state.get("status")
        if isinstance(status, str):
            return status
    if module["implementation_status"] == "implemented":
        return "promoted"
    if module["slug"] in PHASE3_PROMOTED_RECOVERY_SLUGS:
        return "promoted"
    if metadata and metadata.get("manual_acquisition_required"):
        return "blocked_external"
    acquisition_status = str(metadata.get("acquisition_status", "")) if metadata else ""
    cli_phase1_status = str(metadata.get("cli_phase1_status", "")) if metadata else ""
    if cli_phase1_status == "installed" and acquisition_status.endswith("parent_pending"):
        return "smoke_verified"
    return "queued"


def _phase3_phase_state(
    module: dict,
    metadata: dict[str, object] | None,
    completion_status: str | None = None,
) -> str:
    if completion_status == "promoted":
        return "linked"
    if completion_status in {"blocked_runtime", "blocked_smoke"}:
        return "installed"
    if completion_status == "blocked_external":
        return "deferred"
    if module["implementation_status"] == "implemented":
        return "linked"
    if module["slug"] in PHASE3_PROMOTED_RECOVERY_SLUGS:
        return "linked"
    if metadata is None:
        return "planned"
    return str(metadata["phase_state"])


def _phase3_phase_target(
    module: dict,
    metadata: dict[str, object] | None,
    completion_status: str | None = None,
) -> str:
    if completion_status == "promoted":
        return "completed"
    if completion_status in {"blocked_runtime", "blocked_smoke"}:
        return "phase3b"
    if module["implementation_status"] == "implemented":
        return "completed"
    if module["slug"] in PHASE3_PROMOTED_RECOVERY_SLUGS:
        return "completed"
    if metadata is None:
        return "phase1"
    return str(metadata["phase_target"])


def _phase3_inventory_status(
    module: dict,
    completion_status: str | None = None,
) -> str:
    if completion_status == "promoted":
        return "implemented"
    if module["implementation_status"] == "implemented":
        return "implemented"
    if module["slug"] in PHASE3_PROMOTED_RECOVERY_SLUGS:
        return "implemented"
    return "excluded"


def _phase3_promotion_ready(
    module: dict,
    metadata: dict[str, object] | None,
    existing_state: dict[str, object] | None = None,
) -> bool:
    return _phase3_completion_status(module, metadata, existing_state) == "promoted"


def _inventory_acquisition_status(
    metadata: dict[str, object] | None,
    completion_status: str | None = None,
) -> str:
    if metadata is None:
        return "not_required"
    acquisition_status = str(metadata.get("acquisition_status", "not_required"))
    if completion_status == "promoted" and acquisition_status.endswith("parent_pending"):
        return "verified_in_knowledge_runtime"
    return acquisition_status


def _phase3_manual_artifact_path(module: dict) -> str | None:
    return {
        "femm": "knowledge/coding-tools/runtime/manual/femm/femm-installer.exe",
        "pyleecan": "knowledge/coding-tools/runtime/manual/pyleecan/swat-em-source",
        "ma87": "HSL/ma87",
    }.get(module["slug"])


def _phase3_acquisition_source(module: dict, metadata: dict[str, object] | None, preferred_env_ref: str) -> str:
    if module["slug"] == "rhino_common":
        return "host_app:/Applications/Rhino 8.app"
    cli_channel = str(metadata.get("cli_install_channel", "")) if metadata else ""
    if module["slug"] == "picogk_shapekernel":
        return "dotnet_nuget:PicoGK"
    if cli_channel == "docker_build_with_local_hsl":
        return "local_hsl_staging:HSL/coinhsl-2024.05.15"
    if cli_channel == "docker_build_with_onemkl":
        return "checked_in_docker_manifest:intel_onemkl_container"
    if cli_channel == "docker_build":
        return "checked_in_docker_manifest"
    if cli_channel in {"uv_pip", "uv_pip_after_parent_runtime", "uv_pip_with_url_dependency"}:
        return "checked_in_uv_manifest"
    if cli_channel == "knowledge_only":
        return "knowledge_bound_runtime_mapping"
    if cli_channel == "wine_installer_after_download":
        return "external_windows_installer"
    if cli_channel == "licensed_binary_delivery":
        return "licensed_binary_delivery"
    if cli_channel == "host_app_cli":
        return "host_app:/Applications/Rhino 8.app"
    if preferred_env_ref == "artifact://environment-spec/eng_dotnet_sdk":
        return "dotnet_toolchain"
    return "runtime_manifest"


def _phase3_promotion_reason(
    module: dict,
    metadata: dict[str, object] | None,
    completion_status: str,
    parent_package_refs: list[str],
    existing_state: dict[str, object] | None = None,
) -> str:
    if existing_state:
        failure_summary = existing_state.get("last_failure_summary")
        if completion_status in {"blocked_runtime", "blocked_smoke"} and isinstance(failure_summary, str) and failure_summary:
            return failure_summary
    if completion_status == "promoted":
        if module["implementation_status"] == "implemented":
            return f"{module['name']} was already part of the implemented runtime-linked baseline and stays promoted in Phase 3."
        return f"{module['name']} already had a passing runtime-linked verification path, so Phase 3 closes and promotes the prior recovery row."
    if completion_status == "blocked_external":
        return module.get("excluded_reason") or f"{module['name']} is waiting on an external acquisition artifact."
    if completion_status == "smoke_verified":
        return (
            f"{module['name']} has a package-local runtime probe, but promotion is still blocked on parent completion for "
            f"{', '.join(parent_package_refs)}."
        )
    if module["slug"] in PHASE2_SUBSTITUTIONS:
        return f"{module['name']} promotes only through the canonical {PHASE2_SUBSTITUTIONS[module['slug']]['canonical_tool_name']} runtime path."
    if parent_package_refs:
        return f"{module['name']} is queued behind parent completion for {', '.join(parent_package_refs)}."
    return f"{module['name']} is queued for canonical runtime bootstrap, healthcheck, smoke verification, and promotion."


def _phase3_smoke_command(module_slug: str, knowledge_pack_ref: str) -> str:
    return (
        "python scripts/run_knowledge_package_smoke.py "
        f"--module-slug {module_slug} --knowledge-pack-ref {knowledge_pack_ref}"
    )


def build_seed_files() -> None:
    packs: list[dict] = []
    recipes: list[dict] = []
    adapters: list[dict] = []
    evidence_bundles: list[dict] = []
    decisions: list[dict] = []
    phase3_state_by_slug = load_existing_phase3_ledger_state()
    existing_verification_payloads = load_existing_verification_payloads()

    excluded_slugs = {module["slug"] for module in EXCLUDED_MODULES}
    missing_recovery_metadata = sorted(excluded_slugs - set(RECOVERY_METADATA_BY_SLUG))
    if missing_recovery_metadata:
        raise ValueError(f"Missing recovery metadata for excluded modules: {missing_recovery_metadata}")
    deferred_slugs = {
        slug
        for slug, metadata in RECOVERY_METADATA_BY_SLUG.items()
        if metadata["install_method_category"] == "I6_deferred_external_manual"
    }
    missing_dossiers = sorted(deferred_slugs - set(DEFERRED_ACQUISITION_DETAILS))
    if missing_dossiers:
        raise ValueError(f"Missing deferred acquisition dossiers for modules: {missing_dossiers}")

    env_records, verification_records = build_environment_specs(existing_verification_payloads)
    gui_env_records, gui_session_records, gui_verification_records = build_gui_session_artifacts(
        existing_verification_payloads
    )
    gui_session_by_base_env_ref = {
        record["payload"]["base_environment_ref"]: artifact_ref(
            "gui-session-spec",
            record["payload"]["gui_session_spec_id"],
        )
        for record in gui_session_records
    }
    gui_verification_by_session_ref = {
        artifact_ref("gui-session-spec", record["payload"]["gui_session_spec_id"]): record["payload"]["verification_ref"]
        for record in gui_session_records
    }
    for record in env_records:
        payload = record["payload"]
        env_ref = artifact_ref("environment-spec", payload["environment_spec_id"])
        gui_ref = gui_session_by_base_env_ref.get(env_ref)
        if gui_ref:
            payload["gui_session_refs"] = [gui_ref]
            payload["default_gui_session_ref"] = gui_ref
            payload["gui_capability_state"] = (
                "VERIFIED_CONTAINER_GUI"
                if existing_verification_payloads.get(gui_verification_by_session_ref[gui_ref].rsplit("/", 1)[-1], {}).get("outcome") == "PASS"
                else "PLANNED_CONTAINER_GUI"
            )
    env_records.extend(gui_env_records)
    verification_records.extend(gui_verification_records)
    env_payload_by_ref = {
        artifact_ref("environment-spec", record["payload"]["environment_spec_id"]): record["payload"]
        for record in env_records
    }
    decision_index = decision_refs_by_slug()
    modules = _canonical_module_registry()

    for module in modules:
        slug = module["knowledge_pack_slug"]
        pack_ref = artifact_ref("knowledge-pack", slug)
        recipe_id = f"{slug}_{module['category']}"
        recipe_ref = artifact_ref("recipe-object", recipe_id)
        adapter_id = f"{slug}_probe"
        adapter_ref = artifact_ref("execution-adapter-spec", adapter_id)
        evidence_id = f"{slug}_runtime"
        evidence_ref = artifact_ref("evidence-bundle", evidence_id)
        runtime_verification_ref = _phase2_pack_verification_ref(slug)
        family_pack_slug = module.get("family_pack_slug")
        integration_refs = sorted(
            set(
                [artifact_ref("knowledge-pack", related) for related in module["related"]]
                + decision_index.get(module["slug"], [])
                + (
                    [artifact_ref("knowledge-pack", family_pack_slug)]
                    if family_pack_slug and family_pack_slug != slug
                    else []
                )
                + (
                    [artifact_ref("knowledge-pack", "onemkl")]
                    if module["slug"] == "ipopt"
                    else []
                )
                + (
                    [artifact_ref("knowledge-pack", "coinhsl_family")]
                    if module["slug"] in {"ipopt", "ma57", "ma77", "ma86", "ma87", "ma97"}
                    else []
                )
            )
        )
        preferred_env_ref = module["preferred_environment_ref"]
        probe_command = (
            f"python scripts/verify_knowledge_runtime.py --environment-ref {preferred_env_ref}"
        )
        core_objects = _phase2_core_objects(module, preferred_env_ref)
        anti_patterns = _phase2_anti_patterns(module, preferred_env_ref, module.get("substitution_note"))
        recipe_pattern = _phase2_recipe_pattern(module, preferred_env_ref, module["phase2_link_status"])
        failure_signatures = _phase2_failure_signatures(module, module["phase2_link_status"])
        reviewer_checklist = _phase2_reviewer_checklist(module, module["phase2_link_status"])
        interfaces_inputs = [
            f"Typed engineering inputs for {module['name']}",
            f"Declared runtime target {preferred_env_ref}",
        ]
        interfaces_outputs = [
            f"{module['name']} runtime probe output",
            f"{module['name']} task artifact with linked evidence refs",
        ]

        pack_payload = {
            "knowledge_pack_id": f"{slug}_pack",
            "schema_version": "1.0.0",
            "tool_id": slug,
            "tool_name": module["name"],
            "module_class": module["module_class"],
            "library_version": "current-curated",
            "bindings": module["bindings"],
            "scope": {
                "solves": module["solves"],
                "not_for": module["not_for"],
            },
            "core_objects": core_objects,
            "best_for": module["best_for"],
            "anti_patterns": anti_patterns,
            "interfaces": {
                "inputs": interfaces_inputs,
                "outputs": interfaces_outputs,
            },
            "integration_refs": integration_refs,
            "recipe_refs": [recipe_ref],
            "adapter_refs": [adapter_ref],
            "evidence_refs": [evidence_ref],
            "minutes_source_refs": module["source_refs"],
            "environment_refs": module["environment_refs"],
            "alias_names": module.get("alias_names", []),
            "substitution_note": module.get("substitution_note"),
            "excluded_reason": None if module["implementation_status"] == "implemented" else module["phase2_gate_reason"],
            "provenance": {
                "sources": module["source_refs"],
                "examples": module["solves"],
                "benchmarks": module["best_for"],
            },
        }
        packs.append(
            typed_record(
                "knowledge-pack",
                "KNOWLEDGE_PACK",
                slug,
                pack_payload,
                list(module["environment_refs"]),
            )
        )

        recipe_payload = {
            "recipe_id": recipe_id,
            "schema_version": "1.0.0",
            "title": f"{module['name']} phase 2 runtime-linked recipe",
            "task_class": module["category"],
            "assumptions": [
                f"The canonical runtime path for {module['name']} is {preferred_env_ref}.",
                f"The current Phase 2 link status is {module['phase2_link_status']}.",
            ],
            "why_this_stack": f"Use {module['name']} when {module['solves'][0].lower()} is the right fit and the linked runtime path must remain explicit.",
            "knowledge_pack_ref": pack_ref,
            "touched_objects": [
                {
                    "name": item["name"],
                    "role": item["role"],
                    "notes": f"Phase 2 tracks this {module['name']} surface through the linked runtime and evidence path.",
                }
                for item in core_objects
            ],
            "implementation_pattern": recipe_pattern,
            "required_inputs": [
                f"Typed problem inputs for {module['name']}",
                f"Resolved environment spec {preferred_env_ref}",
                "Declared units where engineering values cross the adapter boundary",
            ],
            "required_outputs": [
                f"{module['name']} runtime probe output",
                f"{module['name']} task artifact with provenance and evidence refs",
            ],
            "failure_signatures": failure_signatures,
            "acceptance_tests": [
                f"{module['name']} pack resolves a concrete environment spec",
                f"{module['name']} evidence bundle references the Phase 2 runtime verification report",
                f"{module['name']} recipe preserves explicit provenance and gate status",
            ],
            "adapter_refs": [adapter_ref],
            "evidence_refs": [evidence_ref],
        }
        recipes.append(typed_record("recipe-object", "RECIPE_OBJECT", recipe_id, recipe_payload, [pack_ref]))

        adapter_payload = {
            "adapter_spec_id": adapter_id,
            "schema_version": "1.0.0",
            "tool_id": slug,
            "supported_library_version": "current-curated",
            "knowledge_pack_ref": pack_ref,
            "preferred_environment_ref": preferred_env_ref,
            "environment_refs": module["environment_refs"],
            "callable_interface": {
                "kind": "cli" if preferred_env_ref != "artifact://environment-spec/eng_rhino_host" else "dotnet",
                "entrypoint": probe_command,
                "signature": f"probe_{slug}() -> verification_report",
            },
            "typed_inputs": [
                {"name": "working_dir", "type": "path", "required": False, "unit": None},
                {"name": "problem", "type": "object", "required": False, "unit": None},
            ],
            "typed_outputs": [
                {"name": "probe_stdout", "type": "string", "unit": None},
                {"name": "runtime_gate_state", "type": "string", "unit": None},
            ],
            "unit_policy": {
                "unit_system": "SI",
                "require_declared_units": True,
                "notes": f"{module['name']} adapter inputs remain unit-declared whenever engineering values cross the runtime boundary.",
            },
            "file_translators": (
                [{"from": "problem_spec", "to": "runtime_input", "notes": f"Translate typed problem input into the {module['name']} runtime boundary."}]
                if module["module_class"] in {"integration_layer", "translator", "standard"}
                else []
            ),
            "runtime_requirements": [
                f"Resolve {preferred_env_ref} before invoking {module['name']}.",
                f"Honor the Phase 2 gate state {module['phase2_link_status']} before promoting downstream outputs.",
            ],
            "healthcheck_refs": [runtime_verification_ref],
            "safety_limits": [
                f"Do not promote {module['name']} outputs when the linked verification report outcome is REWORK.",
                f"Keep {module['name']} inside its declared capability boundary.",
            ],
            "emitted_artifact_refs": [runtime_verification_ref],
            "launcher_ref": runtime_profile_map()[preferred_env_ref.split("/")[-1]]["launcher_ref"],
        }
        adapters.append(
            typed_record(
                "execution-adapter-spec",
                "EXECUTION_ADAPTER_SPEC",
                adapter_id,
                adapter_payload,
                [pack_ref, preferred_env_ref],
            )
        )

        evidence_payload = {
            "evidence_bundle_id": evidence_id,
            "schema_version": "1.0.0",
            "title": f"{module['name']} phase 2 verification bundle",
            "tool_id": slug,
            "knowledge_pack_ref": pack_ref,
            "recipe_refs": [recipe_ref],
            "adapter_refs": [adapter_ref],
            "smoke_tests": [
                f"Probe {module['name']} through {preferred_env_ref}",
                f"Confirm the current Phase 2 gate state for {module['name']}",
            ],
            "benchmark_cases": module["solves"],
            "expected_outputs": [
                f"{module['name']} exposes a concrete runtime path",
                f"{module['name']} surfaces a deterministic gate state for downstream agents",
            ],
            "tolerances": [
                f"{module['name']} must keep runtime provenance explicit",
                f"{module['name']} must not hide its current gate state",
            ],
            "convergence_criteria": [
                f"The Phase 2 verification report for {module['name']} is linked and readable",
            ],
            "reviewer_checklist": reviewer_checklist,
            "runtime_verification_refs": [runtime_verification_ref],
            "healthcheck_commands": [probe_command],
            "reference_artifact_refs": [runtime_verification_ref],
            "provenance": {
                "sources": module["source_refs"],
                "benchmarks": module["best_for"],
            },
        }
        evidence_bundles.append(
            typed_record(
                "evidence-bundle",
                "EVIDENCE_BUNDLE",
                evidence_id,
                evidence_payload,
                [pack_ref, recipe_ref, adapter_ref, preferred_env_ref],
            )
        )

        verification_records.append(
            typed_record(
                "verification-report",
                "VERIFICATION_REPORT",
                _phase2_pack_verification_id(slug),
                _phase2_pack_verification_payload(module, pack_ref, existing_verification_payloads),
                [pack_ref, *module["environment_refs"]],
            )
        )

    for item in DECISIONS:
        decisions.append(
            typed_record(
                "decision-log",
                "DECISION_LOG",
                item["decision_id"],
                {
                    "decision_id": item["decision_id"],
                    "schema_version": "1.0.0",
                    "title": item["title"],
                    "statement": item["statement"],
                    "rationale": item["rationale"],
                    "chosen_refs": item["chosen_refs"],
                    "rejected_refs": item["rejected_refs"],
                    "tradeoffs": item["tradeoffs"],
                    "status": item["status"],
                },
                sorted(set(item["chosen_refs"] + item["rejected_refs"])),
            )
        )

    write_json(OUTPUT_ROOT / "substrate" / "knowledge-packs.json", packs)
    write_json(OUTPUT_ROOT / "substrate" / "recipe-objects.json", recipes)
    write_json(OUTPUT_ROOT / "substrate" / "decision-logs.json", decisions)
    write_json(OUTPUT_ROOT / "environments" / "environment-specs.json", env_records)
    write_json(GUI_ROOT / "gui-session-specs.json", gui_session_records)
    write_json(OUTPUT_ROOT / "adapters" / "execution-adapter-specs.json", adapters)
    write_json(OUTPUT_ROOT / "evidence" / "evidence-bundles.json", evidence_bundles)
    write_json(OUTPUT_ROOT / "evidence" / "verification-reports.json", verification_records)

    registry_by_slug = {module["slug"]: module for module in modules if module["inventory_visible"]}
    registry_by_pack_slug = {module["knowledge_pack_slug"]: module for module in modules}
    inventory_entries: list[dict] = []
    for module in IMPLEMENTED_MODULES:
        entry_module = registry_by_slug[module["slug"]]
        inventory_entries.append(
            {
                "name": module["name"],
                "slug": module["slug"],
                "module_ref": minutes_module_ref(module["slug"]),
                "category": module["category"],
                "module_class": module["module_class"],
                "minutes_source_refs": module["source_refs"],
                "executable": True,
                "implementation_status": "implemented",
                "knowledge_pack_ref": artifact_ref("knowledge-pack", entry_module["knowledge_pack_slug"]),
                "environment_refs": entry_module["environment_refs"],
                "excluded_reason": None,
                "phase2_link_status": "recommendable",
                "alias_resolution_kind": "self",
                "canonical_tool_name": module["name"],
                "phase3_completion_status": "promoted",
                "phase3_primary_runtime_ref": entry_module["preferred_environment_ref"],
                "phase3_parent_completion_refs": [],
                "phase3_smoke_case_ref": package_smoke_case_ref(module["slug"]),
                "promotion_ready": True,
                **completed_inventory_metadata(module),
            }
        )
    for module in EXCLUDED_MODULES:
        metadata = recovery_metadata_for_excluded(module)
        phase3_state = phase3_state_by_slug.get(module["slug"])
        alias_data = PHASE2_SUBSTITUTIONS.get(module["slug"])
        entry_module = registry_by_slug[module["slug"]] if module["slug"] in registry_by_slug else None
        canonical_module = (
            registry_by_pack_slug.get(alias_data["knowledge_pack_slug"])
            if alias_data
            else entry_module
        )
        phase3_completion_status = _phase3_completion_status(module, metadata, phase3_state)
        phase2_link_status = (
            "recommendable"
            if phase3_completion_status == "promoted"
            else canonical_module["phase2_link_status"]
            if canonical_module is not None
            else "unlinked"
        )
        inventory_status = _phase3_inventory_status(module, phase3_completion_status)
        phase3_primary_runtime_ref = excluded_environment_refs(module)[0]
        phase3_parent_completion_refs = [
            package_completion_ref(parent_slug)
            for parent_slug in _phase3_parent_slugs_for_module(module, metadata)
        ]
        failure_summary = (
            str(phase3_state.get("last_failure_summary"))
            if phase3_state and phase3_state.get("last_failure_summary")
            else None
        )
        inventory_entries.append(
            {
                "name": module["name"],
                "slug": module["slug"],
                "module_ref": minutes_module_ref(module["slug"]),
                "category": module["category"],
                "module_class": module["module_class"],
                "minutes_source_refs": module["source_refs"],
                "executable": module["executable"],
                "implementation_status": inventory_status,
                "knowledge_pack_ref": (
                    artifact_ref("knowledge-pack", alias_data["knowledge_pack_slug"])
                    if alias_data
                    else artifact_ref("knowledge-pack", module["slug"])
                ),
                "environment_refs": excluded_environment_refs(module),
                "excluded_reason": (
                    None
                    if phase3_completion_status == "promoted"
                    else failure_summary or module["excluded_reason"]
                ),
                "phase2_link_status": phase2_link_status,
                "alias_resolution_kind": "substituted_by_canonical_pack" if alias_data else "self",
                "canonical_tool_name": alias_data["canonical_tool_name"] if alias_data else module["name"],
                "phase3_completion_status": phase3_completion_status,
                "phase3_primary_runtime_ref": phase3_primary_runtime_ref,
                "phase3_parent_completion_refs": phase3_parent_completion_refs,
                "phase3_smoke_case_ref": package_smoke_case_ref(module["slug"]),
                "promotion_ready": _phase3_promotion_ready(module, metadata, phase3_state),
                **{
                    **metadata,
                    "acquisition_status": _inventory_acquisition_status(metadata, phase3_completion_status),
                    "phase_target": _phase3_phase_target(module, metadata, phase3_completion_status),
                    "phase_state": _phase3_phase_state(module, metadata, phase3_completion_status),
                },
            }
        )
    inventory_entries = sorted(inventory_entries, key=lambda item: item["name"].lower())
    inventory_by_slug = {entry["slug"]: entry for entry in inventory_entries}

    phase3_order_index = {slug: idx for idx, slug in enumerate(PHASE3_EXECUTION_ORDER)}
    if set(phase3_order_index) != excluded_slugs:
        raise ValueError(
            "Phase 3 execution order must cover every recovery-bucket module exactly once"
        )
    excluded_modules_by_slug = {module["slug"]: module for module in EXCLUDED_MODULES}
    child_pack_refs_by_parent_slug = {slug: [] for slug in excluded_slugs}
    for module in EXCLUDED_MODULES:
        metadata = recovery_metadata_for_excluded(module)
        for parent_slug in _phase3_parent_slugs_for_module(module, metadata):
            if parent_slug in child_pack_refs_by_parent_slug:
                child_pack_refs_by_parent_slug[parent_slug].append(
                    _phase3_pack_ref_for_slug(module["slug"])
                )

    package_completion_entries: list[dict[str, object]] = []
    package_promotion_history_entries: list[dict[str, object]] = []
    for slug in PHASE3_EXECUTION_ORDER:
        module = excluded_modules_by_slug[slug]
        inventory_entry = inventory_by_slug[slug]
        metadata = recovery_metadata_for_excluded(module)
        phase3_state = phase3_state_by_slug.get(slug, {})
        canonical_runtime_ref = str(inventory_entry["phase3_primary_runtime_ref"])
        env_payload = env_payload_by_ref[canonical_runtime_ref]
        parent_pack_refs = [
            _phase3_pack_ref_for_slug(parent_slug)
            for parent_slug in _phase3_parent_slugs_for_module(module, metadata)
        ]
        child_pack_refs = sorted(dict.fromkeys(child_pack_refs_by_parent_slug.get(slug, [])))
        completion_status = str(inventory_entry["phase3_completion_status"])
        pack_ref = str(inventory_entry["knowledge_pack_ref"])
        package_completion_entries.append(
            {
                "completion_ref": package_completion_ref(slug),
                "smoke_case_ref": package_smoke_case_ref(slug),
                "execution_order": phase3_order_index[slug],
                "module_slug": slug,
                "knowledge_pack_ref": pack_ref,
                "completion_kind": _phase3_completion_kind(module, metadata),
                "canonical_runtime_ref": canonical_runtime_ref,
                "acquisition_source": _phase3_acquisition_source(module, metadata, canonical_runtime_ref),
                "bootstrap_command": env_payload["bootstrap_command"],
                "healthcheck_command": env_payload["healthcheck_command"],
                "smoke_command": _phase3_smoke_command(slug, pack_ref),
                "parent_package_refs": parent_pack_refs,
                "child_package_refs": child_pack_refs,
                "manual_artifact_path": _phase3_manual_artifact_path(module),
                "status": completion_status,
                "last_verification_ref": str(
                    phase3_state.get("last_verification_ref")
                    or _phase2_pack_verification_ref(pack_ref.split("/")[-1])
                ),
                "last_attempted_at": phase3_state.get("last_attempted_at"),
                "last_failure_stage": phase3_state.get("last_failure_stage"),
                "last_failure_summary": phase3_state.get("last_failure_summary"),
                "last_log_path": phase3_state.get("last_log_path"),
                "promotion_reason": _phase3_promotion_reason(
                    module,
                    metadata,
                    completion_status,
                    parent_pack_refs,
                    phase3_state,
                ),
            }
        )
        if completion_status == "promoted":
            package_promotion_history_entries.append(
                {
                    "completion_ref": package_completion_ref(slug),
                    "module_slug": slug,
                    "name": module["name"],
                    "knowledge_pack_ref": pack_ref,
                    "canonical_runtime_ref": canonical_runtime_ref,
                    "last_verification_ref": str(
                        phase3_state.get("last_verification_ref")
                        or _phase2_pack_verification_ref(pack_ref.split("/")[-1])
                    ),
                    "previous_inventory_status": "excluded",
                    "current_inventory_status": inventory_entry["implementation_status"],
                    "promotion_reason": _phase3_promotion_reason(
                        module,
                        metadata,
                        completion_status,
                        parent_pack_refs,
                        phase3_state,
                    ),
                    "recorded_at": str(phase3_state.get("last_attempted_at") or SEED_TS),
                }
            )

    excluded_entries = [
        entry for entry in inventory_entries if entry["implementation_status"] == "excluded"
    ]
    write_json(
        OUTPUT_ROOT / "substrate" / "minutes-inventory.json",
        {
            "schema_version": "1.0.0",
            "focus_area": "engineering",
            "source": "Normalized engineering sections from Conversation Minutes; Kimi/Gemma sections excluded.",
            "recovery_plan": build_recovery_plan_metadata(),
            "entries": inventory_entries,
        },
    )
    write_json(
        PACKAGE_COMPLETION_LEDGER_PATH,
        {
            "schema_version": "1.0.0",
            "source": "Derived from the normalized minutes inventory and Phase 3 package promotion model.",
            "entries": package_completion_entries,
        },
    )
    write_json(
        PACKAGE_PROMOTION_HISTORY_PATH,
        {
            "schema_version": "1.0.0",
            "source": "Recovery-bucket modules promoted out of the exclusion ledger during Phase 3 generation.",
            "entries": package_promotion_history_entries,
        },
    )
    write_text(EXCLUDED_PATH, render_excluded_ledger(excluded_entries))
    acquisition_dossiers_json, acquisition_dossiers_markdown = build_deferred_acquisition_dossiers(
        excluded_entries
    )
    write_json(ACQUISITION_DOSSIERS_JSON_PATH, acquisition_dossiers_json)
    write_text(ACQUISITION_DOSSIERS_MD_PATH, acquisition_dossiers_markdown)


def build_runtime_manifests() -> None:
    profile_by_id = runtime_profile_map()
    for profile in [item for item in _all_runtime_profiles() if item["delivery_kind"] == "uv_venv"]:
        requirement_lines = "\n".join(profile["requirements"]) + "\n"
        write_text(REPO_ROOT / profile["manifest_path"], requirement_lines)

    for profile in [item for item in _all_runtime_profiles() if item["delivery_kind"] == "docker_image"]:
        if "dockerfile_lines" in profile:
            dockerfile = "\n".join(profile["dockerfile_lines"])
        else:
            uv_peer_id = profile["id"].replace("_docker", "_uv")
            uv_peer = profile_by_id.get(uv_peer_id)
            if uv_peer is not None:
                dockerfile = "\n".join(
                    [
                        "FROM python:3.11-slim",
                        "WORKDIR /workspace",
                        f"COPY {uv_peer['manifest_path']} /tmp/requirements.txt",
                        "RUN python -m pip install --upgrade pip && python -m pip install -r /tmp/requirements.txt",
                        'ENTRYPOINT ["python"]',
                        "",
                    ]
                )
            else:
                dockerfile = "\n".join(
                    [
                        "FROM ubuntu:24.04",
                        "SHELL [\"/bin/bash\", \"-lc\"]",
                        "WORKDIR /workspace",
                        "RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends bash ca-certificates && rm -rf /var/lib/apt/lists/*",
                        "CMD [\"bash\"]",
                        "",
                    ]
                )
        write_text(REPO_ROOT / profile["manifest_path"], dockerfile)

    for profile in _all_runtime_profiles():
        if profile["delivery_kind"] == "uv_venv":
            launcher = "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    'ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"',
                    f'ENV_DIR="$ROOT/{profile["runtime_locator"]}"',
                    'exec "$ENV_DIR/bin/python" "$@"',
                    "",
                ]
            )
            write_text(REPO_ROOT / profile["launcher_ref"], launcher, executable=True)
            continue
        if profile["delivery_kind"] == "docker_image":
            platform_args = f'--platform {profile["docker_platform"]} ' if profile.get("docker_platform") else ""
            launcher = "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    'ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"',
                    f'exec docker run --rm {platform_args}-v "$ROOT:$ROOT" -w "$ROOT" {profile["runtime_locator"]} "$@"',
                    "",
                ]
            )
            write_text(REPO_ROOT / profile["launcher_ref"], launcher, executable=True)
            continue
        if profile["delivery_kind"] == "host_app" and profile["id"] == "eng_rhino_host":
            rhino_manifest = "\n".join(
                [
                    "runtime_path=/Applications/Rhino 8.app",
                    "rhinocode_path=/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode",
                    "yak_path=/Applications/Rhino 8.app/Contents/Resources/bin/yak",
                    "scripting_docs=https://www.rhino3d.com/features/developer/scripting/",
                    "gh_python_docs=https://developer.rhino3d.com/guides/scripting/scripting-gh-python/",
                    "gh_csharp_docs=https://developer.rhino3d.com/guides/scripting/scripting-gh-csharp/",
                    "",
                ]
            )
            write_text(REPO_ROOT / profile["manifest_path"], rhino_manifest)
            rhino_launcher = "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    'exec "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" "$@"',
                    "",
                ]
            )
            write_text(REPO_ROOT / profile["launcher_ref"], rhino_launcher, executable=True)

    dotnet_csproj = "\n".join(
        [
            "<Project Sdk=\"Microsoft.NET.Sdk\">",
            "  <PropertyGroup>",
            "    <OutputType>Exe</OutputType>",
            "    <TargetFramework>net9.0</TargetFramework>",
            "    <RollForward>Major</RollForward>",
            "    <ImplicitUsings>enable</ImplicitUsings>",
            "    <Nullable>enable</Nullable>",
            "  </PropertyGroup>",
            "  <ItemGroup>",
            "    <PackageReference Include=\"UnitsNet\" Version=\"5.75.0\" />",
            "    <PackageReference Include=\"MathNet.Numerics\" Version=\"5.0.0\" />",
            "    <PackageReference Include=\"PicoGK\" Version=\"1.7.7.5\" />",
            "  </ItemGroup>",
            "</Project>",
            "",
        ]
    )
    dotnet_program = "\n".join(
        [
            "using MathNet.Numerics;",
            "using System.Reflection;",
            "using UnitsNet;",
            "",
            "var length = Length.FromMeters(1.0);",
            "var gamma = SpecialFunctions.Gamma(5);",
            'var picoAssembly = Assembly.Load("PicoGK");',
            'Console.WriteLine($"UnitsNet:{length.Meters};MathNet:{gamma};PicoGK:{picoAssembly.GetName().Version}");',
            "",
        ]
    )
    write_text(
        RUNTIME_ROOT / "dotnet" / "eng-dotnet" / "KnowledgeDotnetRuntime.csproj",
        dotnet_csproj,
    )
    write_text(
        RUNTIME_ROOT / "dotnet" / "eng-dotnet" / "Program.cs",
        dotnet_program,
    )
    dotnet_launcher = "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            'ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"',
            'export DOTNET_ROLL_FORWARD="${DOTNET_ROLL_FORWARD:-Major}"',
            'exec dotnet run --project "$ROOT/knowledge/coding-tools/runtime/dotnet/eng-dotnet/KnowledgeDotnetRuntime.csproj" -c Release -- "$@"',
            "",
        ]
    )
    write_text(RUNTIME_ROOT / "launchers" / "eng-dotnet.sh", dotnet_launcher, executable=True)
    build_gui_runtime_manifests()


def build_compiled_contexts() -> None:
    sys.path.insert(0, str(REPO_ROOT / "services" / "api-service"))
    from src.control_plane.knowledge_pool import load_knowledge_pool  # noqa: WPS433

    catalog = load_knowledge_pool()
    inventory = catalog.minutes_inventory
    top_level_candidate_refs = sorted(
        {
            entry["knowledge_pack_ref"]
            for entry in inventory["entries"]
            if entry["promotion_ready"]
        }
    )
    project_constraints = {
        "languages": ["python", "c++", "c#", "cli"],
        "scope": "engineering_minutes_phase3_promoted",
        "exclude_draft": True,
        "verified_runtime_only": True,
        "promotion_only": True,
    }
    for role, filename in (
        ("general", "general-context.json"),
        ("coder", "coder-context.json"),
        ("reviewer", "reviewer-context.json"),
    ):
        record = catalog.compile_role_context_record(
            role=role,
            candidate_refs=top_level_candidate_refs,
            task_class="engineering_minutes_phase3_promoted",
            project_constraints=project_constraints,
        )
        write_json(
            OUTPUT_ROOT / "compiled" / filename,
            record.model_dump(mode="json", by_alias=True),
        )

    grouped_candidate_refs: dict[str, list[str]] = {}
    for entry in inventory["entries"]:
        if not entry["knowledge_pack_ref"]:
            continue
        grouped_candidate_refs.setdefault(f"kb:{entry['kb_build_batch']}", []).append(entry["knowledge_pack_ref"])
        grouped_candidate_refs.setdefault(f"install:{entry['install_batch']}", []).append(entry["knowledge_pack_ref"])
    grouped_candidate_refs["family:k2_backend_families"] = [
        artifact_ref("knowledge-pack", slug)
        for slug in ("petsc_family", "trilinos_family", "sparse_direct_family", "coinhsl_family", "nlp_time_chem_family", "geometry_native_family", "onemkl")
    ]

    phase2_root = OUTPUT_ROOT / "compiled" / "phase2"
    for group_name, candidate_refs in grouped_candidate_refs.items():
        refs = sorted(dict.fromkeys(candidate_refs))
        if not refs:
            continue
        safe_name = group_name.replace(":", "_")
        for role in ("general", "coder", "reviewer"):
            record = catalog.compile_role_context_record(
                role=role,
                candidate_refs=refs,
                task_class=f"phase2_{safe_name}",
                project_constraints={
                    "include_runtime_gated": True,
                    "phase2_group": group_name,
                },
            )
            write_json(
                phase2_root / f"{safe_name}_{role}.json",
                record.model_dump(mode="json", by_alias=True),
            )

    phase3_root = OUTPUT_ROOT / "compiled" / "phase3"
    non_promoted_entries = [
        entry
        for entry in inventory["entries"]
        if not entry["promotion_ready"] and entry["slug"] in {module["slug"] for module in EXCLUDED_MODULES}
    ]
    for entry in non_promoted_entries:
        refs = [entry["knowledge_pack_ref"]]
        safe_name = f"package_{entry['slug']}"
        for role in ("general", "coder", "reviewer"):
            record = catalog.compile_role_context_record(
                role=role,
                candidate_refs=refs,
                task_class=f"phase3_{safe_name}",
                project_constraints={
                    "include_runtime_gated": True,
                    "phase3_scope": "package",
                    "module_slug": entry["slug"],
                },
            )
            write_json(
                phase3_root / f"{safe_name}_{role}.json",
                record.model_dump(mode="json", by_alias=True),
            )

    parent_to_child_refs: dict[str, list[str]] = {}
    for entry in non_promoted_entries:
        parent_refs = entry.get("phase3_parent_completion_refs", [])
        for parent_ref in parent_refs:
            parent_slug = parent_ref.split("://", 1)[1]
            parent_to_child_refs.setdefault(parent_slug, []).append(entry["knowledge_pack_ref"])
    for parent_slug, child_refs in sorted(parent_to_child_refs.items()):
        parent_pack_ref = artifact_ref("knowledge-pack", PHASE2_SUBSTITUTIONS.get(parent_slug, {}).get("knowledge_pack_slug", parent_slug))
        refs = sorted(dict.fromkeys([parent_pack_ref, *child_refs]))
        safe_name = f"parent_{parent_slug}"
        for role in ("general", "coder", "reviewer"):
            record = catalog.compile_role_context_record(
                role=role,
                candidate_refs=refs,
                task_class=f"phase3_{safe_name}",
                project_constraints={
                    "include_runtime_gated": True,
                    "phase3_scope": "parent_runtime",
                    "parent_slug": parent_slug,
                },
            )
            write_json(
                phase3_root / f"{safe_name}_{role}.json",
                record.model_dump(mode="json", by_alias=True),
            )


def main() -> int:
    build_runtime_manifests()
    build_seed_files()
    build_compiled_contexts()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
