---
{
  "assumptions": [
    "Default process capability should be treated as provisional unless a specific machine/process is named.",
    "Inspection strategy is part of acceptance when tolerances are function-critical."
  ],
  "interpretation_rules": [
    "Do not infer manufacturability from CAD validity alone.",
    "Surface hidden tolerance or inspection assumptions as open issues."
  ],
  "label": "Manufacturing Process Basis",
  "pool_ref": "artifact://knowledge-pool/manufacturing",
  "principles": [
    "Geometry is not manufacturable until process constraints, tolerance stackups, and inspection methods are considered.",
    "Design intent must survive translation from CAD to manufacturing and simulation artifacts.",
    "Process capability sets practical limits on achievable geometry and tolerances."
  ],
  "reference_points": [
    "Units and datum consistency between CAD, mesh, and manufacturing outputs.",
    "Tolerance-critical feature list.",
    "Process-feasibility check against named manufacturing route."
  ],
  "schema_version": "1.0.0",
  "source_refs": [
    "internal://engineering-theory/manufacturing",
    "standards://manufacturing-reference-data"
  ],
  "summary": "Manufacturing basis for process capability, feature feasibility, tolerancing, inspection, and geometry handoff.",
  "theory_card_id": "manufacturing_process_basis",
  "theory_key": "manufacturing_process_basis",
  "wiki_shard": "theory",
  "wiki_zone": "orchestration"
}
---

Manufacturing basis for process capability, feature feasibility, tolerancing, inspection, and geometry handoff.
