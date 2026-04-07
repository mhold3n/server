# Schemas

## Inventory

- schemas/session_envelope.schema.json
- schemas/problem_spec.schema.json
- schemas/constraint_ast.schema.json
- schemas/gate_decision.schema.json
- schemas/run_manifest.schema.json
- schemas/kernel_io.schema.json
- schemas/patch_plan.schema.json
- schemas/task_request.schema.json
- schemas/task_plan.schema.json
- schemas/task_dossier.schema.json
- schemas/ambiguity_report.schema.json *(NEW)*
- schemas/diagnostic_spec.schema.json *(NEW)*

## Versioning policy

- Semver rules:
- Backwards compatibility rules:
- Deprecation process:

## Enforcement

- Where schemas are validated:
  - `task_request.schema.json` validates dev-plane intake payloads and clarification context.
  - `task_plan.schema.json` validates normalized code-task plans, including delegation hints and explicit verification blocks used for internal execution handoff.
  - `task_dossier.schema.json` validates final run dossiers, including workspace metadata and emitted artifacts.
- Failure behavior:
