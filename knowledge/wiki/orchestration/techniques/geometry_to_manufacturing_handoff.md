---
{
  "application_rules": [
    "Preserve design intent, tolerances, datum assumptions, and manufacturing exclusions.",
    "Separate construction geometry from exported manufacturing or simulation geometry.",
    "Attach inspection and downstream mesh requirements to the handoff artifact."
  ],
  "label": "Geometry-to-Manufacturing Handoff",
  "module_refs": [
    "artifact://module-card/manufacturing_geometry_stack"
  ],
  "schema_version": "1.0.0",
  "summary": "Translate CAD/geometry modules into manufacturable, inspectable, and simulation-ready artifacts.",
  "technique_card_id": "geometry_to_manufacturing_handoff",
  "technique_key": "geometry_to_manufacturing_handoff",
  "theory_refs": [
    "artifact://theory-card/manufacturing_process_basis"
  ],
  "verification_rules": [
    "Check exported geometry for watertightness, units, feature naming, and tolerance-critical surfaces.",
    "Confirm the manufacturing process can realize the selected features and tolerances.",
    "Validate meshability or downstream solver compatibility before using geometry in simulation."
  ],
  "wiki_shard": "techniques",
  "wiki_zone": "orchestration"
}
---

Translate CAD/geometry modules into manufacturable, inspectable, and simulation-ready artifacts.
