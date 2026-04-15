---
{
  "application_rules": [
    "Define flow regime, boundary conditions, discretization, and turbulence/transport assumptions up front.",
    "Track conservation quantities and residual targets as acceptance criteria.",
    "Keep mesh/domain sensitivity visible when results drive engineering decisions."
  ],
  "label": "CFD Conservation Verification",
  "module_refs": [
    "artifact://module-card/cfd_solver_stack"
  ],
  "schema_version": "1.0.0",
  "summary": "Apply CFD modules with explicit transport assumptions, boundary discipline, and conservation checks.",
  "technique_card_id": "cfd_conservation_verification",
  "technique_key": "cfd_conservation_verification",
  "theory_refs": [
    "artifact://theory-card/computational_engineering_numerical_methods"
  ],
  "verification_rules": [
    "Check mass, momentum, energy, or species balances against the stated model.",
    "Verify residuals and monitored quantities stabilize together.",
    "Compare against a benchmark or simplified reference flow when available."
  ],
  "wiki_shard": "techniques",
  "wiki_zone": "orchestration"
}
---

Apply CFD modules with explicit transport assumptions, boundary discipline, and conservation checks.
