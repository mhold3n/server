---
{
  "application_rules": [
    "Treat mode, pool, and module selection as Python control-plane decisions before donor orchestration begins.",
    "Route coding_model packets to Claw through the agent-platform adapter; route non-coding orchestration to merged OMA.",
    "Pass selected refs and compact summaries to executors, not mutable orchestration policy."
  ],
  "label": "Artifact-First Task Graph Execution",
  "module_refs": [
    "artifact://module-card/engineering_orchestration_stack"
  ],
  "schema_version": "1.0.0",
  "summary": "Apply explicit task packets, selected refs, and shared result digests without direct agent-to-agent messaging.",
  "technique_card_id": "artifact_first_task_graph_execution",
  "technique_key": "artifact_first_task_graph_execution",
  "theory_refs": [
    "artifact://theory-card/computational_engineering_numerical_methods"
  ],
  "verification_rules": [
    "Confirm task packets include response_control_ref and selected pool/module/technique/theory refs.",
    "Confirm routing_metadata.selected_executor remains stable and explicit.",
    "Confirm Claw receives translated execution context only."
  ],
  "wiki_shard": "techniques",
  "wiki_zone": "orchestration"
}
---

Apply explicit task packets, selected refs, and shared result digests without direct agent-to-agent messaging.
