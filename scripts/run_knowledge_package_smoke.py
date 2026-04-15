#!/usr/bin/env python3
"""Run a package-scoped smoke check against the generated knowledge pool."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
API_SRC = REPO_ROOT / "services" / "api-service"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from src.control_plane.knowledge_pool import load_knowledge_pool  # noqa: E402


PYTHON_IMPORTS = {
    "botorch": ["botorch"],
    "compas": ["compas"],
    "dymos": ["dymos"],
    "idaes": ["idaes"],
    "mphys": ["mphys"],
    "nevergrad": ["nevergrad"],
    "ompython": ["OMPython"],
    "openpnm": ["openpnm"],
    "optas": ["optas"],
    "pyphs": ["pyphs"],
    "ray": ["ray"],
    "rmg_py": ["rmgpy"],
    "simpeg": ["simpeg"],
    "simpy": ["simpy"],
    "vtk": ["vtk"],
}

CONTAINER_COMMANDS = {
    "calculix": [
        "bash",
        "-lc",
        "tool=$(if command -v ccx >/dev/null; then echo ccx; else echo ccx_2.21; fi); "
        "$tool -v >/tmp/calculix-smoke.log 2>&1 || true; "
        "grep -q 'Version' /tmp/calculix-smoke.log && cat /tmp/calculix-smoke.log && echo OK:calculix",
    ],
    "code_aster": [
        "bash",
        "-lc",
        "mkdir -p /tmp/flasheur && export HOME=/tmp && as_run --version | grep -q 'as_run' && echo OK:code_aster",
    ],
    "code_saturne": [
        "bash",
        "-lc",
        "/opt/code_saturne/bin/code_saturne help >/tmp/code_saturne_help.log 2>&1 || true; grep -q 'code_saturne <topic>' /tmp/code_saturne_help.log && echo OK:code_saturne",
    ],
    "cgal": ["bash", "-lc", "python -c 'import CGAL; print(CGAL.__file__)'"],
    "cholmod": ["bash", "-lc", "find /opt/conda -iname '*cholmod*' -print -quit | grep -q . && echo OK:cholmod"],
    "dealii": ["bash", "-lc", "test -f /usr/include/deal.II/base/config.h && echo OK:dealii"],
    "fenicsx": ["bash", "-lc", "python3 -c 'import dolfinx; print(dolfinx.__version__)'"],
    "hypre": ["bash", "-lc", "python -c \"from petsc4py import PETSc; pc=PETSc.PC().create(); pc.setType('hypre'); print('OK:hypre')\""],
    "ipopt": ["bash", "-lc", "pkg-config --exists ipopt && echo OK:ipopt"],
    "klu": ["bash", "-lc", "find /opt/conda -iname '*klu*' -print -quit | grep -q . && echo OK:klu"],
    "kratos_multiphysics": ["bash", "-lc", "python -c 'import KratosMultiphysics; print(KratosMultiphysics.__file__)'"],
    "ma57": ["bash", "-lc", "test -d /opt/vendor/coinhsl-src/ma57 && echo OK:ma57"],
    "ma77": ["bash", "-lc", "test -d /opt/vendor/coinhsl-src/hsl_ma77 && echo OK:ma77"],
    "ma86": ["bash", "-lc", "test -d /opt/vendor/coinhsl-src/hsl_ma86 && echo OK:ma86"],
    "ma97": ["bash", "-lc", "test -d /opt/vendor/coinhsl-src/hsl_ma97 && echo OK:ma97"],
    "mumps": ["bash", "-lc", "find /opt/conda -iname '*mumps*' -print -quit | grep -q . && echo OK:mumps"],
    "modelica_standard_library": [
        "bash",
        "-lc",
        "printf 'loadModel(Modelica);\\ngetVersion(Modelica);\\n' >/tmp/modelica-smoke.mos && omc /tmp/modelica-smoke.mos | grep -q . && echo OK:modelica_standard_library",
    ],
    "nlp_time_chem_family": ["bash", "-lc", "test -d /opt/conda && echo OK:nlp-time-chem-family"],
    "onemkl": ["bash", "-lc", "test -f /opt/intel/oneapi/mkl/latest/lib/libmkl_rt.so && echo OK:onemkl"],
    "opencamlib": ["bash", "-lc", "python3 -c 'import opencamlib; print(opencamlib.__file__)'"],
    "openfoam": ["bash", "-lc", "compgen -c | grep -Eq '(^|/)foam|icoFoam' && echo OK:openfoam"],
    "openmodelica": ["bash", "-lc", "omc --version"],
    "opensmokepp": ["bash", "-lc", "command -v OpenSMOKEpp_BatchReactor.sh >/dev/null && echo OK:opensmokepp"],
    "paraview": ["bash", "-lc", "(paraview --version >/dev/null || pvserver --version >/dev/null) && echo OK:paraview"],
    "pardiso": ["bash", "-lc", "test -f /opt/intel/oneapi/mkl/latest/lib/libmkl_rt.so && echo OK:pardiso-alias-onemkl"],
    "petsc": ["bash", "-lc", "python -c 'from petsc4py import PETSc; print(PETSc.Sys.getVersion())'"],
    "petsc4py": ["bash", "-lc", "python -c 'import petsc4py; print(petsc4py.__version__)'"],
    "petsc_gamg": ["bash", "-lc", "python -c \"from petsc4py import PETSc; pc=PETSc.PC().create(); pc.setType('gamg'); print('OK:petsc_gamg')\""],
    "petsc_ksp": ["bash", "-lc", "python -c \"from petsc4py import PETSc; ksp=PETSc.KSP().create(); print('OK:petsc_ksp')\""],
    "primme": ["bash", "-lc", "python -c 'import primme; print(primme.__file__)'"],
    "precice": ["bash", "-lc", "python -c 'import precice; print(precice.__file__)'"],
    "project_chrono": ["bash", "-lc", "python -c 'import pychrono; print(pychrono.__version__)'"],
    "pyfmi": ["bash", "-lc", "python3 -c 'import pyfmi; print(pyfmi.__file__)'"],
    "mbdyn": ["bash", "-lc", "test -x /mbdyn/bin/mbdyn && echo OK:mbdyn"],
    "medcoupling": [
        "bash",
        "-lc",
        "test -d /home/salome_user/salome_meca/V2018.0.1_public/tools/Medcoupling-V8_5_0 && echo OK:medcoupling",
    ],
    "moose": ["bash", "-lc", "test -x /opt/moose/bin/moose-opt && test -x /opt/moose/bin/combined-opt && echo OK:moose"],
    "openwam": [
        "bash",
        "-lc",
        "tool=$(command -v wine64 || command -v wine || true); "
        "if [ -z \"$tool\" ] && [ -x /usr/lib/wine/wine64 ]; then tool=/usr/lib/wine/wine64; fi; "
        "runner=(); if command -v xvfb-run >/dev/null; then runner=(xvfb-run -a); fi; "
        "\"${runner[@]}\" \"$tool\" /opt/openwam/OpenWAM.exe /opt/openwam/probe/missing.wam >/tmp/openwam.log 2>&1 || true; "
        "grep -Eiq 'openwam|input|cannot|failed to open|not found' /tmp/openwam.log && echo OK:openwam",
    ],
    "salome": ["bash", "-lc", "salome -h | grep -q 'Usage: salome' && echo OK:salome"],
    "slepc": ["bash", "-lc", "python -c 'from slepc4py import SLEPc; print(SLEPc.__name__)'"],
    "strumpack": ["bash", "-lc", "/usr/local/bin/strumpack_probe && echo OK:strumpack"],
    "suitesparse": ["bash", "-lc", "find /opt/conda -iname '*suitesparse*' -o -iname '*cholmod*' -print -quit | grep -q . && echo OK:suitesparse"],
    "superlu": ["bash", "-lc", "find /opt/conda -iname 'libsuperlu*.so*' -print -quit | grep -q . && echo OK:superlu"],
    "superlu_dist": ["bash", "-lc", "find /opt/conda -iname 'libsuperlu_dist*.so*' -print -quit | grep -q . && echo OK:superlu_dist"],
    "su2": ["bash", "-lc", "SU2_CFD -h >/dev/null && echo OK:su2"],
    "sundials": ["bash", "-lc", "find /opt/conda -iname '*sundials*' -print -quit | grep -q . && echo OK:sundials"],
    "tchem": [
        "bash",
        "-lc",
        "/opt/tchem/bin/tchem.x --help >/tmp/tchem.log 2>&1 || true; "
        "grep -Eiq 'tchem|json|input' /tmp/tchem.log && echo OK:tchem",
    ],
    "trilinos": ["bash", "-lc", "find /opt/conda -name 'libtrilinos*.so*' -print -quit | grep -q . && echo OK:trilinos"],
    "trilinos_belos": ["bash", "-lc", "find /opt/conda -iname '*belos*' -print -quit | grep -q . && echo OK:trilinos_belos"],
    "trilinos_ifpack2": ["bash", "-lc", "find /opt/conda -iname '*ifpack2*' -print -quit | grep -q . && echo OK:trilinos_ifpack2"],
    "trilinos_muelu": ["bash", "-lc", "find /opt/conda -iname '*muelu*' -print -quit | grep -q . && echo OK:trilinos_muelu"],
    "umfpack": ["bash", "-lc", "find /opt/conda -iname '*umfpack*' -print -quit | grep -q . && echo OK:umfpack"],
    "hermes": ["bash", "-lc", "/usr/local/bin/hermes_probe && echo OK:hermes"],
    "rmg_py": ["bash", "-lc", "python -c 'import rmgpy, arkane; print(rmgpy.__file__)'"],
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module-slug", required=True)
    parser.add_argument("--knowledge-pack-ref", required=True)
    args = parser.parse_args()

    catalog = load_knowledge_pool()
    artifact = catalog.knowledge_packs.get(args.knowledge_pack_ref)
    if artifact is None:
        raise ValueError(f"Unknown knowledge pack ref: {args.knowledge_pack_ref}")
    payload = artifact.payload

    if not payload.adapter_refs:
        raise ValueError(f"{args.knowledge_pack_ref} has no adapter refs")
    if not payload.evidence_refs:
        raise ValueError(f"{args.knowledge_pack_ref} has no evidence refs")

    adapter = catalog.execution_adapters[payload.adapter_refs[0]].payload
    environment_ref = adapter.preferred_environment_ref
    evidence = catalog.evidence_bundles[payload.evidence_refs[0]].payload
    if not evidence.smoke_tests:
        raise ValueError(f"{args.knowledge_pack_ref} has no smoke tests")

    environment = catalog.environment_specs[environment_ref].payload
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "verify_knowledge_runtime.py"),
        "--environment-ref",
        environment_ref,
    ]
    if payload.tool_id in CONTAINER_COMMANDS and environment.delivery_kind == "docker_image":
        command.extend(["--container-command", *CONTAINER_COMMANDS[payload.tool_id]])
    elif payload.tool_id in PYTHON_IMPORTS:
        command.extend(["--imports", *PYTHON_IMPORTS[payload.tool_id]])

    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        return result.returncode

    if adapter.knowledge_pack_ref != args.knowledge_pack_ref:
        raise ValueError(f"Adapter for {args.module_slug} is not linked back to {args.knowledge_pack_ref}")
    if environment_ref not in payload.environment_refs:
        raise ValueError(f"Preferred environment {environment_ref} is not linked to {args.knowledge_pack_ref}")
    print(f"OK:package-smoke:{args.module_slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
