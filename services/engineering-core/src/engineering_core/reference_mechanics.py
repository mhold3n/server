"""
reference_mechanics: closed-form rigid-block-on-plane mechanics for v1 harness.

Simplifications (explicit): rigid cube, flat horizontal surface, constant kinetic
friction coefficient from materials fixture, g = 9.81 m/s^2, no deformation,
no temperature-dependent properties. Optional viscous layer uses lumped shear
approximation when assumption_overrides.viscous_enabled and fluid_id set.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

G_MPS2 = 9.81


def _fixtures_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures"


def load_materials() -> dict[str, Any]:
    """Load materials_v1.json (density, interface_mu_k map)."""
    p = _fixtures_dir() / "materials_v1.json"
    return json.loads(p.read_text(encoding="utf-8"))


def load_fluids() -> dict[str, Any]:
    """Load fluids_v1.json."""
    p = _fixtures_dir() / "fluids_v1.json"
    return json.loads(p.read_text(encoding="utf-8"))


def interface_mu_k(data: dict[str, Any], block_id: str, surface_id: str) -> float:
    """Kinetic friction coefficient for block|surface pair."""
    key = f"{block_id}|{surface_id}"
    mu_map = data.get("interface_mu_k", {})
    if key not in mu_map:
        raise KeyError(f"Unknown interface_mu_k key: {key}")
    return float(mu_map[key])


def mass_kg_from_cube(data: dict[str, Any], block_id: str, side_m: float) -> float:
    rho = float(data["materials"][block_id]["density_kg_m3"])
    vol = side_m**3
    return rho * vol


def viscous_resistance_N(
    *,
    eta_Pa_s: float,
    area_m2: float,
    velocity_m_s: float,
    gap_m: float,
) -> float:
    """Lumped viscous shear: tau = eta * (du/dy) ~ eta * v/h; F = tau * A."""
    if gap_m <= 0:
        raise ValueError("gap_m must be positive for viscous model")
    return eta_Pa_s * (velocity_m_s / gap_m) * area_m2


def solve_dry_sliding_block(
    *,
    materials: dict[str, Any],
    fluids: dict[str, Any],
    cube_side_m: float,
    block_material_id: str,
    surface_material_id: str,
    fluid_id: str | None,
    viscous_enabled: bool,
    applied_force_N: float,
    displacement_m: float,
) -> dict[str, Any]:
    """
    Compute normal, friction, acceleration, and quasi-static energy ledger.

    If viscous_enabled and fluid_id: add viscous resistance to resisting force
    (lumped v=0.1 m/s, gap=1e-4 m over bottom face area for v1).
    """
    m = mass_kg_from_cube(materials, block_material_id, cube_side_m)
    normal_n = m * G_MPS2
    reaction_n = normal_n
    mu = interface_mu_k(materials, block_material_id, surface_material_id)
    friction_n = mu * normal_n

    bottom_a = cube_side_m**2
    resisting = friction_n
    if viscous_enabled and fluid_id:
        eta = float(fluids["fluids"][fluid_id]["dynamic_viscosity_Pa_s"])
        v = 0.1
        h = 1e-4
        resisting += viscous_resistance_N(
            eta_Pa_s=eta, area_m2=bottom_a, velocity_m_s=v, gap_m=h
        )

    f_net = applied_force_N - resisting
    work_in = applied_force_N * displacement_m
    if f_net <= 0.0:
        accel = 0.0
        delta_ke = 0.0
        dissipated = work_in
        residual = 0.0
    else:
        accel = f_net / m
        delta_ke = f_net * displacement_m
        dissipated = resisting * displacement_m
        residual = work_in - delta_ke - dissipated

    return {
        "inputs": {
            "cube_side_m": cube_side_m,
            "block_material_id": block_material_id,
            "surface_material_id": surface_material_id,
            "fluid_id": fluid_id,
            "viscous_enabled": viscous_enabled,
            "applied_force_N": applied_force_N,
            "displacement_m": displacement_m,
            "g_mps2": G_MPS2,
        },
        "derived_quantities": {
            "mass_kg": m,
            "kinetic_friction_coefficient": mu,
            "friction_force_N": friction_n,
        },
        "results": {
            "acceleration_mps2": accel,
            "normal_force_N": normal_n,
            "reaction_force_N": reaction_n,
            "resisting_force_N": resisting,
            "heat_dissipation_J": dissipated,
        },
        "energy_balance": {
            "work_in_J": work_in,
            "kinetic_energy_change_J": delta_ke,
            "dissipated_J": dissipated,
            "residual_J": residual,
        },
    }
