---
{
  "application_rules": [
    "Identify governing equations, variable scales, constraints, and likely stiffness before selecting an algorithm.",
    "Prefer bounded, schema-governed runtime calls when execution artifacts must be reproducible.",
    "Keep units and tolerances explicit in task packets and verification criteria."
  ],
  "label": "Numerical Solver Selection",
  "module_refs": [
    "artifact://module-card/numerical_solver_stack"
  ],
  "schema_version": "1.0.0",
  "summary": "Choose numerical solvers by equation class, stiffness, constraints, sensitivity, units, and validation anchors.",
  "technique_card_id": "numerical_solver_selection",
  "technique_key": "numerical_solver_selection",
  "theory_refs": [
    "artifact://theory-card/computational_engineering_numerical_methods"
  ],
  "verification_rules": [
    "Check conservation, residual, or objective convergence against an isolated reference case.",
    "Run a dimensional sanity check before accepting numerical output.",
    "Record solver assumptions and failure signatures in the produced artifact."
  ],
  "wiki_shard": "techniques",
  "wiki_zone": "orchestration"
}
---

Choose numerical solvers by equation class, stiffness, constraints, sensitivity, units, and validation anchors.
