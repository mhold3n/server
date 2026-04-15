---
{
  "application_rules": [
    "State load paths, boundary conditions, material assumptions, and simplifications before model execution.",
    "Keep geometry preparation separate from solver setup when manufacturing constraints are active.",
    "Select elements and discretization according to the expected field behavior."
  ],
  "label": "FEM Model Verification",
  "module_refs": [
    "artifact://module-card/fem_solver_stack"
  ],
  "schema_version": "1.0.0",
  "summary": "Apply finite-element modules with explicit boundary conditions, mesh convergence, and reference-case checks.",
  "technique_card_id": "fem_model_verification",
  "technique_key": "fem_model_verification",
  "theory_refs": [
    "artifact://theory-card/mechanical_engineering_mechanics_basis",
    "artifact://theory-card/computational_engineering_numerical_methods"
  ],
  "verification_rules": [
    "Require mesh convergence or sensitivity evidence for governed conclusions.",
    "Compare against a closed-form, benchmark, or simplified static reference where possible.",
    "Flag singular constraints, unconstrained rigid-body motion, and nonphysical stress concentrations."
  ],
  "wiki_shard": "techniques",
  "wiki_zone": "orchestration"
}
---

Apply finite-element modules with explicit boundary conditions, mesh convergence, and reference-case checks.
