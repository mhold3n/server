# Control plane JSON Schema registry (Draft 2020-12)

<!--
For agents: this directory is the canonical contract surface for unified control-plane
artifacts (`task_packet`, typed `artifact_record`, verification outcomes, escalation).
Runtime validators in `services/api` load these files by path; `$id` URIs are stable
identifiers for cross-ref gates and documentation.
-->

## Layout

| Path | Purpose |
|------|---------|
| `registry.json` | Machine-readable manifest: `$id`, relative path, contract kind |
| `common.schema.json` | Shared `$defs` (enums, primitives, reusable objects) |
| `problem-brief.schema.json` | Stage 0 root intent: scope, deliverables, acceptance tests |
| `knowledge-pack.schema.json` | Shared external knowledge substrate artifact |
| `recipe-object.schema.json` | Task-class recipe object linked from packs |
| `execution-adapter-spec.schema.json` | Typed execution adapter/tool contract |
| `evidence-bundle.schema.json` | Validation/evidence harness artifact |
| `role-context-bundle.schema.json` | Role-specific context compilation artifact |
| `environment-spec.schema.json` | Manifest-backed runtime environment contract |
| `decision-log.schema.json` | Stack selection and tradeoff record |
| `task-packet.schema.json` | Specialist execution contract |
| `task-queue.schema.json` | DAG of `task_packet` refs + approvals |
| `engineering-state.schema.json` | Canonical merged variables, evidence, conflicts, staleness |
| `routing-policy.schema.json` | Router version, budgets, escalation rules, plane/tool matrix |
| `artifact-record.schema.json` | Artifact envelope + lifecycle metadata |
| `verification-report.schema.json` | Gate rows + outcome (`PASS` / `REWORK` / `ESCALATE`) |
| `escalation-packet.schema.json` | Escalation artifact |
| `contract-error.schema.json` | Structured validation / contract failure envelope |
| `control-plane.bundle.schema.json` | Discriminated union for API ingress |
| `CONTROL_PLANE_SPEC.md` | Merge/conflict/staleness semantics (non-JSON) |
| `PROVENANCE_AND_SECURITY.md` | Logging, replay, local sandbox expectations |
| `ROUTING_POLICY.md` | Human narrative for `routing-policy.schema.json` |
| `fixtures/<contract>/` | Golden valid/invalid JSON fixtures for CI |

## `$id` namespace

Base: `https://birtha.local/schemas/control-plane/v1/`

All cross-file `$ref` values use absolute `$id` URIs (no relative filesystem refs in persisted payloads).

## Versioning

- Directory `v1/` is a major boundary. Breaking changes require `v2/` and new `$id` prefix.
- Per-contract `schema_version` inside instances uses SemVer strings (e.g. `1.0.0`).

## Governance notes (v1 discipline)

- **Freeze `taskTypeEnum` growth**: adding new execution `task_type` values increases the risk of `task_packet`
  creeping back into a universal envelope. Treat any new execution type as a design change requiring an explicit
  review decision (why it is a distinct execution class vs a parameterization of an existing type).
- **Subsystem test matrix vs. monolith tests**: large `services/api` pytest counts are useful repo regression signals,
  but do not directly prove harness correctness. For the local engineering harness, the probative tests are:
  - `python scripts/validate_control_plane_schemas.py`
  - `python scripts/validate_model_runtime_schemas.py`
  - `services/engineering-core` goldens (`pytest services/engineering-core/tests`)
  - `services/model-runtime` HTTP/validator tests (`pytest services/model-runtime/tests`)
  - `services/agent-platform/server` harness tests (`npm test`)

## CI gate order (recommended)

1. Schema compile + lint (Draft 2020-12, duplicate `$id`, `$defs` keys)
2. Cross-ref resolution against `registry.json`
3. Golden fixtures (`python scripts/validate_control_plane_schemas.py`)
4. Runtime write-path tests (API / pytest)
5. Consumer conformance (Pydantic ↔ JSON Schema round-trip where applicable)

## Validation script

From repo root:

```bash
python scripts/validate_control_plane_schemas.py
```

Requires `jsonschema` (see `services/api` optional dev deps or `pip install jsonschema`).
