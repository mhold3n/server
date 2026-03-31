# Stack Control Map

Use this map to keep governance decisions tied to authoritative files in `structure/`.

## Source of Truth by Control Area

| Control Area | Primary File | What It Controls |
|---|---|---|
| Determinism levels and prohibitions | `policies/determinism.yaml` | D1/D2/NONE requirements, cache keys, prohibited non-deterministic behavior |
| Budget ceilings | `policies/budgets.yaml` | Kernel time, token limits, retry ceilings, escalation thresholds |
| Write permissions and sandbox limits | `policies/file_write_policy.yaml` | Allowed directories, denied patterns, delete approval requirements |
| LLM extraction mode and fallback | `policies/llm_extraction.yaml` | Local/openrouter routing rules, retry bounds, extraction constraints |
| Domain-quality checks | `policies/data_analysis.yaml` | Gate order, minimum data quality requirements, reproducibility requirements |
| Runtime access enforcement | `runtime/orchestrator.py`, `gateway/compliance.py` | Access checks, gate blocking behavior, audit behavior |
| Validation gate behavior | `validator/gates.py`, `docs/VALIDATION_GATES.md` | Gate decision semantics: PASS/CLARIFY/BLOCK |
| Contract schemas | `schemas/*.json` | Structural constraints for request/spec/output payloads |

## Deterministic Resolution Order

1. Load policy files.
2. Validate task payload shape and enum values.
3. Allocate resource budget from `budgets.yaml`.
4. Apply permission constraints from `file_write_policy.yaml`.
5. Apply determinism and cache constraints from `determinism.yaml`.
6. Select communication behavior (clarify/block/escalate) from gates and sensitivity.
7. Emit contract as canonical JSON.

## Conflict Rule

When two controls disagree, choose the stricter constraint and record the chosen source path.

## Non-Negotiable Constraints

- Never bypass gate-based block decisions.
- Never allow delete without explicit approval.
- Never produce unstructured output when a schema exists.
- Never treat unsourced claims as acceptable in D1/D2 paths.
