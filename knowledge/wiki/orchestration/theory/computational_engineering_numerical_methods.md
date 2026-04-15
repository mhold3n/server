---
{
  "assumptions": [
    "Numerical tolerances are problem-specific and must be recorded.",
    "Local runtime behavior is not trusted without a deterministic or benchmark-backed check."
  ],
  "interpretation_rules": [
    "Treat numerical output as evidence only when solver assumptions and verification checks are visible.",
    "Escalate rather than silently accepting unstable or unconverged results."
  ],
  "label": "Computational Engineering Numerical Methods",
  "pool_ref": "artifact://knowledge-pool/computational_engineering",
  "principles": [
    "Algorithm choice follows equation class, scale, stiffness, constraints, and required confidence.",
    "Convergence, conservation, and sensitivity checks are part of the result, not optional commentary.",
    "Execution context must be bounded and reproducible for governed engineering runs."
  ],
  "reference_points": [
    "Dimensional sanity checks.",
    "Residual and objective convergence traces.",
    "Known benchmark or simplified reference cases."
  ],
  "schema_version": "1.0.0",
  "source_refs": [
    "internal://engineering-theory/numerical-methods",
    "internal://runtime-verification/benchmark-cases"
  ],
  "summary": "Numerical-method basis for solver selection, discretization, convergence, stability, sensitivity, and reproducible execution.",
  "theory_card_id": "computational_engineering_numerical_methods",
  "theory_key": "computational_engineering_numerical_methods",
  "wiki_shard": "theory",
  "wiki_zone": "orchestration"
}
---

Numerical-method basis for solver selection, discretization, convergence, stability, sensitivity, and reproducible execution.
