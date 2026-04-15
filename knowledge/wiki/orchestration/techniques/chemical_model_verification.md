---
{
  "application_rules": [
    "State species set, mechanism scope, thermodynamic basis, and reaction assumptions before execution.",
    "Separate chemical-domain assumptions from numerical-solver choices.",
    "Keep units, temperature/pressure ranges, and source provenance visible."
  ],
  "label": "Chemical Model Verification",
  "module_refs": [
    "artifact://module-card/chemical_modeling_stack"
  ],
  "schema_version": "1.0.0",
  "summary": "Apply chemical modeling modules with species, mechanisms, thermochemistry, and kinetic assumptions kept explicit.",
  "technique_card_id": "chemical_model_verification",
  "technique_key": "chemical_model_verification",
  "theory_refs": [
    "artifact://theory-card/chemistry_chemical_modeling_basis"
  ],
  "verification_rules": [
    "Check elemental balance and reaction stoichiometry before accepting mechanism output.",
    "Compare calculated properties or rates against static reference points when available.",
    "Flag extrapolation beyond source data or model validity ranges."
  ],
  "wiki_shard": "techniques",
  "wiki_zone": "orchestration"
}
---

Apply chemical modeling modules with species, mechanisms, thermochemistry, and kinetic assumptions kept explicit.
