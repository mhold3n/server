---
name: deterministic-stack-governance
description: Deterministically allocate compute budgets, permission boundaries, and communication paths for tasks in the R&D orchestration stack. Use when work must enforce policy-driven source selection, output quality, relevance checks, and stable response structure across `structure/` gateway, router, validator, runtime, and policy files.
---

# Deterministic Stack Governance

Enforce a fixed control loop that converts any task request into a deterministic governance contract before implementation or execution.

## Workflow

1. Normalize the request into a small JSON payload with only stable fields:
   - `task_id`
   - `user_goal`
   - `complexity` (`low|medium|high`)
   - `sensitivity` (`public|internal|confidential|restricted`)
   - `determinism_level` (`D1|D2|NONE`)
   - `requires_external_sources` (`true|false`)
   - `side_effects` (`none|file_write|network|code_exec`)
2. Build the contract using `scripts/build_governance_contract.py`.
3. Apply contract decisions in this order:
   - Resource allocation
   - Permission mode and escalation requirements
   - Clarify/block communication behavior
   - Output contract checks (source, quality, relevance, structure)
4. Emit final decisions as canonical JSON (`indent=2`, sorted keys, no extra fields).

## Command

Run:

```bash
python scripts/build_governance_contract.py \
  --stack-root ../../ \
  --input-json '{"task_id":"t1","user_goal":"...","complexity":"medium","sensitivity":"internal","determinism_level":"D2","requires_external_sources":false,"side_effects":"file_write"}'
```

Use `--input-file` for larger payloads.

## Decision Rules

- Read `references/stack_control_map.md` once at the start of a task to locate authoritative controls.
- Prefer the strictest applicable policy when controls conflict.
- Treat missing policy files as configuration errors and fail closed.
- Use deterministic defaults:
  - LLM extraction with `temperature=0.0`, fixed seed, bounded retries
  - No speculative execution under D1/D2
  - No write/delete actions beyond declared policy and approval gates
- Require clarification instead of guessing when ambiguity is unresolved.

## Output Contract

Always require output sections defined in this canonical order:

1. `source_policy`
2. `quality_policy`
3. `relevance_policy`
4. `structure_policy`
5. `resource_allocation`
6. `permission_policy`
7. `communication_policy`
8. `enforcement_sequence`

Serialize with sorted keys for byte-stable output, and use the `required_sections` list as the canonical semantic order. Load `references/output_contract.schema.json` when validating downstream response shape.

## Adaptation Boundaries

- Adjust thresholds only through policy files under `structure/policies/`.
- Do not hardcode ad hoc exceptions in task-specific prompts.
- Keep contract synthesis deterministic and side-effect free.
