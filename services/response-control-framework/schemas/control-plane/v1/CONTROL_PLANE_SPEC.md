# Control plane — canonical state, merge, and verification (v1)

<!--
For agents: operational semantics that JSON Schema cannot express alone. Pair with
`*.schema.json` for field-level contracts and with `PROVENANCE_AND_SECURITY.md` for logging.
-->

## Artifact truth model

- **Authoritative payloads** are versioned JSON objects identified by `artifact://…` refs and stored under the typed envelope (`artifact-record.schema.json`) or as standalone files that validate against the same schemas.
- **Problem brief** (`problem-brief.schema.json`) is the root scope contract; **engineering state** (`engineering-state.schema.json`) is the merged technical truth for routing and decomposition; **task queue** (`task-queue.schema.json`) is the execution DAG over **task packets** only (no embedded chat).

## Merge and conflict rules

1. **Single writer per artifact type per trace**: only one `ACTIVE` `PROBLEM_BRIEF` per `trace_id` unless an explicit branch is opened (separate `trace_id`).
2. **Engineering state supersession**: a new `engineering_state` artifact must list prior evidence in `evidence_bundle_refs` and bump `merge_policy_version` when merge semantics change.
3. **Conflicts**: every open conflict must appear in `engineering_state.conflicts` with `resolution_status=open|escalated|resolved|waived`. Escalation to the strategic model is driven by `routing-policy.schema.json` + `verification-report.schema.json`, not ad-hoc prose.
4. **Staleness**: `staleness[]` records which evidence artifacts are outdated and why; routers must not treat stale artifacts as premises for new task packets without an explicit refresh task.

## Verification gates

- **Gate rows** live on `verification_report.gate_results` (`gate_kind`: schema, units, numeric_sanity, tests, citations, policy, simulation, custom).
- **Outcomes**: `PASS` | `REWORK` | `ESCALATE` on the report; `REWORK`/`ESCALATE` require `blocking_findings` per schema.
- **Deterministic validators** should emit `gate_results` with `status=FAIL` before suggesting `ESCALATE`.

## Failure / recovery (summary)

| Situation | Expected control-plane reaction |
|-----------|-----------------------------------|
| Schema / unit gate fails | `REWORK` with remediation in `gate_results[].remediation_hint` |
| Open conflicts exceed policy threshold | `ESCALATE` after `verification_report` with `recommended_next_action=create_escalation_packet` |
| Evidence stale | Block downstream `task_packet` creation until refresh task completes |

## Determinism

- Serialize JSON with stable key ordering in golden tests; floats in engineering payloads should be written with explicit units (`quantifiedScalar`) not bare floats in mixed-unit contexts.
