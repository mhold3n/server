"""Golden tests: deterministic solver + verification (no GPU)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engineering_core import solve_mechanics, verify_engineering_report
from engineering_core.reference_mechanics import load_materials, mass_kg_from_cube

FIX = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "engineering_core"
    / "fixtures"
)


def _req(**kwargs: object) -> dict:
    base = {
        "schema_version": "1.0.0",
        "assumption_profile_id": "RIGID_BLOCK_DRY_SLIDING_V1",
        "assumption_overrides": {"fluid_id": None, "viscous_enabled": False},
        "geometry": {"shape": "CUBE", "cube_side_m": 1.0},
        "block_material_id": "steel_7850",
        "surface_material_id": "concrete_rough",
        "fluid_id": None,
        "applied_force_N": 40000.0,
        "force_direction_assumption": "horizontal_in_plane",
        "displacement_m": 1.0,
    }
    base.update(kwargs)
    return base


def test_dry_sliding_block_mass_and_force_balance() -> None:
    rep = solve_mechanics(_req())
    mats = load_materials()
    m = mass_kg_from_cube(mats, "steel_7850", 1.0)
    assert rep["derived_quantities"]["mass_kg"] == pytest.approx(m)
    assert rep["results"]["normal_force_N"] == pytest.approx(m * 9.81)
    vo = verify_engineering_report(rep)
    assert vo["status"] == "PASS"


def test_viscous_increases_resisting_force() -> None:
    dry = solve_mechanics(_req(applied_force_N=2000.0))
    wet = solve_mechanics(
        _req(
            applied_force_N=2000.0,
            assumption_overrides={"fluid_id": "water_20c", "viscous_enabled": True},
        ),
    )
    assert wet["results"]["resisting_force_N"] > dry["results"]["resisting_force_N"]


def test_material_swap_changes_friction_or_mass() -> None:
    a = solve_mechanics(_req(block_material_id="steel_7850", applied_force_N=40000.0))
    b = solve_mechanics(_req(block_material_id="aluminum_2700", applied_force_N=40000.0))
    assert a["derived_quantities"]["mass_kg"] != pytest.approx(b["derived_quantities"]["mass_kg"])
    assert a["derived_quantities"]["friction_force_N"] != pytest.approx(
        b["derived_quantities"]["friction_force_N"],
    )


def test_energy_ledger_residual() -> None:
    rep = solve_mechanics(_req())
    eb = rep["energy_balance"]
    assert eb["residual_J"] == pytest.approx(0.0, abs=1e-9)
    vo = verify_engineering_report(rep)
    assert vo["tolerance_results"]["energy_residual_J"] <= 1e-5


def test_fixtures_are_valid_json() -> None:
    json.loads((FIX / "materials_v1.json").read_text(encoding="utf-8"))
    json.loads((FIX / "fluids_v1.json").read_text(encoding="utf-8"))
