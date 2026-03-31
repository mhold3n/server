#!/usr/bin/env python3
"""Build a deterministic governance contract for the structure stack."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict

import yaml

COMPLEXITY_VALUES = {"low", "medium", "high"}
SENSITIVITY_VALUES = {"public", "internal", "confidential", "restricted"}
DETERMINISM_VALUES = {"D1", "D2", "NONE"}
SIDE_EFFECT_VALUES = {"none", "file_write", "network", "code_exec"}

REQUIRED_FIELDS = {
    "task_id",
    "user_goal",
    "complexity",
    "sensitivity",
    "determinism_level",
    "requires_external_sources",
    "side_effects",
}

POLICY_FILES = {
    "budgets": "policies/budgets.yaml",
    "determinism": "policies/determinism.yaml",
    "file_write": "policies/file_write_policy.yaml",
    "llm_extraction": "policies/llm_extraction.yaml",
    "data_analysis": "policies/data_analysis.yaml",
}

REQUIRED_OUTPUT_SECTIONS = [
    "source_policy",
    "quality_policy",
    "relevance_policy",
    "structure_policy",
    "resource_allocation",
    "permission_policy",
    "communication_policy",
    "enforcement_sequence",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate deterministic governance contract JSON."
    )
    parser.add_argument(
        "--stack-root",
        required=True,
        help="Path to structure stack root containing policies/",
    )
    parser.add_argument(
        "--input-json",
        help="Inline JSON task payload.",
    )
    parser.add_argument(
        "--input-file",
        help="Path to JSON file containing task payload.",
    )
    return parser.parse_args()


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required policy file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Policy file must deserialize to mapping: {path}")
    return payload


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_task_payload(args: argparse.Namespace) -> Dict[str, Any]:
    if bool(args.input_json) == bool(args.input_file):
        raise ValueError("Pass exactly one of --input-json or --input-file.")

    if args.input_json:
        payload = json.loads(args.input_json)
    else:
        with Path(args.input_file).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError("Task payload must be a JSON object.")
    return payload


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_payload(payload: Dict[str, Any]) -> None:
    missing = sorted(REQUIRED_FIELDS - set(payload.keys()))
    require(not missing, f"Missing required payload fields: {', '.join(missing)}")

    require(
        payload["complexity"] in COMPLEXITY_VALUES,
        f"complexity must be one of {sorted(COMPLEXITY_VALUES)}",
    )
    require(
        payload["sensitivity"] in SENSITIVITY_VALUES,
        f"sensitivity must be one of {sorted(SENSITIVITY_VALUES)}",
    )
    require(
        payload["determinism_level"] in DETERMINISM_VALUES,
        f"determinism_level must be one of {sorted(DETERMINISM_VALUES)}",
    )
    require(
        payload["side_effects"] in SIDE_EFFECT_VALUES,
        f"side_effects must be one of {sorted(SIDE_EFFECT_VALUES)}",
    )
    require(
        isinstance(payload["requires_external_sources"], bool),
        "requires_external_sources must be boolean",
    )


def complexity_factor(complexity: str) -> float:
    return {"low": 0.35, "medium": 0.6, "high": 0.85}[complexity]


def llm_call_cap(complexity: str) -> int:
    return {"low": 2, "medium": 4, "high": 6}[complexity]


def build_contract(
    payload: Dict[str, Any],
    policies: Dict[str, Dict[str, Any]],
    policy_digests: Dict[str, str],
) -> Dict[str, Any]:
    budgets = policies["budgets"]
    determinism = policies["determinism"]
    file_write = policies["file_write"]
    llm_extraction = policies["llm_extraction"]
    data_analysis = policies["data_analysis"]

    compute = budgets["compute"]
    det_level = payload["determinism_level"]
    complexity = payload["complexity"]
    sensitivity = payload["sensitivity"]
    side_effects = payload["side_effects"]
    external = payload["requires_external_sources"]

    max_llm_calls = min(
        compute["max_llm_calls_per_session"],
        llm_call_cap(complexity) + (1 if external else 0),
    )
    max_llm_tokens = min(
        compute["max_llm_tokens_per_request"],
        int(compute["max_llm_tokens_per_request"] * complexity_factor(complexity)),
    )
    max_kernel_time_ms = int(
        compute["max_kernel_execution_time_ms"] * complexity_factor(complexity)
    )

    if det_level == "D2":
        retries = min(1, compute["max_retries_per_stage"])
    elif det_level == "D1":
        retries = min(2, compute["max_retries_per_stage"])
    else:
        retries = compute["max_retries_per_stage"]

    default_mode = llm_extraction["mode_selection"]["default"]
    llm_mode = default_mode
    if complexity == "high" or external:
        llm_mode = "openrouter"

    source_scope = "internal_only"
    if external:
        source_scope = "internal_plus_approved_external"
    if det_level == "D2" and not external:
        source_scope = "strict_internal_only"

    permission_mode = "read_only"
    if side_effects == "file_write":
        permission_mode = file_write["default_mode"]
    elif side_effects in {"network", "code_exec"}:
        permission_mode = "restricted"

    escalation_required = (
        sensitivity in {"confidential", "restricted"} or side_effects == "code_exec"
    )

    ambiguity_gate = data_analysis["gates"]["execution_order"][0]
    quality_gate = data_analysis["gates"]["execution_order"][1]

    contract = {
        "contract_version": "1.0.0",
        "task_id": payload["task_id"],
        "policy_inputs": {
            name: {
                "path": POLICY_FILES[name],
                "sha256": policy_digests[name],
            }
            for name in sorted(POLICY_FILES)
        },
        "source_policy": {
            "mode": source_scope,
            "citation_required": True,
            "allow_derived_claims_without_source": False,
            "preferred_sources": [
                "registry",
                "schemas",
                "policies",
                "kernel_outputs",
            ],
            "external_source_rules": {
                "allowed": external,
                "require_primary_source": True,
                "require_retrieval_timestamp": True,
            },
        },
        "quality_policy": {
            "require_schema_validation": True,
            "required_gates": [ambiguity_gate, quality_gate],
            "determinism_level": det_level,
            "max_retries_per_stage": retries,
            "acceptance": {
                "error_rate_percent_max": budgets["escalation_thresholds"][
                    "error_rate_percent"
                ],
                "latency_p99_ms_max": budgets["escalation_thresholds"][
                    "latency_p99_ms"
                ],
            },
        },
        "relevance_policy": {
            "require_goal_traceability": True,
            "max_unattributed_claims": 0 if det_level in {"D1", "D2"} else 1,
            "ambiguity_action": "clarify",
            "out_of_scope_action": "block",
        },
        "structure_policy": {
            "format": "json",
            "sorted_keys": True,
            "required_sections": REQUIRED_OUTPUT_SECTIONS,
            "forbid_extra_top_level_sections": True,
        },
        "resource_allocation": {
            "max_kernel_execution_time_ms": max_kernel_time_ms,
            "max_llm_tokens_per_request": max_llm_tokens,
            "max_llm_calls_per_session": max_llm_calls,
            "max_retries_per_stage": retries,
            "llm_mode": llm_mode,
            "cache": {
                "key_components": determinism["caching"]["key_components"],
                "cacheable": determinism["caching"]["cacheable"],
                "never_cacheable": determinism["caching"]["never_cacheable"],
            },
        },
        "permission_policy": {
            "mode": permission_mode,
            "allowed_directories": file_write["allowed_directories"],
            "denied_patterns": file_write["denied_patterns"],
            "delete_requires_approval": file_write["operations"]["delete"][
                "requires_approval"
            ],
            "escalation_required": escalation_required,
            "escalation_reason": (
                "sensitivity_or_code_execution"
                if escalation_required
                else "none"
            ),
        },
        "communication_policy": {
            "clarify_on_ambiguity": True,
            "clarify_questions_max": 3,
            "block_conditions": [
                "gate_failure",
                "access_denied",
                "budget_exceeded",
                "policy_violation",
            ],
            "user_update_milestones": [
                "contract_built",
                "gates_evaluated",
                "execution_complete",
            ],
            "escalation_target": (
                "security_admin"
                if escalation_required
                else "task_owner"
            ),
        },
        "enforcement_sequence": [
            "validate_payload",
            "load_policy_files",
            "synthesize_resource_allocation",
            "apply_permission_controls",
            "apply_ambiguity_and_quality_gates",
            "validate_response_structure",
            "emit_canonical_contract",
        ],
    }
    return contract


def main() -> int:
    try:
        args = parse_args()
        payload = load_task_payload(args)
        validate_payload(payload)

        stack_root = Path(args.stack_root).resolve()
        policies: Dict[str, Dict[str, Any]] = {}
        policy_digests: Dict[str, str] = {}
        for name, rel_path in POLICY_FILES.items():
            file_path = stack_root / rel_path
            policies[name] = load_yaml(file_path)
            policy_digests[name] = digest_file(file_path)

        contract = build_contract(payload, policies, policy_digests)
        print(json.dumps(contract, indent=2, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
