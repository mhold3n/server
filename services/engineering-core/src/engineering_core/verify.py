"""
verify_engineering_report: deterministic checks → verification_outcome JSON.

For agents: check names are fixed enum; per-check status is PASS|FAIL only.
"""

from __future__ import annotations

from typing import Any

CHECK_NAMES = (
    "REQUIRED_FIELDS_PRESENT",
    "MASS_CONSISTENCY",
    "FORCE_BALANCE",
    "ENERGY_BALANCE",
    "NONNEGATIVE_DISSIPATION",
)

TOL_FORCE = 1e-6
TOL_ENERGY = 1e-5
TOL_MASS = 1e-9


def _check(
    name: str,
    ok: bool,
    details: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": "PASS" if ok else "FAIL",
        "details": details,
    }


def verify_engineering_report(report: dict[str, Any]) -> dict[str, Any]:
    """Return a dict matching verification_outcome.schema.json."""
    checks: list[dict[str, Any]] = []
    blocking: list[str] = []
    tolerance_results: dict[str, float] = {}

    required_top = (
        "schema_version",
        "results",
        "energy_balance",
        "inputs",
        "derived_quantities",
    )
    missing = [k for k in required_top if k not in report]
    ok_fields = len(missing) == 0
    checks.append(
        _check(
            "REQUIRED_FIELDS_PRESENT",
            ok_fields,
            "ok" if ok_fields else f"missing: {missing}",
        ),
    )
    if not ok_fields:
        blocking.append("missing required report fields")

    results = report.get("results", {})
    energy = report.get("energy_balance", {})
    inputs = report.get("inputs", {})
    derived = report.get("derived_quantities", {})

    mass_consistent = True
    mass_detail = "skipped"
    if ok_fields and "cube_side_m" in inputs and "block_material_id" in inputs:
        side = float(inputs["cube_side_m"])
        vol = side**3
        from engineering_core.reference_mechanics import load_materials, mass_kg_from_cube

        try:
            mats = load_materials()
            m_expected = mass_kg_from_cube(mats, inputs["block_material_id"], side)
            m_reported = float(derived.get("mass_kg", -1.0))
            err = abs(m_reported - m_expected)
            tolerance_results["mass_error_kg"] = err
            mass_consistent = err <= TOL_MASS
            mass_detail = f"expected_mass_kg={m_expected}, reported={m_reported}, err={err}"
        except Exception as e:  # noqa: BLE001
            mass_consistent = False
            mass_detail = str(e)
    checks.append(_check("MASS_CONSISTENCY", mass_consistent, mass_detail))
    if not mass_consistent:
        blocking.append("mass inconsistency")

    force_ok = True
    force_detail = "skipped"
    if ok_fields and "mass_kg" in derived:
        m = float(derived["mass_kg"])
        a = float(results.get("acceleration_mps2", 0.0))
        f_applied = float(inputs.get("applied_force_N", 0.0))
        resisting = float(results.get("resisting_force_N", 0.0))
        f_net = f_applied - resisting
        if abs(a) < 1e-12:
            err = abs(f_net)
            tolerance_results["force_balance_error"] = err
            force_ok = abs(f_applied) <= resisting + TOL_FORCE
            force_detail = f"static/no_accel: |F_applied - R|={err}, applied<=R+tol"
        else:
            err = abs(f_net - m * a)
            tolerance_results["force_balance_error"] = err
            force_ok = err <= TOL_FORCE
            force_detail = f"|(F_applied-R) - m*a| = {err}"
    checks.append(_check("FORCE_BALANCE", force_ok, force_detail))
    if not force_ok:
        blocking.append("force balance")

    w = float(energy.get("work_in_J", 0.0))
    dke = float(energy.get("kinetic_energy_change_J", 0.0))
    diss = float(energy.get("dissipated_J", 0.0))
    res = float(energy.get("residual_J", 0.0))
    ledger = abs(w - dke - diss - res)
    tolerance_results["energy_residual_J"] = ledger
    energy_ok = ledger <= TOL_ENERGY
    checks.append(
        _check(
            "ENERGY_BALANCE",
            energy_ok,
            f"|work - dke - diss - residual| = {ledger}",
        ),
    )
    if not energy_ok:
        blocking.append("energy ledger")

    diss_ok = float(results.get("heat_dissipation_J", -1.0)) >= 0.0
    checks.append(
        _check(
            "NONNEGATIVE_DISSIPATION",
            diss_ok,
            "heat_dissipation_J >= 0" if diss_ok else "negative dissipation",
        ),
    )
    if not diss_ok:
        blocking.append("negative dissipation")

    all_pass = all(c["status"] == "PASS" for c in checks)
    status = "PASS" if all_pass else "REWORK"

    return {
        "status": status,
        "checks": checks,
        "blocking_issues": blocking,
        "tolerance_results": tolerance_results,
    }
