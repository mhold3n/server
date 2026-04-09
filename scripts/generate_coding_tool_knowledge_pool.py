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
EXCLUDED_PATH = REPO_ROOT / "KNOWLEGE MINUTES EXCLUDED.md"
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


RUNTIME_PROFILES: list[dict] = [
    {
        "id": "eng_geometry_uv",
        "runtime_profile": "eng-geometry",
        "delivery_kind": "uv_venv",
        "module_ids": ["gmsh", "cadquery", "occt", "meshio"],
        "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
        "manifest_format": "requirements_txt",
        "manifest_path": "knowledge/coding-tools/runtime/uv/eng-geometry.requirements.txt",
        "runtime_locator": ".cache/knowledge-envs/eng-geometry",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_geometry_uv",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_geometry_uv --imports cadquery gmsh OCP meshio",
        "launcher_ref": "knowledge/coding-tools/runtime/launchers/eng-geometry.sh",
        "requirements": ["cadquery", "gmsh", "meshio"],
        "verification_enabled": True,
        "notes": ["Companion local geometry runtime for scripted CAD, meshing, and translation."],
    },
    {
        "id": "eng_geometry_docker",
        "runtime_profile": "eng-geometry",
        "delivery_kind": "docker_image",
        "module_ids": ["gmsh", "cadquery", "occt", "meshio"],
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
            "enoppy"
        ],
        "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
        "manifest_format": "requirements_txt",
        "manifest_path": "knowledge/coding-tools/runtime/uv/eng-mdo.requirements.txt",
        "runtime_locator": ".cache/knowledge-envs/eng-mdo",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_mdo_uv",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_mdo_uv --imports casadi pymoo ortools pyomo.environ openturns smt SALib openmdao.api cvxpy jmetal enoppy",
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
            "enoppy"
        ],
        "verification_enabled": True,
        "verification_reasons": [
            "Runtime profile eng-mdo passed its linked import health check during this sprint.",
            "cvxpy loaded with OR-Tools compatibility warnings for GLOP/PDLP on OR-Tools 9.15.6755; core imports still completed successfully.",
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
            "enoppy"
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
        "module_ids": ["fipy"],
        "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
        "manifest_format": "requirements_txt",
        "manifest_path": "knowledge/coding-tools/runtime/uv/eng-structures.requirements.txt",
        "runtime_locator": ".cache/knowledge-envs/eng-structures",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_structures_uv",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_structures_uv --imports fipy",
        "launcher_ref": "knowledge/coding-tools/runtime/launchers/eng-structures.sh",
        "requirements": ["fipy"],
        "verification_enabled": True,
        "notes": ["Companion local lightweight structures/PDE runtime for custom transport models."],
    },
    {
        "id": "eng_structures_docker",
        "runtime_profile": "eng-structures",
        "delivery_kind": "docker_image",
        "module_ids": ["fipy"],
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
        "module_ids": ["pyspice", "fmpy"],
        "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
        "manifest_format": "requirements_txt",
        "manifest_path": "knowledge/coding-tools/runtime/uv/eng-system.requirements.txt",
        "runtime_locator": ".cache/knowledge-envs/eng-system",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_system_uv",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_system_uv --imports PySpice fmpy",
        "launcher_ref": "knowledge/coding-tools/runtime/launchers/eng-system.sh",
        "requirements": ["PySpice", "fmpy"],
        "verification_enabled": True,
        "notes": ["Companion local system-model runtime for circuit and FMU execution libraries."],
    },
    {
        "id": "eng_system_docker",
        "runtime_profile": "eng-system",
        "delivery_kind": "docker_image",
        "module_ids": ["pyspice", "fmpy"],
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
        "module_ids": ["pint", "unyt", "xarray", "h5py", "zarr", "dask", "parsl", "pybind11", "nanobind", "mpi4py"],
        "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
        "manifest_format": "requirements_txt",
        "manifest_path": "knowledge/coding-tools/runtime/uv/eng-backbone.requirements.txt",
        "runtime_locator": ".cache/knowledge-envs/eng-backbone",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_backbone_uv",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_backbone_uv --imports pint unyt xarray h5py zarr dask parsl pybind11 nanobind mpi4py",
        "launcher_ref": "knowledge/coding-tools/runtime/launchers/eng-backbone.sh",
        "requirements": ["pint", "unyt", "xarray", "h5py", "zarr", "dask", "parsl", "pybind11", "nanobind", "mpi4py"],
        "verification_enabled": True,
        "notes": ["Companion local backbone runtime for units, arrays, orchestration, and native bridges."],
    },
    {
        "id": "eng_backbone_docker",
        "runtime_profile": "eng-backbone",
        "delivery_kind": "docker_image",
        "module_ids": ["pint", "unyt", "xarray", "h5py", "zarr", "dask", "parsl", "pybind11", "nanobind", "mpi4py"],
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
        "module_ids": ["unitsnet", "mathnet_numerics"],
        "supported_host_platforms": ["darwin-arm64", "linux-amd64"],
        "manifest_format": "csproj",
        "manifest_path": "knowledge/coding-tools/runtime/dotnet/eng-dotnet/KnowledgeDotnetRuntime.csproj",
        "runtime_locator": "knowledge/coding-tools/runtime/dotnet/eng-dotnet/bin/Release/net8.0",
        "bootstrap_command": "python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_dotnet_sdk",
        "healthcheck_command": "python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_dotnet_sdk --dotnet-probe",
        "launcher_ref": "knowledge/coding-tools/runtime/launchers/eng-dotnet.sh",
        "requirements": [],
        "verification_enabled": True,
        "verification_reasons": [
            "Runtime profile eng-dotnet passed its linked health check during this sprint.",
            "The probe runs with DOTNET_ROLL_FORWARD=Major so the net8.0 test project can execute on the installed host runtime.",
        ],
        "notes": ["Companion dotnet runtime for implemented engineering support libraries."],
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


EXCLUDED_MODULES = [
    excluded(slug="openfoam", name="OpenFOAM", category="seed_stack", module_class="application", source_refs=["minutes://table1#L298"], reason="no viable canonical Docker runtime verified in this sprint"),
    excluded(slug="calculix", name="CalculiX", category="seed_stack", module_class="application", source_refs=["minutes://table1#L299"], reason="no viable canonical Docker runtime verified in this sprint"),
    excluded(slug="picogk_shapekernel", name="PicoGK / ShapeKernel", category="seed_stack", module_class="application", source_refs=["minutes://table1#L301"], reason="no headless redistributable runtime was packaged in this sprint"),
    excluded(slug="ipopt", name="IPOPT", category="seed_stack", module_class="runtime_kernel", source_refs=["minutes://table1#L303"], reason="isolated native backend packaging was not verified in this sprint"),
    excluded(slug="opencamlib", name="OpenCAMLib", category="geometry_manufacturing", module_class="runtime_kernel", source_refs=["minutes://table1#L308"], reason="no reliable isolated runtime was verified in this sprint"),
    excluded(slug="cgal", name="CGAL", category="geometry_manufacturing", module_class="runtime_kernel", source_refs=["minutes://table1#L309"], reason="no viable isolated runtime package was verified in this sprint"),
    excluded(slug="su2", name="SU2", category="thermofluids_chemistry", module_class="application", source_refs=["minutes://table1#L312"], reason="no viable canonical Docker runtime was verified in this sprint"),
    excluded(slug="code_saturne", name="code_saturne", category="thermofluids_chemistry", module_class="application", source_refs=["minutes://table1#L313"], reason="no viable canonical Docker runtime was verified in this sprint"),
    excluded(slug="openwam", name="OpenWAM", category="thermofluids_chemistry", module_class="application", source_refs=["minutes://table1#L314"], reason="no isolated runtime package was verified in this sprint"),
    excluded(slug="opensmokepp", name="OpenSMOKE++", category="thermofluids_chemistry", module_class="application", source_refs=["minutes://table1#L315"], reason="no isolated runtime package was verified in this sprint"),
    excluded(slug="tchem", name="TChem", category="thermofluids_chemistry", module_class="runtime_kernel", source_refs=["minutes://table1#L316"], reason="HPC chemistry runtime was not verified in this sprint"),
    excluded(slug="idaes", name="IDAES", category="thermofluids_chemistry", module_class="framework", source_refs=["minutes://table1#L319"], reason="heavyweight process-stack runtime was not verified in this sprint"),
    excluded(slug="fenicsx", name="FEniCSx", category="structures_pde", module_class="framework", source_refs=["minutes://table1#L320"], reason="no isolated runtime package was verified in this sprint"),
    excluded(slug="dealii", name="deal.II", category="structures_pde", module_class="framework", source_refs=["minutes://section2#L67"], reason="no isolated runtime package was verified in this sprint"),
    excluded(slug="hermes", name="Hermes", category="structures_pde", module_class="framework", source_refs=["minutes://section2#L75"], reason="no isolated runtime package was verified in this sprint"),
    excluded(slug="kratos_multiphysics", name="Kratos Multiphysics", category="structures_pde", module_class="framework", source_refs=["minutes://table1#L321"], reason="no viable canonical Docker runtime was verified in this sprint"),
    excluded(slug="moose", name="MOOSE", category="structures_pde", module_class="framework", source_refs=["minutes://table1#L322"], reason="no viable canonical Docker runtime was verified in this sprint"),
    excluded(slug="code_aster", name="Code_Aster", category="structures_pde", module_class="application", source_refs=["minutes://table1#L324"], reason="no viable canonical Docker runtime was verified in this sprint"),
    excluded(slug="project_chrono", name="Project Chrono", category="electrics_dynamics_system", module_class="framework", source_refs=["minutes://table1#L325"], reason="no reliable isolated runtime package was verified in this sprint"),
    excluded(slug="pyleecan", name="PYLEECAN", category="electrics_dynamics_system", module_class="application", source_refs=["minutes://table1#L326"], reason="package depends on a URL-only swat-em source that was not locked into a canonical isolated runtime in this sprint"),
    excluded(slug="femm", name="FEMM", category="electrics_dynamics_system", module_class="application", source_refs=["minutes://table1#L327"], reason="non-headless GUI and Windows-leaning runtime"),
    excluded(slug="openmodelica", name="OpenModelica", category="electrics_dynamics_system", module_class="application", source_refs=["minutes://table1#L329"], reason="no canonical headless Modelica toolchain was verified in this sprint"),
    excluded(slug="ompython", name="OMPython", category="electrics_dynamics_system", module_class="integration_layer", source_refs=["minutes://table1#L329"], reason="depends on an OpenModelica host runtime that was not verified in this sprint"),
    excluded(slug="modelica_standard_library", name="Modelica Standard Library", category="electrics_dynamics_system", module_class="standard", source_refs=["minutes://table1#L329"], reason="depends on a verified Modelica host that was not packaged in this sprint", executable=False),
    excluded(slug="pyoptsparse", name="pyOptSparse", category="optimization_uq_backbone", module_class="framework", source_refs=["minutes://table1#L330"], reason="native optimization backend stack was not verified in this sprint"),
    excluded(slug="dakota", name="Dakota", category="optimization_uq_backbone", module_class="application", source_refs=["minutes://table1#L331"], reason="no isolated runtime package was verified in this sprint"),
    excluded(slug="petsc", name="PETSc", category="optimization_uq_backbone", module_class="runtime_kernel", source_refs=["minutes://table1#L335"], reason="HPC native runtime was not verified in this sprint"),
    excluded(slug="petsc4py", name="petsc4py", category="optimization_uq_backbone", module_class="integration_layer", source_refs=["minutes://table1#L335"], reason="depends on PETSc runtime that was not verified in this sprint"),
    excluded(slug="sundials", name="SUNDIALS", category="optimization_uq_backbone", module_class="runtime_kernel", source_refs=["minutes://table1#L336"], reason="native solver stack was not verified in this sprint"),
    excluded(slug="mphys", name="MPhys", category="workflow_coupling", module_class="integration_layer", source_refs=["minutes://table2#L347"], reason="package/runtime was not verified in this sprint"),
    excluded(slug="precice", name="preCICE", category="workflow_coupling", module_class="integration_layer", source_refs=["minutes://table2#L348"], reason="no viable canonical Docker runtime was verified in this sprint"),
    excluded(slug="fmi_fmus", name="FMI / FMUs", category="workflow_coupling", module_class="standard", source_refs=["minutes://table2#L349"], reason="standard/specification, not a standalone runtime installation", executable=False),
    excluded(slug="pyfmi", name="PyFMI", category="workflow_coupling", module_class="integration_layer", source_refs=["minutes://table2#L350"], reason="native FMI backend was not verified in this sprint"),
    excluded(slug="salome", name="SALOME", category="workflow_coupling", module_class="application", source_refs=["minutes://table2#L352"], reason="GUI-heavy platform was not packaged in this sprint"),
    excluded(slug="medcoupling", name="MEDCoupling", category="workflow_coupling", module_class="translator", source_refs=["minutes://table2#L353"], reason="native SALOME dependency stack was not verified in this sprint"),
    excluded(slug="cgns", name="CGNS", category="workflow_coupling", module_class="standard", source_refs=["minutes://table2#L354"], reason="standard/format, not a standalone runtime installation", executable=False),
    excluded(slug="exodus_ii", name="Exodus II", category="workflow_coupling", module_class="standard", source_refs=["minutes://table2#L354"], reason="standard/format, not a standalone runtime installation", executable=False),
    excluded(slug="ray", name="Ray", category="workflow_coupling", module_class="integration_layer", source_refs=["minutes://table2#L357"], reason="distributed runtime was not verified in this sprint"),
    excluded(slug="paraview", name="ParaView", category="workflow_coupling", module_class="application", source_refs=["minutes://table2#L360"], reason="GUI-heavy visualization stack was not packaged in this sprint"),
    excluded(slug="vtk", name="VTK", category="workflow_coupling", module_class="framework", source_refs=["minutes://table2#L360"], reason="runtime was not verified in this sprint"),
    excluded(slug="compas", name="Compas", category="geometry_manufacturing", module_class="framework", source_refs=["minutes://section5#L147"], reason="not prioritized for this sprint"),
    excluded(slug="simpeg", name="SimPEG", category="domain_specific", module_class="framework", source_refs=["minutes://section4#L125"], reason="not prioritized for this sprint"),
    excluded(slug="pyphs", name="PyPHS", category="domain_specific", module_class="framework", source_refs=["minutes://section4#L132"], reason="not prioritized for this sprint"),
    excluded(slug="rhino_common", name="RhinoCommon", category="csharp_examples", module_class="framework", source_refs=["minutes://section_csharp#L290"], reason="proprietary CAD runtime not packaged in this sprint"),
    excluded(slug="mbdyn", name="MBDyn", category="reserve", module_class="application", source_refs=["minutes://table1#L338"], reason="reserve-list runtime not prioritized in this sprint"),
    excluded(slug="rmg_py", name="RMG-Py", category="reserve", module_class="application", source_refs=["minutes://table1#L338"], reason="reserve-list runtime not prioritized in this sprint"),
    excluded(slug="simpy", name="SimPy", category="reserve", module_class="framework", source_refs=["minutes://table1#L338"], reason="reserve-list runtime not prioritized in this sprint"),
    excluded(slug="botorch", name="BoTorch", category="reserve", module_class="framework", source_refs=["minutes://table1#L338"], reason="reserve-list runtime not prioritized in this sprint"),
    excluded(slug="nevergrad", name="Nevergrad", category="reserve", module_class="framework", source_refs=["minutes://table1#L338"], reason="reserve-list runtime not prioritized in this sprint"),
    excluded(slug="openpnm", name="OpenPNM", category="reserve", module_class="framework", source_refs=["minutes://table1#L338"], reason="reserve-list runtime not prioritized in this sprint"),
    excluded(slug="porepy", name="PorePy", category="reserve", module_class="framework", source_refs=["minutes://table1#L338"], reason="reserve-list runtime not prioritized in this sprint"),
    excluded(slug="optas", name="OptaS", category="optimization_uq_backbone", module_class="framework", source_refs=["minutes://section3#L114"], reason="runtime was not verified in this sprint"),
    excluded(slug="dymos", name="Dymos", category="workflow_coupling", module_class="framework", source_refs=["minutes://section_actual_stack#L371"], reason="runtime was not verified in this sprint"),
    excluded(slug="ma57", name="MA57", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L728"], reason="licensed sparse direct solver backend not packaged in this sprint"),
    excluded(slug="ma77", name="MA77", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L821"], reason="licensed sparse direct solver backend not packaged in this sprint"),
    excluded(slug="ma86", name="MA86", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L821"], reason="licensed sparse direct solver backend not packaged in this sprint"),
    excluded(slug="ma87", name="MA87", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L821"], reason="licensed sparse direct solver backend not packaged in this sprint"),
    excluded(slug="ma97", name="MA97", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L821"], reason="licensed sparse direct solver backend not packaged in this sprint"),
    excluded(slug="mumps", name="MUMPS", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L729"], reason="native sparse direct backend was not verified in this sprint"),
    excluded(slug="superlu", name="SuperLU", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L730"], reason="native sparse direct backend was not verified in this sprint"),
    excluded(slug="superlu_dist", name="SuperLU_DIST", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L730"], reason="native sparse direct backend was not verified in this sprint"),
    excluded(slug="pardiso", name="PARDISO", category="solver_backends", module_class="runtime_kernel", source_refs=["minutes://solver_table#L731"], reason="licensed sparse direct backend was not packaged in this sprint"),
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


def build_environment_specs() -> tuple[list[dict], list[dict]]:
    environment_records: list[dict] = []
    verification_records: list[dict] = []
    for profile in RUNTIME_PROFILES:
        payload = {
            "environment_spec_id": profile["id"],
            "schema_version": "1.0.0",
            "runtime_profile": profile["runtime_profile"],
            "delivery_kind": profile["delivery_kind"],
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

    env_records, verification_records = build_environment_specs()
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
                "category": module["category"],
                "module_class": module["module_class"],
                "minutes_source_refs": module["source_refs"],
                "executable": True,
                "implementation_status": "implemented",
                "knowledge_pack_ref": artifact_ref("knowledge-pack", module["slug"]),
                "environment_refs": env_refs_for_module(module),
                "excluded_reason": None,
            }
        )
    for module in EXCLUDED_MODULES:
        inventory_entries.append(
            {
                "name": module["name"],
                "slug": module["slug"],
                "category": module["category"],
                "module_class": module["module_class"],
                "minutes_source_refs": module["source_refs"],
                "executable": module["executable"],
                "implementation_status": "excluded",
                "knowledge_pack_ref": None,
                "environment_refs": [],
                "excluded_reason": module["excluded_reason"],
            }
        )
    inventory_entries = sorted(inventory_entries, key=lambda item: item["name"].lower())
    write_json(
        OUTPUT_ROOT / "substrate" / "minutes-inventory.json",
        {
            "schema_version": "1.0.0",
            "focus_area": "engineering",
            "source": "Normalized engineering sections from Conversation Minutes; Kimi/Gemma sections excluded.",
            "entries": inventory_entries,
        },
    )

    excluded_lines = [
        "# KNOWLEGE MINUTES EXCLUDED",
        "",
        "| name | reason excluded |",
        "| --- | --- |",
    ]
    for module in sorted(EXCLUDED_MODULES, key=lambda item: item["name"].lower()):
        excluded_lines.append(f"| {module['name']} | {module['excluded_reason']} |")
    write_text(EXCLUDED_PATH, "\n".join(excluded_lines) + "\n")


def build_runtime_manifests() -> None:
    profile_by_id = runtime_profile_map()
    uv_profiles = [profile for profile in RUNTIME_PROFILES if profile["delivery_kind"] == "uv_venv"]
    for profile in uv_profiles:
        requirement_lines = "\n".join(profile["requirements"]) + "\n"
        write_text(REPO_ROOT / profile["manifest_path"], requirement_lines)

    for profile in [item for item in RUNTIME_PROFILES if item["delivery_kind"] == "docker_image"]:
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

    dotnet_csproj = "\n".join(
        [
            "<Project Sdk=\"Microsoft.NET.Sdk\">",
            "  <PropertyGroup>",
            "    <OutputType>Exe</OutputType>",
            "    <TargetFramework>net8.0</TargetFramework>",
            "    <RollForward>Major</RollForward>",
            "    <ImplicitUsings>enable</ImplicitUsings>",
            "    <Nullable>enable</Nullable>",
            "  </PropertyGroup>",
            "  <ItemGroup>",
            "    <PackageReference Include=\"UnitsNet\" Version=\"5.75.0\" />",
            "    <PackageReference Include=\"MathNet.Numerics\" Version=\"5.0.0\" />",
            "  </ItemGroup>",
            "</Project>",
            "",
        ]
    )
    dotnet_program = "\n".join(
        [
            "using MathNet.Numerics;",
            "using UnitsNet;",
            "",
            "var length = Length.FromMeters(1.0);",
            "var gamma = SpecialFunctions.Gamma(5);",
            'Console.WriteLine($"UnitsNet:{length.Meters};MathNet:{gamma}");',
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


def build_compiled_contexts() -> None:
    sys.path.insert(0, str(REPO_ROOT / "services" / "api"))
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


def main() -> int:
    build_runtime_manifests()
    build_seed_files()
    build_compiled_contexts()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
