# Coding Tools Knowledge Pool

This directory is the schema-backed, repo-native runtime-linked seed for the expert engineering knowledge pool v1.

The four layers are stored as:

- `substrate/`: shared external knowledge substrate
- `adapters/`: typed execution adapters/tools
- `evidence/`: validation/evidence harness
- `compiled/`: role-specific context compilation

Canonical source artifacts are typed artifact envelopes whose payloads validate against the control-plane schemas in [schemas/control-plane/v1](/Users/maxholden/GitHub/server/schemas/control-plane/v1).

The normalized engineering inventory from the minutes is stored in `substrate/minutes-inventory.json`. Every engineering-minute module is represented either by:

- a runtime-linked `KNOWLEDGE_PACK` with adapters, evidence, and environment specs
- an explicit row in [/Users/maxholden/GitHub/server/KNOWLEGE MINUTES EXCLUDED.md](/Users/maxholden/GitHub/server/KNOWLEGE%20MINUTES%20EXCLUDED.md)

The excluded-module recovery plan is stored directly in the normalized inventory via:

- `recovery_plan`: install-method categories, knowledge-build categories, batch order, and chosen defaults
- per-entry recovery fields such as `install_method_category`, `install_batch`, `kb_build_method_category`, `kb_build_batch`, `phase_target`, `phase_state`, `cli_install_channel`, `cli_phase1_status`, `user_intervention_class`, and dependency refs

Manual intervention is now reserved for proprietary/license-gated modules and modules that still require website or email delivered artifacts. Everything else is classified into a Phase 1 CLI lane.

Recent runtime-link decisions reflected in the tracker:

- `PARDISO` now resolves to an `Intel oneMKL` Docker path instead of a licensed Panua acquisition path.
- `IPOPT` now resolves to the open containerized build path with local `HSL/` inputs staged for canonical packaging.
- `RhinoCommon` now resolves to the installed local `Rhino 8` host runtime via `rhinocode`, rather than staying in the manual-acquisition bucket.

Deferred/manual modules also get explicit acquisition dossiers in:

- `substrate/deferred-acquisition-dossiers.json`
- [/Users/maxholden/GitHub/server/knowledge/coding-tools/DEFERRED_ACQUISITION_DOSSIERS.md](/Users/maxholden/GitHub/server/knowledge/coding-tools/DEFERRED_ACQUISITION_DOSSIERS.md)

Implemented runtime-linked coverage in this sprint:

- `Cantera`
- `CasADi`
- `pymoo`
- `Gmsh`
- `CadQuery`
- `Open CASCADE (OCCT)`
- `OR-Tools`
- `Pyomo`
- `CoolProp`
- `TESPy`
- `FiPy`
- `PySpice`
- `FMPy`
- `OpenTURNS`
- `SMT`
- `SALib`
- `OpenMDAO`
- `meshio`
- `Pint`
- `unyt`
- `xarray`
- `h5py`
- `Zarr`
- `Dask`
- `Parsl`
- `pybind11`
- `nanobind`
- `mpi4py`
- `CVXPY`
- `jMetalPy`
- `ENOPPY`
- `UnitsNet`
- `Math.NET Numerics`

Checked-in runtime manifests live under:

- `runtime/uv/` for local `uv` environments
- `runtime/docker/` for canonical Docker manifests
- `runtime/dotnet/` for the `.NET 9` support runtime, now including `PicoGK` from NuGet
- `runtime/host/` for local host-app manifests such as the `Rhino 8` scripting runtime
- `runtime/docker/eng-wine.Dockerfile` for the canonical `wine64` runtime used to host Windows-oriented CLI installers
- `runtime/launchers/` for deterministic entrypoints tied back to the environment specs

To rebuild the seeded artifacts and compiled role bundles:

```bash
./.venv/bin/python scripts/generate_coding_tool_knowledge_pool.py
```

To bootstrap and verify a linked runtime:

```bash
./.venv/bin/python scripts/bootstrap_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_thermochem_uv
./.venv/bin/python scripts/verify_knowledge_runtime.py --environment-ref artifact://environment-spec/eng_thermochem_uv --imports cantera CoolProp tespy
```
