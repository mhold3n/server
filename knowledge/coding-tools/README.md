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
- `runtime/dotnet/` for the `.NET 8` support runtime
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
