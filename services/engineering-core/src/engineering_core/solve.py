"""
solve_mechanics: map solve_mechanics_request_v1 JSON to engineering_report_v1.

For agents: validates profile and dispatches reference_mechanics; no silent coercion.
"""

from __future__ import annotations

from typing import Any

from engineering_core.reference_mechanics import (
    load_fluids,
    load_materials,
    solve_dry_sliding_block,
)


def solve_mechanics(request: dict[str, Any]) -> dict[str, Any]:
    """
    Public solver entry. `request` must match solve_mechanics_request_v1 (caller validates JSON Schema).
    """
    profile = request["assumption_profile_id"]
    if profile != "RIGID_BLOCK_DRY_SLIDING_V1":
        raise ValueError(f"Unsupported assumption_profile_id: {profile}")

    ov = request["assumption_overrides"]
    viscous = bool(ov["viscous_enabled"])
    fluid_id = ov["fluid_id"]
    if viscous and not fluid_id:
        raise ValueError("viscous_enabled requires fluid_id in overrides")
    geom = request["geometry"]
    if geom["shape"] != "CUBE":
        raise ValueError("Only CUBE geometry supported in v1")

    side = float(geom["cube_side_m"])
    displacement_m = float(request.get("displacement_m", 1.0))

    materials = load_materials()
    fluids = load_fluids()

    body_fluid = request.get("fluid_id")
    if body_fluid is not None and viscous:
        raise ValueError("Use assumption_overrides.fluid_id for viscous layer in v1")

    core = solve_dry_sliding_block(
        materials=materials,
        fluids=fluids,
        cube_side_m=side,
        block_material_id=request["block_material_id"],
        surface_material_id=request["surface_material_id"],
        fluid_id=fluid_id if viscous else None,
        viscous_enabled=viscous,
        applied_force_N=float(request["applied_force_N"]),
        displacement_m=displacement_m,
    )

    assumptions = [
        "Rigid cube, flat horizontal surface",
        "Constant kinetic friction from materials_v1 interface_mu_k",
        f"g = 9.81 m/s^2",
        "Quasi-static energy bookkeeping for displacement_m",
    ]
    if viscous:
        assumptions.append("Lumped viscous shear: v=0.1 m/s, gap=1e-4 m on bottom face")

    return {
        "schema_version": "1.0.0",
        "problem_brief": {
            "summary": (
                f"Dry/lubricated sliding cube: side {side} m, "
                f"block {request['block_material_id']}, surface {request['surface_material_id']}"
            ),
        },
        "assumptions": assumptions,
        "inputs": core["inputs"],
        "derived_quantities": core["derived_quantities"],
        "results": core["results"],
        "energy_balance": core["energy_balance"],
        "model_limits": [
            "Single kinetic friction coefficient per interface",
            "No temperature-dependent properties",
            "Viscous model is lumped, not Navier-Stokes",
        ],
        "comparison_case": {},
    }
