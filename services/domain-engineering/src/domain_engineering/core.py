"""Engineering-governed control-plane helpers.

This module turns existing control-plane contracts into executable policy:
legacy chat/task-plan/task-packet inputs are bridged into a structured
``problem_brief``; a deterministic derivation creates ``engineering_state``;
and decomposition into ``task_queue`` / ``task_packet`` is blocked until the
governing artifacts are valid and ready.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import NAMESPACE_URL, uuid4, uuid5

from ai_shared_service.domain_classifier import DomainClassifier
from response_control_framework.contracts import (
    AnalysisPathway,
    ArtifactType,
    AssumptionSpec,
    AssumptionStatusRecord,
    BudgetPolicy,
    CodeGuidance,
    ConflictRecord,
    ConstraintProvenance,
    ConstraintSpec,
    DeliverableSpec,
    DesignSpace,
    DesignVariableSpec,
    EngineeringState,
    EscalationPacket,
    EscalationReason,
    EvidenceInput,
    Executor,
    HumanApprovalBlock,
    KnowledgeCoverageClass,
    KnowledgePoolAssessment,
    ObjectiveRecord,
    OpenIssueRecord,
    OperationalContext,
    OperationalScenario,
    Priority,
    ProblemBrief,
    ProblemBriefProvenance,
    ProblemStatement,
    Producer,
    QueueStatus,
    RequiredGateRecord,
    RequiredOutputSpec,
    ResponseControlAssessment,
    RoutingMetadata,
    StateConstraint,
    StateVariable,
    SuccessCriterion,
    SystemBoundary,
    TaskPacket,
    TaskPacketStatus,
    TaskQueue,
    TaskQueueApproval,
    TaskQueueItem,
    TaskType,
    UnknownItem,
    VerificationIntentRow,
    WikiEditKind,
)
from response_control_framework.knowledge_pool import (
    load_knowledge_pool,
    resolve_engineering_knowledge_pool_root,
)
from response_control_framework.response_control import (
    evaluate_response_control,
    response_control_artifact_ref,
    selected_response_control_refs,
)
from response_control_framework.validation import (
    validate_engineering_state_json,
    validate_knowledge_pool_assessment_json,
    validate_problem_brief_json,
    validate_response_control_assessment_json,
    validate_task_packet_json,
    validate_task_queue_json,
)
from response_control_framework.wiki_proposals import (
    create_proposal,
    resolve_wiki_overlay_context,
)

_ENGINEERING_HINTS = (
    "architecture",
    "workflow",
    "orchestr",
    "schema",
    "contract",
    "decompose",
    "analysis",
    "simulate",
    "simulation",
    "verification",
    "parser",
    "refactor",
    "multi-file",
    "multiple files",
    "codebase",
    "repository",
    "system design",
    "engineering",
)

_MODE_ORDER = (
    "casual_chat",
    "ideation",
    "napkin_math",
    "engineering_task",
    "strict_engineering",
)
_MODE_RANK = {mode: index for index, mode in enumerate(_MODE_ORDER)}
_ENGINEERING_MODES = {"engineering_task", "strict_engineering"}
_QUANTITATIVE_HINTS = (
    "calculate",
    "derive",
    "estimate",
    "equation",
    "formula",
    "quantitative",
    "backlash",
    "phase accuracy",
    "thermal growth",
    "tolerance",
    "stress",
    "strain",
    "torque",
)
_IDEATION_HINTS = (
    "brainstorm",
    "ideas",
    "concept",
    "explore",
    "what if",
    "possible approaches",
    "tradeoffs",
)
_CODING_HINTS = (
    "implement",
    "code",
    "refactor",
    "patch",
    "edit",
    "fix",
    "test",
    "repository",
    "repo",
    "file",
    "module",
    "service",
)
_MULTIMODAL_HINTS = (
    "pdf",
    "drawing",
    "diagram",
    "image",
    "screenshot",
    "multimodal",
    "ocr",
    "callout",
)
_SIMULATION_HINTS = (
    "simulate",
    "simulation",
    "solver",
    "parser",
    "cad",
    "cae",
    "doe",
)
_CHEMISTRY_HINTS = (
    "chemistry",
    "chemical",
    "catalyst",
    "reaction",
    "kinetics",
    "stoichiometry",
    "molecule",
    "compound",
)
_MECHANICAL_HINTS = (
    "mechanical",
    "transmission",
    "torque",
    "tolerance",
    "gear",
    "shaft",
    "bearing",
    "actuator",
)
_KNOWLEDGE_REQUIRED_HINTS = (
    "solver",
    "library",
    "runtime",
    "adapter",
    "environment",
    "simulation",
    "optimiz",
    "units",
)
_KNOWLEDGE_STRICT_TASK_CLASSES = {
    "thermochemistry_screening",
    "optimization_uq_backbone",
    "geometry_manufacturing",
    "workflow_coupling",
    "electrics_dynamics_system",
    "structures_pde",
}
_KNOWLEDGE_CACHE: tuple[str, Any] | None = None


@dataclass(frozen=True)
class ModeSignal:
    minimum_mode: str
    confidence: float
    reason: str
    source: str = "inferred"


@dataclass(frozen=True)
class ModeEvaluationContext:
    text: str
    context: dict[str, Any]
    requested_mode: str | None = None
    active_mode: str | None = None
    minimum_mode: str | None = None


class ModeSignalProvider(Protocol):
    def collect(self, evaluation: ModeEvaluationContext) -> list[ModeSignal]:
        ...


def _normalize_mode(mode: Any) -> str | None:
    if mode is None:
        return None
    value = str(mode).strip().lower()
    if value == "engineering":
        value = "strict_engineering"
    if value == "strict":
        value = "strict_engineering"
    if value in _MODE_RANK:
        return value
    return None


def _response_mode_to_engagement_alias(response_mode: str, *, strict: bool = True) -> str:
    if response_mode == "engineering":
        return "strict_engineering" if strict else "engineering_task"
    if response_mode in {"casual_chat", "ideation", "napkin_math"}:
        return response_mode
    return "ideation" if response_mode in {"research", "business", "content", "marketing"} else "casual_chat"


def _mode_max(*modes: str | None) -> str:
    best = "casual_chat"
    for mode in modes:
        normalized = _normalize_mode(mode)
        if normalized and _MODE_RANK[normalized] > _MODE_RANK[best]:
            best = normalized
    return best


def _mode_is_lower(left: str | None, right: str | None) -> bool:
    left_norm = _normalize_mode(left)
    right_norm = _normalize_mode(right)
    if left_norm is None or right_norm is None:
        return False
    return _MODE_RANK[left_norm] < _MODE_RANK[right_norm]


class ExplicitModeSignalProvider:
    def collect(self, evaluation: ModeEvaluationContext) -> list[ModeSignal]:
        requested = _normalize_mode(evaluation.requested_mode)
        if requested is None:
            return []
        return [
            ModeSignal(
                minimum_mode=requested,
                confidence=1.0,
                reason=f"explicit_requested_mode:{requested}",
                source="explicit",
            )
        ]


class SessionModeSignalProvider:
    def collect(self, evaluation: ModeEvaluationContext) -> list[ModeSignal]:
        signals: list[ModeSignal] = []
        active = _normalize_mode(evaluation.active_mode)
        if active is not None:
            signals.append(
                ModeSignal(
                    minimum_mode=active,
                    confidence=0.95,
                    reason=f"active_session_mode_floor:{active}",
                    source="resumed_session",
                )
            )
        minimum = _normalize_mode(evaluation.minimum_mode)
        if minimum is not None:
            signals.append(
                ModeSignal(
                    minimum_mode=minimum,
                    confidence=0.9,
                    reason=f"persisted_minimum_mode:{minimum}",
                    source="resumed_session",
                )
            )
        return signals


class DomainClassifierSignalProvider:
    """
    Evaluates the input text using an external machine learning classifier to assert
    the baseline domain (e.g., chemistry, software engineering).
    
    If the text overwhelmingly registers as chemistry + engineering (e.g., thermal dynamics),
    we immediately elevate the boundary to `strict_engineering` because chemical interactions
    cannot safely be answered casually without rigorous artifact bounding.
    """
    def __init__(self) -> None:
        self.classifier = DomainClassifier()

    def collect(self, evaluation: ModeEvaluationContext) -> list[ModeSignal]:
        scores = self.classifier.classify(evaluation.text, threshold=0.08)
        if not scores:
            return []
        top_domains = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        signals: list[ModeSignal] = []
        chemistry = scores.get("chemistry", 0.0)
        engineering = max(scores.get("mechanical", 0.0), scores.get("materials", 0.0))
        software = scores.get("software_engineering", 0.0)
        if chemistry >= 0.15 and (engineering >= 0.12 or software >= 0.12):
            signals.append(
                ModeSignal(
                    minimum_mode="strict_engineering",
                    confidence=min(1.0, chemistry + max(engineering, software)),
                    reason="hard_rule:chemistry_plus_engineering_domain",
                )
            )
        elif engineering >= 0.18 and software >= 0.14:
            signals.append(
                ModeSignal(
                    minimum_mode="engineering_task",
                    confidence=min(1.0, engineering + software),
                    reason="domain_signal:cross_engineering_software_work",
                )
            )
        elif chemistry >= 0.16 or engineering >= 0.18:
            signals.append(
                ModeSignal(
                    minimum_mode="napkin_math",
                    confidence=max(chemistry, engineering),
                    reason=f"domain_signal:{top_domains[0][0]}",
                )
            )
        return signals


class WorkScopeSignalProvider:
    """
    Analyzes the requested target file scope (e.g., context boundaries inside the IDE)
    to decide the strictness of the required orchestration.
    
    A user casually mentioning "refactor" across 5 sub-systems implicitly requires
    `strict_engineering` to enforce test-gates, whereas modifying a single module might
    only warrant `engineering_task`. If the target involves multimodal extraction
    (like visual diagrams), we lock to strict rules to prevent hallucinated logic.
    """
    def collect(self, evaluation: ModeEvaluationContext) -> list[ModeSignal]:
        ctx = evaluation.context
        lower = evaluation.text.lower()
        signals: list[ModeSignal] = []
        target_paths = ctx.get("target_paths")
        target_count = len(target_paths) if isinstance(target_paths, list) else 0
        expected_file_count = int(ctx.get("expected_file_count", 0) or 0)
        likely_multi_file = bool(ctx.get("likely_multi_file"))
        mentions_repo = any(hint in lower for hint in _CODING_HINTS)
        mentions_quant = any(hint in lower for hint in _QUANTITATIVE_HINTS)
        mentions_multimodal = any(hint in lower for hint in _MULTIMODAL_HINTS)
        mentions_simulation = any(hint in lower for hint in _SIMULATION_HINTS)
        mentions_ideation = any(hint in lower for hint in _IDEATION_HINTS)
        acceptance_hints = (
            "acceptance criteria" in lower
            or "verify" in lower
            or "verification" in lower
            or "tests" in lower
            or "deterministic" in lower
        )
        if mentions_multimodal and (mentions_repo or mentions_simulation):
            signals.append(
                ModeSignal(
                    minimum_mode="strict_engineering",
                    confidence=0.95,
                    reason="hard_rule:multimodal_plus_coding_or_simulation",
                )
            )
        if (
            expected_file_count > 1
            or target_count > 1
            or likely_multi_file
            or "cross-subsystem" in lower
            or "multi-file" in lower
            or "multiple files" in lower
        ) and mentions_repo:
            mode = "strict_engineering" if acceptance_hints or "artifact" in lower else "engineering_task"
            signals.append(
                ModeSignal(
                    minimum_mode=mode,
                    confidence=0.9 if mode == "strict_engineering" else 0.82,
                    reason=(
                        "hard_rule:multifile_mutation_with_governance"
                        if mode == "strict_engineering"
                        else "scope_signal:multifile_repo_work"
                    ),
                )
            )
        elif mentions_repo and acceptance_hints:
            signals.append(
                ModeSignal(
                    minimum_mode="engineering_task",
                    confidence=0.8,
                    reason="hard_rule:bounded_repo_work_with_verification",
                )
            )
        elif mentions_quant and not mentions_repo:
            signals.append(
                ModeSignal(
                    minimum_mode="napkin_math",
                    confidence=0.72,
                    reason="hard_rule:quantitative_reasoning_without_repo_mutation",
                )
            )
        elif mentions_ideation and not mentions_repo:
            signals.append(
                ModeSignal(
                    minimum_mode="ideation",
                    confidence=0.66,
                    reason="hard_rule:open_ended_concept_exploration",
                )
            )
        return signals


class HardRuleSignalProvider:
    def collect(self, evaluation: ModeEvaluationContext) -> list[ModeSignal]:
        lower = evaluation.text.lower()
        signals: list[ModeSignal] = []
        has_ideation = any(hint in lower for hint in _IDEATION_HINTS)
        has_repo_work = any(hint in lower for hint in _CODING_HINTS)
        has_quant = any(hint in lower for hint in _QUANTITATIVE_HINTS)
        has_chemistry = any(hint in lower for hint in _CHEMISTRY_HINTS)
        has_mechanical = any(hint in lower for hint in _MECHANICAL_HINTS)
        if has_chemistry and (has_mechanical or "engineering" in lower):
            signals.append(
                ModeSignal(
                    minimum_mode="strict_engineering",
                    confidence=0.96,
                    reason="hard_rule:chemistry_plus_engineering_keywords",
                )
            )
        if has_ideation and not has_repo_work and not has_quant:
            signals.append(
                ModeSignal(
                    minimum_mode="ideation",
                    confidence=0.78,
                    reason="hard_rule:open_ended_concept_exploration",
                )
            )
            return signals
        if any(hint in lower for hint in _ENGINEERING_HINTS):
            signals.append(
                ModeSignal(
                    minimum_mode="engineering_task",
                    confidence=0.68,
                    reason="heuristic:engineering_keyword_density",
                )
            )
        if "strict engineering" in lower or "artifact-governed" in lower:
            signals.append(
                ModeSignal(
                    minimum_mode="strict_engineering",
                    confidence=0.92,
                    reason="heuristic:explicit_strict_engineering_language",
                )
            )
        if not signals and len(evaluation.text.split()) >= 20:
            signals.append(
                ModeSignal(
                    minimum_mode="ideation",
                    confidence=0.4,
                    reason="heuristic:long_form_nontrivial_request",
                )
            )
        return signals


class KnowledgePoolSignalProvider:
    def collect(self, evaluation: ModeEvaluationContext) -> list[ModeSignal]:
        assessment = _prompt_knowledge_assessment(
            text=evaluation.text,
            context=evaluation.context,
        )
        coverage = assessment.coverage_class
        required = assessment.required_for_mode
        if not required:
            return []
        if assessment.derived_task_class in _KNOWLEDGE_STRICT_TASK_CLASSES:
            return [
                ModeSignal(
                    minimum_mode="strict_engineering",
                    confidence=0.95 if coverage is KnowledgeCoverageClass.STRONG else 0.86,
                    reason=f"knowledge_pool:{coverage.value}:{assessment.derived_task_class}",
                )
            ]
        return [
            ModeSignal(
                minimum_mode="engineering_task",
                confidence=0.88 if coverage is KnowledgeCoverageClass.STRONG else 0.78,
                reason=f"knowledge_pool:{coverage.value}:{assessment.derived_task_class}",
            )
        ]


def _knowledge_pool_root() -> Path:
    """Engineering substrate root; matches :func:`resolve_engineering_knowledge_pool_root`."""
    return cast(Path, resolve_engineering_knowledge_pool_root())


def _knowledge_pool_fingerprint(root: Path) -> str:
    digest = sha256()
    for path in sorted(root.rglob("*.json")):
        stat = path.stat()
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(str(stat.st_mtime_ns).encode("utf-8"))
        digest.update(str(stat.st_size).encode("utf-8"))
    return digest.hexdigest()


def _knowledge_catalog() -> Any:
    global _KNOWLEDGE_CACHE  # noqa: PLW0603 - intentional process-local cache
    root = _knowledge_pool_root()
    fingerprint = _knowledge_pool_fingerprint(root)
    if _KNOWLEDGE_CACHE and _KNOWLEDGE_CACHE[0] == fingerprint:
        return _KNOWLEDGE_CACHE[1]
    catalog = load_knowledge_pool(root=root)
    _KNOWLEDGE_CACHE = (fingerprint, catalog)
    return catalog


def _knowledge_task_class_from_text(
    text: str,
    scores: dict[str, float],
) -> str:
    lower = text.lower()
    if any(hint in lower for hint in _CHEMISTRY_HINTS):
        return "thermochemistry_screening"
    if any(
        hint in lower
        for hint in ("optimization", "optimize", "surrogate", "uncertainty", "uq", "doe")
    ):
        return "optimization_uq_backbone"
    if any(
        hint in lower
        for hint in ("cad", "geometry", "mesh", "manufactur", "gmsh", "cadquery", "occt")
    ):
        return "geometry_manufacturing"
    if any(hint in lower for hint in ("spice", "circuit", "electrical", "signal")):
        return "electrics_dynamics_system"
    if any(hint in lower for hint in ("pde", "finite volume", "diffusion", "field solve")):
        return "structures_pde"
    if any(
        hint in lower
        for hint in ("runtime", "adapter", "workflow", "pipeline", "integration", "orchestrat")
    ):
        return "workflow_coupling"
    return "engineering_minutes_runtime_link"


def _knowledge_languages(text: str, context: dict[str, Any]) -> list[str]:
    lower = text.lower()
    languages: list[str] = []
    explicit = context.get("languages")
    if isinstance(explicit, list):
        languages.extend(str(item).strip().lower() for item in explicit if str(item).strip())
    if "python" in lower:
        languages.append("python")
    if "c++" in lower or "cpp" in lower:
        languages.append("c++")
    if "c#" in lower or "dotnet" in lower or ".net" in lower:
        languages.append("c#")
    if "cli" in lower:
        languages.append("cli")
    if not languages:
        languages.append("python")
    return list(dict.fromkeys(languages))


def _knowledge_requirement_flags(text: str, context: dict[str, Any]) -> dict[str, bool]:
    lower = text.lower()
    has_repo_work = any(hint in lower for hint in _CODING_HINTS)
    has_simulation = any(hint in lower for hint in _SIMULATION_HINTS)
    has_multimodal = any(hint in lower for hint in _MULTIMODAL_HINTS)
    has_runtime = any(hint in lower for hint in _KNOWLEDGE_REQUIRED_HINTS)
    has_quantitative = any(hint in lower for hint in _QUANTITATIVE_HINTS)
    explicit_target_paths = isinstance(context.get("target_paths"), list) and bool(context.get("target_paths"))
    has_units_signal = bool(
        re.search(r"\bunits?\b", lower)
        or re.search(r"\bsi\b", lower)
        or "us customary" in lower
    )
    return {
        "external_solver": has_simulation or "thermo" in lower or "combustion" in lower,
        "runtime_selection": has_runtime or "bootstrap" in lower or "launcher" in lower,
        "multimodal_engineering": has_multimodal and (has_repo_work or has_simulation or "engineering" in lower),
        "tool_backed_codegen": has_repo_work and (
            has_runtime
            or has_simulation
            or "library" in lower
            or "adapter" in lower
            or "environment" in lower
        ),
        "units_heavy": has_units_signal,
        "repo_local_only": has_repo_work and not (has_runtime or has_simulation) and explicit_target_paths,
        "quantitative_reasoning": has_quantitative,
    }


def _knowledge_required_for_mode(
    *,
    text: str,
    context: dict[str, Any],
) -> bool:
    flags = _knowledge_requirement_flags(text, context)
    return any(
        flags[key]
        for key in (
            "external_solver",
            "runtime_selection",
            "multimodal_engineering",
            "tool_backed_codegen",
            "units_heavy",
        )
    )


def _prompt_problem_spec(
    *,
    text: str,
    context: dict[str, Any],
    scores: dict[str, float],
    task_class: str,
    flags: dict[str, bool],
) -> dict[str, Any]:
    domains = [domain for domain, score in scores.items() if score >= 0.1]
    return {
        "request_text": text,
        "task_class": task_class,
        "domains": domains,
        "target_paths": context.get("target_paths") or [],
        "required_capabilities": [name for name, enabled in flags.items() if enabled],
    }


def _prompt_project_constraints(
    *,
    text: str,
    context: dict[str, Any],
    flags: dict[str, bool],
) -> dict[str, Any]:
    return {
        "languages": _knowledge_languages(text, context),
        "integration": "linked runtime" if flags["runtime_selection"] or flags["external_solver"] else "repo-local",
        "verified_runtime": flags["runtime_selection"] or flags["external_solver"],
        "repo_scope": "bounded" if context.get("target_paths") else "unbounded",
    }


def _assessment_artifact_ref(assessment: KnowledgePoolAssessment | dict[str, Any]) -> str:
    identifier = (
        assessment.knowledge_pool_assessment_id
        if isinstance(assessment, KnowledgePoolAssessment)
        else assessment["knowledge_pool_assessment_id"]
    )
    return _artifact_ref("knowledge_pool_assessment", identifier)


def _coverage_for_candidates(
    *,
    required_for_mode: bool,
    flags: dict[str, bool],
    candidate_pack_refs: list[str],
    adapter_refs: list[str],
    environment_refs: list[str],
    runtime_verification_refs: list[str],
) -> tuple[KnowledgeCoverageClass, list[str]]:
    if not required_for_mode:
        return (KnowledgeCoverageClass.NOT_APPLICABLE, [])
    if not candidate_pack_refs:
        return (
            KnowledgeCoverageClass.NONE,
            ["No runtime-linked knowledge packs matched the declared engineering capability needs."],
        )
    checks = {
        "candidate_pack": bool(candidate_pack_refs),
        "preferred_adapter": (not flags["tool_backed_codegen"]) or bool(adapter_refs),
        "preferred_environment": (
            not (flags["runtime_selection"] or flags["external_solver"])
        )
        or bool(environment_refs),
        "runtime_verification": (
            not (flags["runtime_selection"] or flags["external_solver"])
        )
        or bool(runtime_verification_refs),
    }
    if all(checks.values()):
        return (KnowledgeCoverageClass.STRONG, [])
    gaps = [
        f"Missing {name.replace('_', ' ')} coverage from the knowledge pool assessment."
        for name, passed in checks.items()
        if not passed
    ]
    if checks["candidate_pack"] and any(checks.values()):
        return (KnowledgeCoverageClass.PARTIAL, gaps)
    return (KnowledgeCoverageClass.WEAK, gaps)


def _build_knowledge_pool_assessment(
    *,
    derived_task_class: str,
    required_for_mode: bool,
    flags: dict[str, bool],
    problem_spec: dict[str, Any],
    project_constraints: dict[str, Any],
    rule_matches: list[str],
) -> KnowledgePoolAssessment:
    """
    Constructs a deterministic assessment of what knowledge resources (tools, physics engines, solvers)
    are required to safely execute the inferred task class.
    
    Why: Rather than letting an LLM guess what adapter to use to run an OpenFOAM mesh generation or
    a chemistry ODE simulation, this function calls `load_knowledge_pool` and executes a deterministic
    ranking algorithm (`catalog.resolve_stack`). This returns the top 5 physically verified adapters
    and environments that the generated packets MUST use, preventing hallucinations during execution.
    """
    assessment_id = str(
        uuid5(
            NAMESPACE_URL,
            "knowledge-pool-assessment:"
            + json.dumps(
                {
                    "derived_task_class": derived_task_class,
                    "required_for_mode": required_for_mode,
                    "flags": flags,
                    "problem_spec": problem_spec,
                    "project_constraints": project_constraints,
                    "rule_matches": rule_matches,
                },
                sort_keys=True,
            ),
        )
    )
    if not required_for_mode:
        return validate_knowledge_pool_assessment_json(
            {
                "knowledge_pool_assessment_id": assessment_id,
                "schema_version": "1.0.0",
                "derived_task_class": derived_task_class,
                "coverage_class": KnowledgeCoverageClass.NOT_APPLICABLE,
                "required_for_mode": False,
                "candidate_pack_refs": [],
                "preferred_adapter_refs": [],
                "preferred_environment_refs": [],
                "runtime_verification_refs": [],
                "knowledge_gaps": [],
                "rule_matches": list(rule_matches),
                "created_at": _iso_now(),
            }
        )
    try:
        catalog = _knowledge_catalog()
        ranked = catalog.resolve_stack(problem_spec, project_constraints)
    except Exception as exc:
        return validate_knowledge_pool_assessment_json(
            {
                "knowledge_pool_assessment_id": assessment_id,
                "schema_version": "1.0.0",
                "derived_task_class": derived_task_class,
                "coverage_class": KnowledgeCoverageClass.NONE,
                "required_for_mode": True,
                "candidate_pack_refs": [],
                "preferred_adapter_refs": [],
                "preferred_environment_refs": [],
                "runtime_verification_refs": [],
                "knowledge_gaps": [f"Knowledge pool unavailable: {exc}"],
                "rule_matches": [*rule_matches, "knowledge_pool:unavailable"],
                "created_at": _iso_now(),
            }
        )

    candidates = ranked[:5]
    candidate_pack_refs = [candidate.knowledge_pack_ref for candidate in candidates]
    adapter_refs = list(
        dict.fromkeys(
            adapter_ref
            for candidate in candidates
            for adapter_ref in candidate.adapter_refs
        )
    )
    environment_refs = list(
        dict.fromkeys(
            environment_ref
            for candidate in candidates
            for environment_ref in candidate.environment_refs
        )
    )
    runtime_refs = list(
        dict.fromkeys(
            verification_ref
            for candidate in candidates
            for verification_ref in candidate.runtime_verification_refs
        )
    )
    coverage_class, gaps = _coverage_for_candidates(
        required_for_mode=required_for_mode,
        flags=flags,
        candidate_pack_refs=candidate_pack_refs,
        adapter_refs=adapter_refs,
        environment_refs=environment_refs,
        runtime_verification_refs=runtime_refs,
    )
    return validate_knowledge_pool_assessment_json(
        {
            "knowledge_pool_assessment_id": assessment_id,
            "schema_version": "1.0.0",
            "derived_task_class": derived_task_class,
            "coverage_class": coverage_class,
            "required_for_mode": required_for_mode,
            "candidate_pack_refs": candidate_pack_refs,
            "preferred_adapter_refs": adapter_refs[:3],
            "preferred_environment_refs": environment_refs[:3],
            "runtime_verification_refs": runtime_refs[:5],
            "knowledge_gaps": gaps,
            "rule_matches": [
                *rule_matches,
                f"knowledge_pool:coverage:{coverage_class.value}",
            ],
            "created_at": _iso_now(),
        }
    )


def _prompt_knowledge_assessment(
    *,
    text: str,
    context: dict[str, Any],
) -> KnowledgePoolAssessment:
    cached = context.get("__knowledge_pool_assessment")
    if isinstance(cached, dict) and cached.get("knowledge_pool_assessment_id"):
        return validate_knowledge_pool_assessment_json(cached)
    scores = DomainClassifier().classify(text, threshold=0.08)
    flags = _knowledge_requirement_flags(text, context)
    derived_task_class = _knowledge_task_class_from_text(text, scores)
    required_for_mode = _knowledge_required_for_mode(text=text, context=context)
    assessment = _build_knowledge_pool_assessment(
        derived_task_class=derived_task_class,
        required_for_mode=required_for_mode,
        flags=flags,
        problem_spec=_prompt_problem_spec(
            text=text,
            context=context,
            scores=scores,
            task_class=derived_task_class,
            flags=flags,
        ),
        project_constraints=_prompt_project_constraints(
            text=text,
            context=context,
            flags=flags,
        ),
        rule_matches=[
            f"knowledge_pool:task_class:{derived_task_class}",
            *[f"knowledge_pool:domain:{name}" for name, score in scores.items() if score >= 0.1],
        ],
    )
    context["__knowledge_pool_assessment"] = assessment.model_dump(mode="json")
    return assessment


def _problem_brief_response_control(
    problem_brief: ProblemBrief,
    *,
    requested_mode: str | None = None,
) -> dict[str, Any]:
    text = " ".join(
        [
            problem_brief.title,
            problem_brief.summary,
            problem_brief.problem_statement.need,
            " ".join(problem_brief.problem_statement.non_goals),
            " ".join(item.description for item in problem_brief.deliverables),
            " ".join(item.description for item in problem_brief.inputs),
            " ".join(criterion.statement for criterion in problem_brief.success_criteria),
            " ".join(criterion.metric for criterion in problem_brief.success_criteria),
        ]
    ).strip()
    context = {
        "target_paths": list(problem_brief.code_guidance.target_paths)
        if problem_brief.code_guidance is not None
        else [],
    }
    assessment = evaluate_response_control(
        prompt=text,
        context=context,
        requested_mode=requested_mode or "engineering",
    )
    return assessment.model_dump(mode="json")


def _problem_brief_knowledge_assessment(problem_brief: ProblemBrief) -> KnowledgePoolAssessment:
    text = " ".join(
        [
            problem_brief.title,
            problem_brief.summary,
            problem_brief.problem_statement.need,
            " ".join(problem_brief.problem_statement.non_goals),
            " ".join(item.description for item in problem_brief.deliverables),
            " ".join(item.description for item in problem_brief.inputs),
            " ".join(criterion.statement for criterion in problem_brief.success_criteria),
            " ".join(criterion.metric for criterion in problem_brief.success_criteria),
        ]
    ).strip()
    context = {
        "target_paths": list(problem_brief.code_guidance.target_paths)
        if problem_brief.code_guidance is not None
        else [],
        "knowledge_required": True,
    }
    scores = DomainClassifier().classify(text, threshold=0.08)
    flags = _knowledge_requirement_flags(text, context)
    derived_task_class = _knowledge_task_class_from_text(text, scores)
    required_for_mode = (
        _knowledge_required_for_mode(text=text, context=context)
        or any(
            item.kind in {"artifact", "standard", "document", "drawing"}
            for item in problem_brief.inputs
        )
    )
    return _build_knowledge_pool_assessment(
        derived_task_class=derived_task_class,
        required_for_mode=required_for_mode,
        flags=flags,
        problem_spec=_prompt_problem_spec(
            text=text,
            context=context,
            scores=scores,
            task_class=derived_task_class,
            flags=flags,
        ),
        project_constraints={
            "languages": _knowledge_languages(text, context),
            "integration": "linked runtime" if required_for_mode else "repo-local",
            "verified_runtime": required_for_mode,
            "repo_scope": (
                "bounded"
                if problem_brief.code_guidance
                and problem_brief.code_guidance.target_paths
                else "unbounded"
            ),
        },
        rule_matches=[
            f"knowledge_pool:task_class:{derived_task_class}",
            "knowledge_pool:problem_brief_structured_pass",
        ],
    )


def _problem_brief_knowledge_project_constraints(
    problem_brief: ProblemBrief,
    *,
    required_for_mode: bool,
) -> dict[str, Any]:
    text = " ".join(
        [
            problem_brief.title,
            problem_brief.problem_statement.need,
            " ".join(criterion.metric for criterion in problem_brief.success_criteria),
        ]
    )
    context = {
        "target_paths": list(problem_brief.code_guidance.target_paths)
        if problem_brief.code_guidance is not None
        else [],
    }
    return {
        "languages": _knowledge_languages(text, context),
        "integration": "linked runtime" if required_for_mode else "repo-local",
        "verified_runtime": required_for_mode,
        "repo_scope": (
            "bounded"
            if problem_brief.code_guidance and problem_brief.code_guidance.target_paths
            else "unbounded"
        ),
    }


def _knowledge_role_context_payloads(
    *,
    assessment: KnowledgePoolAssessment,
    project_constraints: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if (
        not assessment.required_for_mode
        or assessment.coverage_class not in {KnowledgeCoverageClass.PARTIAL, KnowledgeCoverageClass.STRONG}
        or not assessment.candidate_pack_refs
    ):
        return {}
    catalog = _knowledge_catalog()
    payloads: dict[str, dict[str, Any]] = {}
    for role in ("general", "coder", "reviewer"):
        payload = catalog.compile_role_context(
            role=role,
            candidate_refs=list(assessment.candidate_pack_refs),
            task_class=assessment.derived_task_class,
            project_constraints=project_constraints,
        )
        payloads[role] = payload.model_dump(mode="json")
    return payloads


def _knowledge_gate_record(assessment: KnowledgePoolAssessment) -> RequiredGateRecord:
    return RequiredGateRecord(
        gate_id="knowledge_pool_coverage",
        gate_type="verification",
        status="PENDING",
        rationale="Knowledge-pool coverage is insufficient for governed execution.",
    )


def _knowledge_gap_escalation_packet(
    *,
    problem_brief_ref: str,
    engineering_state_ref: str,
    assessment: KnowledgePoolAssessment,
) -> EscalationPacket:
    supporting_refs = [problem_brief_ref, _assessment_artifact_ref(assessment)]
    if engineering_state_ref:
        supporting_refs.append(engineering_state_ref)
    supporting_refs.extend(assessment.candidate_pack_refs)
    return EscalationPacket(
        escalation_packet_id=uuid4(),
        reason=EscalationReason.COMPLEXITY,
        unresolved_items=list(assessment.knowledge_gaps) or ["knowledge_pool_coverage_insufficient"],
        supporting_artifact_refs=list(dict.fromkeys(supporting_refs)),
        compressed_state_ref=engineering_state_ref or problem_brief_ref,
        requested_by="knowledge_pool_gate",
        created_at=datetime.now(UTC),
    )


def reset_engineering_sessions_for_tests() -> None:
    """Strict-engineering sessions are now durably persisted via DevPlane."""
    global _KNOWLEDGE_CACHE  # noqa: PLW0603 - test reset
    _KNOWLEDGE_CACHE = None
    from response_control_framework.response_control import reset_response_control_catalog_cache_for_tests

    reset_response_control_catalog_cache_for_tests()
    return None


def evaluate_engagement_mode(
    *,
    prompt: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    context: dict[str, Any] | None = None,
    requested_mode: str | None = None,
    active_mode: str | None = None,
    minimum_mode: str | None = None,
) -> dict[str, Any]:
    """Infer the required engagement mode directly from current evidence."""
    ctx = context or {}
    text = (prompt or _latest_user_content(messages)).strip()
    response_control = evaluate_response_control(
        prompt=text,
        messages=messages,
        context=ctx,
        requested_mode=requested_mode,
        active_mode=active_mode,
        minimum_mode=minimum_mode,
    )
    response_control_payload = validate_response_control_assessment_json(
        response_control.model_dump(mode="json")
    ).model_dump(mode="json")
    response_mode = str(response_control.mode_selection.selected_mode.value)
    prompt_assessment = _prompt_knowledge_assessment(text=text, context=ctx)
    requested = _normalize_mode(
        requested_mode
        or ctx.get("engagement_mode")
        or ("strict_engineering" if ctx.get("strict_engineering") is True else None)
    )
    persisted_floor = _normalize_mode(
        active_mode
        or ctx.get("active_engagement_mode")
        or ctx.get("session_engagement_mode")
        or ("strict_engineering" if ctx.get("engineering_session_id") else None)
    )
    persisted_minimum = _normalize_mode(
        minimum_mode or ctx.get("minimum_engagement_mode")
    )
    evaluation = ModeEvaluationContext(
        text=text,
        context=ctx,
        requested_mode=requested,
        active_mode=persisted_floor,
        minimum_mode=persisted_minimum,
    )
    providers: tuple[ModeSignalProvider, ...] = (
        ExplicitModeSignalProvider(),
        SessionModeSignalProvider(),
        DomainClassifierSignalProvider(),
        WorkScopeSignalProvider(),
        HardRuleSignalProvider(),
        KnowledgePoolSignalProvider(),
    )
    signals = [signal for provider in providers for signal in provider.collect(evaluation)]
    inferred_mode = _mode_max(*(signal.minimum_mode for signal in signals))
    minimum_required = _mode_max(inferred_mode, persisted_floor, persisted_minimum)
    downward_request = requested is not None and _mode_is_lower(requested, minimum_required)
    chosen_mode = minimum_required
    source = (
        "resumed_session"
        if _normalize_mode(persisted_floor) == minimum_required
        else "inferred"
    )
    if requested is not None and not downward_request:
        chosen_mode = _mode_max(requested, minimum_required)
        source = "explicit" if chosen_mode == requested else source
    relevant_signals = [
        signal.reason
        for signal in signals
        if _MODE_RANK[_normalize_mode(signal.minimum_mode) or "casual_chat"]
        >= _MODE_RANK[minimum_required]
    ]
    if not relevant_signals:
        relevant_signals = ["default:ordinary_assistance"]
    pending_mode_change: dict[str, Any] | None = None
    if downward_request and requested is not None:
        pending_mode_change = {
            "proposed_mode": requested,
            "reason": (
                f"Current mode floor is {minimum_required}; automatic de-escalation is disabled."
            ),
            "prompt": (
                f"This session is currently governed at '{minimum_required}'. "
                f"If you want to de-escalate to '{requested}', please confirm explicitly."
            ),
        }
        chosen_mode = minimum_required
        source = "resumed_session" if persisted_floor else "inferred"
    confidence = max((signal.confidence for signal in signals), default=0.35)
    response_mode_alias = _response_mode_to_engagement_alias(
        response_mode,
        strict=chosen_mode == "strict_engineering",
    )
    response_mode_reasons = list(
        dict.fromkeys(
            [
                *response_control.mode_selection.reasons,
                *relevant_signals,
            ]
        )
    )
    mode_dissonance = (
        response_control.mode_selection.mode_dissonance.model_dump(mode="json")
        if response_control.mode_selection.mode_dissonance is not None
        else None
    )
    return {
        "response_mode": response_mode,
        "response_mode_source": "explicit"
        if response_control.mode_selection.user_override
        else source,
        "response_mode_confidence": response_control.mode_selection.confidence,
        "response_mode_reasons": response_control.mode_selection.reasons,
        "mode_dissonance": mode_dissonance,
        "response_control_assessment": response_control_payload,
        "response_control_ref": response_control_artifact_ref(response_control),
        **selected_response_control_refs(response_control),
        "assembly_order": list(response_control.assembly_order),
        "engagement_mode": chosen_mode,
        "engagement_mode_source": "explicit"
        if response_control.mode_selection.user_override
        else source,
        "engagement_mode_confidence": round(
            min(max(confidence, response_control.mode_selection.confidence), 1.0),
            3,
        ),
        "engagement_mode_reasons": response_mode_reasons,
        "minimum_engagement_mode": response_mode_alias
        if response_control.mode_selection.user_override
        else minimum_required,
        "pending_mode_change": pending_mode_change,
        "requires_confirmation": pending_mode_change is not None,
        "rule_matches": [signal.reason for signal in signals],
        "knowledge_pool_assessment": prompt_assessment.model_dump(mode="json"),
        "knowledge_pool_assessment_ref": _assessment_artifact_ref(prompt_assessment),
        "knowledge_pool_coverage": prompt_assessment.coverage_class.value,
        "knowledge_candidate_refs": list(prompt_assessment.candidate_pack_refs),
        "knowledge_required": prompt_assessment.required_for_mode,
        "knowledge_gaps": list(prompt_assessment.knowledge_gaps),
        "derived_task_class": prompt_assessment.derived_task_class,
    }


def should_auto_promote_engineering(
    *,
    prompt: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    context: dict[str, Any] | None = None,
    requested_mode: str | None = None,
    active_mode: str | None = None,
    minimum_mode: str | None = None,
) -> dict[str, Any]:
    """Compatibility helper for callers that still expect binary promotion."""
    decision = evaluate_engagement_mode(
        prompt=prompt,
        messages=messages,
        context=context,
        requested_mode=requested_mode,
        active_mode=active_mode,
        minimum_mode=minimum_mode,
    )
    mode = str(decision["engagement_mode"])
    return {
        **decision,
        "promote": mode in _ENGINEERING_MODES,
        "reason": (
            decision["engagement_mode_reasons"][0]
            if decision["engagement_mode_reasons"]
            else "default_chat_path"
        ),
    }


def intake_engineering_request(
    *,
    user_input: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    context: dict[str, Any] | None = None,
    session_id: str | None = None,
    persisted_snapshot: dict[str, Any] | None = None,
    task_packet: dict[str, Any] | None = None,
    task_plan: dict[str, Any] | None = None,
    project_context: dict[str, Any] | None = None,
    engagement_mode: str | None = None,
    engagement_mode_source: str | None = None,
    engagement_mode_confidence: float | None = None,
    engagement_mode_reasons: list[str] | None = None,
    minimum_engagement_mode: str | None = None,
    pending_mode_change: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bridge legacy inputs into governing artifacts and enforce gates."""
    ctx = deepcopy(context or {})
    project_ctx = deepcopy(project_context or {})
    engineering_session_id = session_id or str(uuid4())
    snapshot = deepcopy(persisted_snapshot or {})
    if isinstance(snapshot.get("knowledge_pool_assessment"), dict):
        ctx["__knowledge_pool_assessment"] = snapshot["knowledge_pool_assessment"]
    prompt_text = (user_input or _latest_user_content(messages)).strip()
    prompt_assessment = _prompt_knowledge_assessment(
        text=prompt_text,
        context=ctx,
    )
    response_control = evaluate_response_control(
        prompt=prompt_text,
        context=ctx,
        requested_mode=engagement_mode or snapshot.get("response_mode") or snapshot.get("engagement_mode"),
    )
    response_control_payload = response_control.model_dump(mode="json")
    response_refs = selected_response_control_refs(response_control)
    selected_refs = [
        *list(response_refs["selected_knowledge_pool_refs"]),
        *list(response_refs["selected_module_refs"]),
        *list(response_refs["selected_technique_refs"]),
        *list(response_refs["selected_theory_refs"]),
    ]
    wiki_overlay_context = resolve_wiki_overlay_context(selected_refs)
    wiki_edit_candidates = _collect_wiki_edit_candidates(
        context=ctx,
        project_context=project_ctx,
        task_packet=task_packet,
        task_plan=task_plan,
    )
    wiki_edit_proposals = _create_wiki_edit_proposals(
        candidates=wiki_edit_candidates,
        selected_refs=selected_refs,
        created_by="control_plane.engineering_intake",
    )
    wiki_edit_proposal_refs = [
        _artifact_ref("wiki_edit_proposal", proposal["wiki_edit_proposal_id"])
        for proposal in wiki_edit_proposals
        if proposal.get("wiki_edit_proposal_id")
    ]
    bridged = _draft_problem_brief(
        base=snapshot.get("problem_brief"),
        user_input=user_input,
        messages=messages,
        context=ctx,
        task_packet=task_packet,
        task_plan=task_plan,
        project_context=project_ctx,
    )

    missing_fields = _problem_brief_missing_fields(bridged)
    clarification_questions = _clarification_questions_for_missing(missing_fields)
    result: dict[str, Any] = {
        "ok": True,
        "engineering_session_id": engineering_session_id,
        "engagement_mode": _normalize_mode(engagement_mode)
        or _normalize_mode(snapshot.get("engagement_mode"))
        or "strict_engineering",
        "engagement_mode_source": (
            engagement_mode_source or snapshot.get("engagement_mode_source") or "inferred"
        ),
        "engagement_mode_confidence": (
            engagement_mode_confidence
            if engagement_mode_confidence is not None
            else snapshot.get("engagement_mode_confidence")
        ),
        "engagement_mode_reasons": list(
            engagement_mode_reasons
            or snapshot.get("engagement_mode_reasons")
            or []
        ),
        "minimum_engagement_mode": _normalize_mode(minimum_engagement_mode)
        or _normalize_mode(snapshot.get("minimum_engagement_mode"))
        or _normalize_mode(engagement_mode)
        or "strict_engineering",
        "pending_mode_change": pending_mode_change or snapshot.get("pending_mode_change"),
        "response_mode": response_control.mode_selection.selected_mode.value,
        "response_control_assessment": response_control_payload,
        "response_control_ref": response_control_artifact_ref(response_control),
        "selected_knowledge_pool_refs": list(response_refs["selected_knowledge_pool_refs"]),
        "selected_module_refs": list(response_refs["selected_module_refs"]),
        "selected_technique_refs": list(response_refs["selected_technique_refs"]),
        "selected_theory_refs": list(response_refs["selected_theory_refs"]),
        "assembly_order": list(response_control.assembly_order),
        "knowledge_pool_assessment": prompt_assessment.model_dump(mode="json"),
        "knowledge_pool_assessment_ref": _assessment_artifact_ref(prompt_assessment),
        "knowledge_pool_coverage": prompt_assessment.coverage_class.value,
        "knowledge_candidate_refs": list(prompt_assessment.candidate_pack_refs),
        "knowledge_role_contexts": {},
        "knowledge_role_context_refs": [],
        "knowledge_gaps": list(prompt_assessment.knowledge_gaps),
        "knowledge_required": prompt_assessment.required_for_mode,
        "problem_brief": bridged,
        "problem_brief_ref": _artifact_ref("problem_brief", bridged["problem_brief_id"]),
        "problem_brief_valid": False,
        "missing_fields": missing_fields,
        "clarification_questions": clarification_questions,
        "bridge_used": True,
        "status": "CLARIFICATION_REQUIRED" if missing_fields else "READY",
        "engineering_state": None,
        "engineering_state_ref": None,
        "task_queue": None,
        "task_packets": [],
        "task_packet_refs": [],
        "ready_for_task_decomposition": False,
        "required_gates": [],
        "wiki_overlay_context": wiki_overlay_context,
        "wiki_edit_proposals": wiki_edit_proposals,
        "wiki_edit_proposal_refs": wiki_edit_proposal_refs,
    }

    if missing_fields:
        return result

    pb_model = validate_problem_brief_json(bridged)
    structured_assessment = _problem_brief_knowledge_assessment(pb_model)
    structured_response_control_payload = _problem_brief_response_control(
        pb_model,
        requested_mode=engagement_mode or result.get("response_mode") or "engineering",
    )
    structured_response_control = validate_response_control_assessment_json(
        structured_response_control_payload
    )
    structured_response_refs = selected_response_control_refs(structured_response_control)
    role_context_payloads = _knowledge_role_context_payloads(
        assessment=structured_assessment,
        project_constraints=_problem_brief_knowledge_project_constraints(
            pb_model,
            required_for_mode=structured_assessment.required_for_mode,
        ),
    )
    state_model = derive_engineering_state(
        pb_model,
        knowledge_pool_assessment=structured_assessment,
        response_control_assessment=structured_response_control,
    )
    result.update(
        {
            "problem_brief": pb_model.model_dump(mode="json", exclude_none=True),
            "problem_brief_valid": True,
            "knowledge_pool_assessment": structured_assessment.model_dump(mode="json"),
            "knowledge_pool_assessment_ref": _assessment_artifact_ref(structured_assessment),
            "knowledge_pool_coverage": structured_assessment.coverage_class.value,
            "knowledge_candidate_refs": list(structured_assessment.candidate_pack_refs),
            "knowledge_role_contexts": role_context_payloads,
            "knowledge_role_context_refs": [
                _artifact_ref("role_context_bundle", payload["role_context_bundle_id"])
                for payload in role_context_payloads.values()
            ],
            "knowledge_gaps": list(structured_assessment.knowledge_gaps),
            "knowledge_required": structured_assessment.required_for_mode,
            "response_mode": structured_response_control.mode_selection.selected_mode.value,
            "response_control_assessment": structured_response_control.model_dump(mode="json"),
            "response_control_ref": response_control_artifact_ref(structured_response_control),
            "selected_knowledge_pool_refs": list(
                structured_response_refs["selected_knowledge_pool_refs"]
            ),
            "selected_module_refs": list(structured_response_refs["selected_module_refs"]),
            "selected_technique_refs": list(
                structured_response_refs["selected_technique_refs"]
            ),
            "selected_theory_refs": list(structured_response_refs["selected_theory_refs"]),
            "assembly_order": list(structured_response_control.assembly_order),
            "engineering_state": state_model.model_dump(mode="json", exclude_none=True),
            "engineering_state_ref": _artifact_ref(
                "engineering_state",
                state_model.engineering_state_id,
            ),
            "ready_for_task_decomposition": state_model.ready_for_task_decomposition,
            "required_gates": [gate.model_dump(mode="json") for gate in state_model.required_gates],
            "wiki_overlay_context": resolve_wiki_overlay_context(
                [
                    *list(structured_response_refs["selected_knowledge_pool_refs"]),
                    *list(structured_response_refs["selected_module_refs"]),
                    *list(structured_response_refs["selected_technique_refs"]),
                    *list(structured_response_refs["selected_theory_refs"]),
                ]
            ),
        }
    )

    if state_model.ready_for_task_decomposition:
        low_coverage = (
            structured_assessment.required_for_mode
            and structured_assessment.coverage_class
            in {KnowledgeCoverageClass.NONE, KnowledgeCoverageClass.WEAK}
        )
        if low_coverage:
            knowledge_gate = _knowledge_gate_record(structured_assessment).model_dump(mode="json")
            result["required_gates"] = [*result["required_gates"], knowledge_gate]
            result["ready_for_task_decomposition"] = False
            if result["engagement_mode"] == "engineering_task":
                escalation = _knowledge_gap_escalation_packet(
                    problem_brief_ref=result["problem_brief_ref"],
                    engineering_state_ref=result["engineering_state_ref"],
                    assessment=structured_assessment,
                )
                result.update(
                    {
                        "status": "ESCALATED",
                        "escalation_packet": escalation.model_dump(mode="json"),
                        "escalation_packet_ref": _artifact_ref(
                            "escalation_record",
                            escalation.escalation_packet_id,
                        ),
                    }
                )
                return result
            result["status"] = "BLOCKED"
            return result
        task_queue, task_packets = build_task_queue(
            problem_brief=pb_model,
            engineering_state=state_model,
            knowledge_pool_assessment=structured_assessment,
            knowledge_role_contexts=role_context_payloads,
            response_control_assessment=structured_response_control,
        )
        result.update(
            {
                "task_queue": task_queue.model_dump(mode="json"),
                "task_packets": [
                    packet.model_dump(mode="json", exclude_none=True)
                    for packet in task_packets
                ],
                "task_packet_refs": [
                    _artifact_ref("task_packet", packet.task_packet_id) for packet in task_packets
                ],
            }
        )
    else:
        result["status"] = "BLOCKED"
    return result


def derive_engineering_state(
    problem_brief: ProblemBrief | dict[str, Any],
    *,
    knowledge_pool_assessment: KnowledgePoolAssessment | dict[str, Any] | None = None,
    response_control_assessment: ResponseControlAssessment | dict[str, Any] | None = None,
) -> EngineeringState:
    """Deterministically normalize a valid problem_brief into engineering_state."""
    pb = (
        problem_brief
        if isinstance(problem_brief, ProblemBrief)
        else validate_problem_brief_json(problem_brief)
    )
    assessment = (
        knowledge_pool_assessment
        if isinstance(knowledge_pool_assessment, KnowledgePoolAssessment)
        else validate_knowledge_pool_assessment_json(knowledge_pool_assessment)
        if isinstance(knowledge_pool_assessment, dict)
        else _problem_brief_knowledge_assessment(pb)
    )
    response_control = (
        response_control_assessment
        if isinstance(response_control_assessment, ResponseControlAssessment)
        else validate_response_control_assessment_json(response_control_assessment)
        if isinstance(response_control_assessment, dict)
        else validate_response_control_assessment_json(_problem_brief_response_control(pb))
    )
    response_refs = selected_response_control_refs(response_control)
    problem_brief_ref = _artifact_ref("problem_brief", pb.problem_brief_id)
    evidence_refs = [
        item.ref
        for item in pb.inputs
        if item.ref and item.ref.startswith("artifact://")
    ]
    variables = [
        _to_state_variable(variable, problem_brief_ref)
        for variable in (
            list(pb.design_space.responses)
            + list(pb.design_space.controllable_variables)
            + list(pb.design_space.noise_factors)
            + list(pb.design_space.fixed_parameters)
        )
    ]
    constraints = [
        StateConstraint(
            id=constraint.constraint_id,
            statement=constraint.statement,
            kind=_normalize_state_constraint_kind(constraint.kind),
            source_artifact_ref=problem_brief_ref,
            provenance_source=constraint.provenance.source_type,
            rationale=constraint.provenance.rationale,
        )
        for constraint in pb.constraints
    ]
    boundary_conditions = _derive_boundary_conditions(pb.operational_context)
    assumption_status = [
        AssumptionStatusRecord(
            assumption_id=assumption.assumption_id,
            statement=assumption.statement,
            validation_intent=assumption.validation_intent,
            status=(
                "validated"
                if assumption.status == "validated"
                else "waived"
                if assumption.status == "waived"
                else "pending"
            ),
            blocking=assumption.blocking_if_unvalidated,
            impact_if_false=assumption.impact_if_false,
        )
        for assumption in pb.assumptions
    ]
    unknowns = [
        UnknownItem(
            id=f"unknown_{assumption.assumption_id}",
            description=f"Validate assumption: {assumption.statement}",
            blocking=assumption.blocking_if_unvalidated,
        )
        for assumption in pb.assumptions
        if assumption.status == "assumed"
    ]
    open_issues = [
        OpenIssueRecord(
            issue_id=f"issue_{assumption.assumption_id}",
            description=f"Assumption requires validation: {assumption.statement}",
            category="assumption",
            blocking=assumption.blocking_if_unvalidated,
            source_artifact_refs=[problem_brief_ref],
        )
        for assumption in pb.assumptions
        if assumption.status == "assumed"
    ]
    if assessment.required_for_mode and assessment.knowledge_gaps:
        open_issues.extend(
            OpenIssueRecord(
                issue_id=f"knowledge_gap_{index}",
                description=gap,
                category="other",
                blocking=False,
                source_artifact_refs=[problem_brief_ref],
            )
            for index, gap in enumerate(assessment.knowledge_gaps, start=1)
        )
    required_gates: list[RequiredGateRecord] = []
    if pb.human_approval and pb.human_approval.required_before_execution:
        for gate in pb.human_approval.gates:
            required_gates.append(
                RequiredGateRecord(
                    gate_id=gate.gate_id,
                    gate_type="approval",
                    status="PENDING",
                    rationale=gate.rationale or "Human approval required before execution.",
                )
            )
            open_issues.append(
                OpenIssueRecord(
                    issue_id=f"approval_{gate.gate_id}",
                    description=gate.rationale or "Human approval required before execution.",
                    category="approval",
                    blocking=True,
                    source_artifact_refs=[problem_brief_ref],
                )
            )

    conflicts: list[ConflictRecord] = []
    staleness: list[Any] = []
    blocking_unknowns = [unknown for unknown in unknowns if unknown.blocking]
    ready_for_task_decomposition = not blocking_unknowns and not required_gates
    role_context_payloads = _knowledge_role_context_payloads(
        assessment=assessment,
        project_constraints=_problem_brief_knowledge_project_constraints(
            pb,
            required_for_mode=assessment.required_for_mode,
        ),
    )

    state_payload = {
        "engineering_state_id": str(uuid4()),
        "schema_version": "1.0.0",
        "problem_brief_ref": problem_brief_ref,
        "knowledge_pool_assessment_ref": _assessment_artifact_ref(assessment),
        "knowledge_pool_coverage": assessment.coverage_class.value,
        "knowledge_candidate_refs": list(assessment.candidate_pack_refs),
        "knowledge_role_context_refs": [
            _artifact_ref("role_context_bundle", payload["role_context_bundle_id"])
            for payload in role_context_payloads.values()
        ],
        "knowledge_gaps": list(assessment.knowledge_gaps),
        "knowledge_required": assessment.required_for_mode,
        "response_control_ref": response_control_artifact_ref(response_control),
        "selected_knowledge_pool_refs": list(response_refs["selected_knowledge_pool_refs"]),
        "selected_module_refs": list(response_refs["selected_module_refs"]),
        "selected_technique_refs": list(response_refs["selected_technique_refs"]),
        "selected_theory_refs": list(response_refs["selected_theory_refs"]),
        "evidence_bundle_refs": evidence_refs,
        "normalized_boundary": {
            "system_of_interest": pb.system_boundary.system_of_interest,
            "system_level": pb.system_boundary.system_level,
            "included": list(pb.system_boundary.included),
            "excluded": list(pb.system_boundary.excluded),
            "interfaces": list(pb.system_boundary.interfaces),
        },
        "objectives": [
            ObjectiveRecord(
                objective_id=criterion.criterion_id,
                statement=criterion.statement,
                metric=criterion.metric,
                verification_method=criterion.verification_method,
                priority=criterion.priority,
            ).model_dump(mode="json")
            for criterion in pb.success_criteria
        ],
        "verification_intent": [
            VerificationIntentRow(
                criterion_id=criterion.criterion_id,
                verification_method=criterion.verification_method,
                expected_evidence=criterion.expected_evidence,
                target_summary=_criterion_target_summary(criterion),
                status="planned",
            ).model_dump(mode="json")
            for criterion in pb.success_criteria
        ],
        "variables": [variable.model_dump(mode="json") for variable in variables],
        "constraints": [constraint.model_dump(mode="json") for constraint in constraints],
        "boundary_conditions": boundary_conditions,
        "unknowns": [unknown.model_dump(mode="json") for unknown in unknowns],
        "assumption_status": [
            row.model_dump(mode="json") for row in assumption_status
        ],
        "open_issues": [issue.model_dump(mode="json") for issue in open_issues],
        "mechanism_candidates": [],
        "analysis_pathways": [
            AnalysisPathway(
                id="analysis_primary",
                summary="Deterministic decomposition generated from success criteria and deliverables.",
            ).model_dump(mode="json")
        ],
        "conflicts": [conflict.model_dump(mode="json") for conflict in conflicts],
        "staleness": staleness,
        "required_gates": [gate.model_dump(mode="json") for gate in required_gates],
        "ready_for_task_decomposition": ready_for_task_decomposition,
        "merge_policy_version": "merge-v2-engineering-governed",
        "summary_for_routing": (
            f"{_engineering_summary(pb, blocking_unknowns)} "
            f"Knowledge coverage: {assessment.coverage_class.value}."
        ),
        "updated_at": _iso_now(),
    }
    if pb.trace_id:
        state_payload["trace_id"] = pb.trace_id
    return validate_engineering_state_json(state_payload)


def build_task_queue(
    *,
    problem_brief: ProblemBrief | dict[str, Any],
    engineering_state: EngineeringState | dict[str, Any],
    knowledge_pool_assessment: KnowledgePoolAssessment | dict[str, Any] | None = None,
    knowledge_role_contexts: dict[str, dict[str, Any]] | None = None,
    response_control_assessment: ResponseControlAssessment | dict[str, Any] | None = None,
) -> tuple[TaskQueue, list[TaskPacket]]:
    """Build governed task_queue + task_packets; fail closed if gates remain open."""
    pb = (
        problem_brief
        if isinstance(problem_brief, ProblemBrief)
        else validate_problem_brief_json(problem_brief)
    )
    state = (
        engineering_state
        if isinstance(engineering_state, EngineeringState)
        else validate_engineering_state_json(engineering_state)
    )
    if not state.ready_for_task_decomposition:
        raise ValueError("engineering_state is not ready for task decomposition")
    assessment = (
        knowledge_pool_assessment
        if isinstance(knowledge_pool_assessment, KnowledgePoolAssessment)
        else validate_knowledge_pool_assessment_json(knowledge_pool_assessment)
        if isinstance(knowledge_pool_assessment, dict)
        else _problem_brief_knowledge_assessment(pb)
    )
    if (
        assessment.required_for_mode
        and assessment.coverage_class in {KnowledgeCoverageClass.NONE, KnowledgeCoverageClass.WEAK}
    ):
        raise ValueError("knowledge pool coverage is insufficient for task decomposition")
    role_contexts = knowledge_role_contexts or _knowledge_role_context_payloads(
        assessment=assessment,
        project_constraints=_problem_brief_knowledge_project_constraints(
            pb,
            required_for_mode=assessment.required_for_mode,
        ),
    )
    response_control = (
        response_control_assessment
        if isinstance(response_control_assessment, ResponseControlAssessment)
        else validate_response_control_assessment_json(response_control_assessment)
        if isinstance(response_control_assessment, dict)
        else validate_response_control_assessment_json(_problem_brief_response_control(pb))
    )

    problem_brief_ref = _artifact_ref("problem_brief", pb.problem_brief_id)
    engineering_state_ref = _artifact_ref("engineering_state", state.engineering_state_id)
    input_refs = [problem_brief_ref, engineering_state_ref, *state.evidence_bundle_refs]
    seen_refs: set[str] = set()
    ordered_refs: list[str] = []
    for ref in input_refs:
        if ref and ref not in seen_refs:
            seen_refs.add(ref)
            ordered_refs.append(ref)

    deliverables = list(pb.deliverables)
    if not any(
        deliverable.artifact_type_hint == ArtifactType.VERIFICATION_REPORT
        for deliverable in deliverables
    ):
        deliverables.append(
            DeliverableSpec(
                deliverable_id="verification_report",
                description="Deterministic verification report for the generated execution artifacts.",
                artifact_type_hint=ArtifactType.VERIFICATION_REPORT,
                acceptance_criteria=[
                    "Verification report references the task outputs and unresolved issues."
                ],
            )
        )

    packets: list[TaskPacket] = []
    packet_refs: list[str] = []
    for deliverable in deliverables:
        packet = _task_packet_for_deliverable(
            deliverable=deliverable,
            problem_brief=pb,
            engineering_state=state,
            input_artifact_refs=ordered_refs,
            knowledge_pool_assessment=assessment,
            knowledge_role_contexts=role_contexts,
            response_control_assessment=response_control,
        )
        packets.append(packet)
        packet_refs.append(_artifact_ref("task_packet", packet.task_packet_id))

    items: list[TaskQueueItem] = []
    prerequisite_refs = [
        ref
        for ref, packet in zip(packet_refs, packets, strict=True)
        if packet.task_type is not TaskType.VALIDATION
    ]
    for index, (packet_ref, packet) in enumerate(zip(packet_refs, packets, strict=True), start=1):
        depends_on = prerequisite_refs if packet.task_type is TaskType.VALIDATION else []
        items.append(
            TaskQueueItem(
                order_hint=index,
                task_packet_ref=packet_ref,
                depends_on=depends_on,
                approval=TaskQueueApproval(
                    required=False,
                    status="WAIVED",
                ),
                aggregate_budget=packet.budget_policy,
            )
        )

    queue_payload = {
        "task_queue_id": str(uuid4()),
        "schema_version": "1.0.0",
        "problem_brief_ref": problem_brief_ref,
        "engineering_state_ref": engineering_state_ref,
        "merge_policy_version": state.merge_policy_version,
        "queue_status": QueueStatus.OPEN,
        "items": [item.model_dump(mode="json") for item in items],
        "notes": "Engineering-governed task queue derived deterministically from problem_brief and engineering_state.",
        "created_at": _iso_now(),
        "updated_at": _iso_now(),
    }
    if pb.trace_id:
        queue_payload["trace_id"] = pb.trace_id
    queue = validate_task_queue_json(queue_payload)
    return queue, packets


def build_escalation_packet(
    *,
    engineering_state: EngineeringState | dict[str, Any],
    verification_report: dict[str, Any],
    problem_brief_ref: str,
    verification_report_ref: str | None = None,
) -> EscalationPacket:
    """Create a typed escalation packet from verification/conflict artifacts."""
    state = (
        engineering_state
        if isinstance(engineering_state, EngineeringState)
        else validate_engineering_state_json(engineering_state)
    )
    findings = verification_report.get("blocking_findings", []) or []
    unresolved_items = [
        finding.get("code", "verification_finding")
        for finding in findings
        if isinstance(finding, dict)
    ]
    unresolved_items.extend(
        issue.description for issue in state.open_issues if issue.blocking
    )
    unresolved_items.extend(
        conflict.description
        for conflict in state.conflicts
        if conflict.resolution_status == "open"
    )
    if not unresolved_items:
        unresolved_items = ["typed escalation requested without explicit unresolved items"]

    reason = (
        EscalationReason.CONFLICT
        if any(conflict.resolution_status == "open" for conflict in state.conflicts)
        else EscalationReason.AMBIGUITY
        if any(issue.blocking for issue in state.open_issues)
        else EscalationReason.HIGH_IMPACT_REVIEW
    )
    supporting_refs = [problem_brief_ref, state.problem_brief_ref]
    supporting_refs.extend(state.evidence_bundle_refs)
    supporting_refs.extend(verification_report.get("validated_artifact_refs", []) or [])
    if verification_report_ref:
        supporting_refs.append(verification_report_ref)
    deduped_supporting_refs = list(dict.fromkeys(ref for ref in supporting_refs if ref))
    return EscalationPacket.model_validate(
        {
            "escalation_packet_id": str(uuid4()),
            "schema_version": "1.0.0",
            "reason": reason,
            "unresolved_items": unresolved_items,
            "supporting_artifact_refs": deduped_supporting_refs,
            "compressed_state_ref": _artifact_ref(
                "engineering_state",
                state.engineering_state_id,
            ),
            "requested_by": "engineering_control_plane",
            "parent_verification_report_id": verification_report.get("verification_report_id"),
            "created_at": _iso_now(),
        }
    )


def _draft_problem_brief(
    *,
    base: dict[str, Any] | None,
    user_input: str | None,
    messages: list[dict[str, Any]] | None,
    context: dict[str, Any],
    task_packet: dict[str, Any] | None,
    task_plan: dict[str, Any] | None,
    project_context: dict[str, Any],
) -> dict[str, Any]:
    payload = deepcopy(base or {})
    explicit_pb = context.get("problem_brief")
    if isinstance(explicit_pb, dict):
        payload = _deep_merge(payload, explicit_pb)

    text = (user_input or _latest_user_content(messages)).strip()
    task_packet = task_packet or {}
    task_plan = task_plan or {}
    project_name = str(project_context.get("project_name") or project_context.get("name") or "").strip()
    now = _iso_now()
    payload.setdefault("problem_brief_id", str(uuid4()))
    payload.setdefault("schema_version", "1.0.0")
    trace_id = context.get("trace_id") or payload.get("trace_id")
    if trace_id:
        payload["trace_id"] = trace_id
    else:
        payload.pop("trace_id", None)
    payload.setdefault("title", task_packet.get("title") or _derive_title(text))
    payload.setdefault(
        "summary",
        _truncate(
            task_packet.get("context_summary")
            or task_plan.get("objective")
            or text,
            limit=280,
        ),
    )
    payload.setdefault("created_at", now)
    payload["updated_at"] = now
    payload.setdefault(
        "provenance",
        ProblemBriefProvenance(
            source_stage="intent_capture",
            producer=Producer(
                component="engineering_bridge",
                executor="local_general_model",
            ),
            input_digest_sha256=_digest_for_inputs(text, task_packet, task_plan),
        ).model_dump(mode="json"),
    )
    payload.setdefault("forbidden_actions", list(context.get("forbidden_actions", [])))
    payload.setdefault(
        "human_approval",
        HumanApprovalBlock(
            required_before_execution=bool(context.get("require_human_approval", False)),
            gates=[],
        ).model_dump(mode="json"),
    )

    system_boundary = payload.get("system_boundary") or {}
    if not system_boundary:
        included = _ensure_string_list(

                context.get("included")
                or (task_packet.get("scope") or {}).get("included")
                or []

        )
        excluded = _ensure_string_list(

                context.get("excluded")
                or (task_packet.get("scope") or {}).get("excluded")
                or []

        )
        system_boundary = SystemBoundary(
            system_of_interest=project_name or _derive_system_of_interest(text, task_plan, task_packet),
            system_level="repository" if task_plan or task_packet else None,
            included=included,
            excluded=excluded,
            interfaces=_ensure_string_list(context.get("interfaces", [])),
        ).model_dump(mode="json")
    payload["system_boundary"] = system_boundary

    if "problem_statement" not in payload:
        payload["problem_statement"] = ProblemStatement(
            need=str(task_packet.get("objective") or task_plan.get("objective") or text).strip(),
            why=str(context.get("why") or "").strip() or None,
            non_goals=_ensure_string_list(
                context.get("non_goals")
                or (task_packet.get("scope") or {}).get("excluded")
                or []
            ),
        ).model_dump(mode="json")

    if "operational_context" not in payload:
        scenario = _build_default_scenario(task_packet=task_packet, task_plan=task_plan, text=text)
        if scenario is not None:
            payload["operational_context"] = OperationalContext(
                unit_system=context.get("unit_system"),
                notes=_truncate(str(context.get("operational_notes") or ""), limit=200) or None,
                scenarios=[scenario],
            ).model_dump(mode="json")

    if "success_criteria" not in payload:
        payload["success_criteria"] = _derive_success_criteria(
            context=context,
            task_packet=task_packet,
            task_plan=task_plan,
        )

    if "constraints" not in payload:
        payload["constraints"] = _derive_constraints(
            context=context,
            task_packet=task_packet,
            task_plan=task_plan,
        )

    if "assumptions" not in payload:
        payload["assumptions"] = _derive_assumptions(
            context=context,
            task_packet=task_packet,
        )

    if "design_space" not in payload:
        payload["design_space"] = _derive_design_space(payload.get("success_criteria", []))

    if "deliverables" not in payload:
        payload["deliverables"] = _derive_deliverables(
            context=context,
            task_packet=task_packet,
            task_plan=task_plan,
        )

    if "inputs" not in payload:
        payload["inputs"] = _derive_inputs(
            context=context,
            task_packet=task_packet,
            task_plan=task_plan,
            project_context=project_context,
        )

    if "code_guidance" not in payload:
        code_guidance = _derive_code_guidance(
            context=context,
            task_packet=task_packet,
            task_plan=task_plan,
        )
        if code_guidance is not None:
            payload["code_guidance"] = code_guidance

    return payload


def _problem_brief_missing_fields(payload: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not payload.get("title"):
        missing.append("title")
    if not payload.get("summary"):
        missing.append("summary")
    system_boundary = payload.get("system_boundary") or {}
    if not system_boundary.get("system_of_interest"):
        missing.append("system_boundary.system_of_interest")
    problem_statement = payload.get("problem_statement") or {}
    if not problem_statement.get("need"):
        missing.append("problem_statement.need")
    if "non_goals" not in problem_statement:
        missing.append("problem_statement.non_goals")
    operational_context = payload.get("operational_context") or {}
    if not operational_context.get("scenarios"):
        missing.append("operational_context.scenarios")
    success_criteria = payload.get("success_criteria") or []
    if not success_criteria:
        missing.append("success_criteria")
    constraints = payload.get("constraints") or []
    if not constraints:
        missing.append("constraints")
    design_space = payload.get("design_space") or {}
    if not design_space.get("responses"):
        missing.append("design_space.responses")
    deliverables = payload.get("deliverables") or []
    if not deliverables:
        missing.append("deliverables")
    inputs = payload.get("inputs") or []
    if not inputs:
        missing.append("inputs")
    provenance = payload.get("provenance") or {}
    producer = provenance.get("producer") or {}
    if not provenance.get("source_stage"):
        missing.append("provenance.source_stage")
    if not producer.get("component"):
        missing.append("provenance.producer.component")
    if not producer.get("executor"):
        missing.append("provenance.producer.executor")
    return missing


def _clarification_questions_for_missing(missing_fields: list[str]) -> list[str]:
    prompts: list[str] = []
    if "system_boundary.system_of_interest" in missing_fields:
        prompts.append("What system or subsystem is the work explicitly in scope for?")
    if "problem_statement.need" in missing_fields:
        prompts.append("What concrete engineering need should this workflow solve before any implementation starts?")
    if "operational_context.scenarios" in missing_fields:
        prompts.append("What operating scenario or usage mode should govern the first engineering decomposition?")
    if "success_criteria" in missing_fields:
        prompts.append("What measurable success criteria and verification methods should govern the work?")
    if "constraints" in missing_fields:
        prompts.append("What constraints or boundaries must be treated as governing, including file or subsystem scope if relevant?")
    if "design_space.responses" in missing_fields:
        prompts.append("What response variables or outcomes should the system optimize or verify?")
    if "deliverables" in missing_fields:
        prompts.append("What concrete deliverables should downstream task generation produce?")
    if "inputs" in missing_fields:
        prompts.append("What evidence or input artifacts should the workflow treat as authoritative?")
    return prompts[:3]


def _task_packet_for_deliverable(
    *,
    deliverable: DeliverableSpec,
    problem_brief: ProblemBrief,
    engineering_state: EngineeringState,
    input_artifact_refs: list[str],
    knowledge_pool_assessment: KnowledgePoolAssessment,
    knowledge_role_contexts: dict[str, dict[str, Any]],
    response_control_assessment: ResponseControlAssessment,
) -> TaskPacket:
    task_type, executor = _task_routing_for_deliverable(deliverable)
    _ = (knowledge_pool_assessment, knowledge_role_contexts)
    response_refs = selected_response_control_refs(response_control_assessment)
    budget_policy = BudgetPolicy(
        allow_escalation=task_type in {TaskType.VALIDATION, TaskType.ESCALATION_REVIEW},
    )
    acceptance_criteria = (
        list(deliverable.acceptance_criteria)
        or [criterion.statement for criterion in problem_brief.success_criteria]
    )
    packet_payload = {
        "task_packet_id": str(uuid4()),
        "schema_version": "1.0.0",
        "status": TaskPacketStatus.PENDING,
        "task_type": task_type,
        "title": deliverable.description,
        "objective": deliverable.description,
        "scope": {
            "included": list(problem_brief.system_boundary.included),
            "excluded": list(problem_brief.system_boundary.excluded),
        },
        "input_artifact_refs": input_artifact_refs,
        "context_summary": _task_context_summary(problem_brief, engineering_state, deliverable),
        "constraints": [constraint.statement for constraint in problem_brief.constraints]
        + list(problem_brief.forbidden_actions),
        "assumptions": [
            assumption.statement
            for assumption in problem_brief.assumptions
            if assumption.status == "assumed"
        ],
        "response_control_ref": response_control_artifact_ref(response_control_assessment),
        "selected_knowledge_pool_refs": list(response_refs["selected_knowledge_pool_refs"]),
        "selected_module_refs": list(response_refs["selected_module_refs"]),
        "selected_technique_refs": list(response_refs["selected_technique_refs"]),
        "selected_theory_refs": list(response_refs["selected_theory_refs"]),
        "code_guidance": (
            problem_brief.code_guidance.model_dump(mode="json", exclude_none=True)
            if problem_brief.code_guidance and executor is Executor.CODING_MODEL
            else None
        ),
        "required_outputs": [
            RequiredOutputSpec(
                artifact_type=deliverable.artifact_type_hint or ArtifactType.CODE_PATCH,
                schema_version="1.0.0",
            ).model_dump(mode="json")
        ],
        "acceptance_criteria": acceptance_criteria,
        "validation_requirements": [
            f"{row.criterion_id}:{row.verification_method}:{row.target_summary}"
            for row in engineering_state.verification_intent
        ]
        if task_type is TaskType.VALIDATION
        else [],
        "priority": _highest_priority(problem_brief.success_criteria),
        "budget_policy": budget_policy.model_dump(mode="json"),
        "routing_metadata": RoutingMetadata(
            requested_by="engineering_control_plane",
            selected_executor=executor,
            reason=f"deliverable:{deliverable.deliverable_id}",
            router_policy_version="engineering-governed-v1",
        ).model_dump(mode="json"),
        "provenance": {
            "source_stage": "engineering_decomposition",
            "decision_log_ref": problem_brief.provenance.raw_intent_artifact_ref,
        },
        "created_at": _iso_now(),
        "updated_at": _iso_now(),
    }
    return validate_task_packet_json(packet_payload)


def _derive_success_criteria(
    *,
    context: dict[str, Any],
    task_packet: dict[str, Any],
    task_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    explicit = context.get("success_criteria")
    if isinstance(explicit, list) and explicit:
        return explicit

    acceptance = _ensure_string_list(
        task_packet.get("acceptance_criteria") or task_plan.get("acceptance_criteria") or []
    )
    verification_blocks = task_plan.get("verification_plan") or []
    criteria: list[dict[str, Any]] = []
    for index, criterion in enumerate(acceptance, start=1):
        criteria.append(
            SuccessCriterion(
                criterion_id=f"criterion_{index}",
                statement=criterion,
                metric=f"criterion_{index}_pass",
                target={"value": 1.0, "unit": "pass"},
                verification_method="test" if verification_blocks else "review",
                expected_evidence="codebase",
                priority=Priority.HIGH if index == 1 else Priority.MEDIUM,
            ).model_dump(mode="json")
        )
    return criteria


def _derive_constraints(
    *,
    context: dict[str, Any],
    task_packet: dict[str, Any],
    task_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    explicit = context.get("constraints")
    if isinstance(explicit, list) and explicit and isinstance(explicit[0], dict):
        return explicit

    raw_constraints = _ensure_string_list(task_packet.get("constraints") or task_plan.get("constraints") or [])
    constraints: list[dict[str, Any]] = []
    for index, item in enumerate(raw_constraints, start=1):
        constraints.append(
            ConstraintSpec(
                constraint_id=f"constraint_{index}",
                statement=item,
                kind="workflow",
                provenance=ConstraintProvenance(
                    source_type="task_packet" if task_packet else "task_plan",
                ),
            ).model_dump(mode="json")
        )
    if not constraints and (task_packet or task_plan):
        constraints.append(
            ConstraintSpec(
                constraint_id="constraint_workspace_only",
                statement="Execution must stay inside the isolated workspace and artifact-governed file scope.",
                kind="workflow",
                provenance=ConstraintProvenance(source_type="system_policy"),
            ).model_dump(mode="json")
        )
    return constraints


def _derive_assumptions(
    *,
    context: dict[str, Any],
    task_packet: dict[str, Any],
) -> list[dict[str, Any]]:
    explicit = context.get("assumptions")
    if isinstance(explicit, list) and explicit and isinstance(explicit[0], dict):
        return explicit
    assumptions = _ensure_string_list(task_packet.get("assumptions") or [])
    return [
        AssumptionSpec(
            assumption_id=f"assumption_{index}",
            statement=item,
            validation_intent="Carry the assumption into deterministic verification and confirm it remains valid.",
            impact_if_false="Downstream implementation or verification may be invalid.",
        ).model_dump(mode="json")
        for index, item in enumerate(assumptions, start=1)
    ]


def _derive_design_space(success_criteria: list[dict[str, Any]]) -> dict[str, Any]:
    responses = [
        DesignVariableSpec(
            variable_id=str(criterion.get("metric") or f"response_{index}"),
            description=str(criterion.get("statement") or f"response_{index}"),
            category="response",
            unit=(
                (criterion.get("target") or {}).get("unit")
                or (criterion.get("minimum") or {}).get("unit")
                or (criterion.get("maximum") or {}).get("unit")
            ),
        ).model_dump(mode="json")
        for index, criterion in enumerate(success_criteria, start=1)
    ]
    if not responses:
        return {
            "responses": [],
            "controllable_variables": [],
            "noise_factors": [],
            "fixed_parameters": [],
        }
    return DesignSpace(
        responses=[DesignVariableSpec.model_validate(item) for item in responses]
    ).model_dump(mode="json")


def _derive_deliverables(
    *,
    context: dict[str, Any],
    task_packet: dict[str, Any],
    task_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    explicit = context.get("deliverables")
    if isinstance(explicit, list) and explicit and isinstance(explicit[0], dict):
        return explicit

    deliverables: list[dict[str, Any]] = []
    required_outputs = task_packet.get("required_outputs") or []
    for index, output in enumerate(required_outputs, start=1):
        deliverables.append(
            DeliverableSpec(
                deliverable_id=f"deliverable_{index}",
                description=f"Produce {output.get('artifact_type', 'CODE_PATCH')} for the scoped engineering task.",
                artifact_type_hint=output.get("artifact_type"),
                acceptance_criteria=_ensure_string_list(task_packet.get("acceptance_criteria") or []),
            ).model_dump(mode="json")
        )
    if not deliverables and (task_packet or task_plan):
        deliverables.append(
            DeliverableSpec(
                deliverable_id="code_patch",
                description="Produce the governed implementation change for the scoped repository task.",
                artifact_type_hint=ArtifactType.CODE_PATCH,
                acceptance_criteria=_ensure_string_list(
                    task_packet.get("acceptance_criteria") or task_plan.get("acceptance_criteria") or []
                ),
            ).model_dump(mode="json")
        )
        deliverables.append(
            DeliverableSpec(
                deliverable_id="verification_report",
                description="Produce a deterministic verification report for the governed implementation change.",
                artifact_type_hint=ArtifactType.VERIFICATION_REPORT,
            ).model_dump(mode="json")
        )
    return deliverables


def _derive_inputs(
    *,
    context: dict[str, Any],
    task_packet: dict[str, Any],
    task_plan: dict[str, Any],
    project_context: dict[str, Any],
) -> list[dict[str, Any]]:
    explicit = context.get("inputs")
    if isinstance(explicit, list) and explicit and isinstance(explicit[0], dict):
        return explicit

    refs = _ensure_string_list(task_packet.get("input_artifact_refs") or [])
    inputs = [
        EvidenceInput(
            input_id=f"input_{index}",
            kind="artifact",
            description=f"Upstream artifact input {index}",
            ref=ref,
            required=True,
        ).model_dump(mode="json")
        for index, ref in enumerate(refs, start=1)
    ]
    repo_ref_hint = str(task_plan.get("repo_ref_hint") or "").strip()
    if repo_ref_hint:
        inputs.append(
            EvidenceInput(
                input_id="repo_ref_hint",
                kind="codebase",
                description="Repository ref hint carried forward from the devplane task plan.",
                ref=repo_ref_hint,
                required=True,
            ).model_dump(mode="json")
        )
    elif project_context.get("project_id"):
        inputs.append(
            EvidenceInput(
                input_id="project_codebase",
                kind="artifact",
                description="Project codebase artifact root for the isolated task workspace.",
                ref=f"artifact://codebase/{project_context['project_id']}",
                required=True,
            ).model_dump(mode="json")
        )
    return inputs


def _derive_code_guidance(
    *,
    context: dict[str, Any],
    task_packet: dict[str, Any],
    task_plan: dict[str, Any],
) -> dict[str, Any] | None:
    explicit = context.get("code_guidance")
    if isinstance(explicit, dict):
        return explicit

    target_paths = []
    if isinstance(context.get("target_paths"), list):
        target_paths = _ensure_string_list(context.get("target_paths"))
    hints = _ensure_string_list(task_plan.get("implementation_outline") or [])
    if not target_paths and not hints and not task_packet and not task_plan:
        return None
    return CodeGuidance(
        summary="Supplemental code execution guidance derived from the current engineering context.",
        file_scope=task_packet.get("scope"),
        target_paths=target_paths,
        implementation_hints=hints,
        acceptance_focus=_ensure_string_list(task_plan.get("acceptance_criteria") or []),
        forbidden_actions=_ensure_string_list(context.get("forbidden_actions") or []),
    ).model_dump(mode="json", exclude_none=True)


def _build_default_scenario(
    *,
    task_packet: dict[str, Any],
    task_plan: dict[str, Any],
    text: str,
) -> OperationalScenario | None:
    description = str(task_plan.get("objective") or task_packet.get("objective") or "").strip()
    conditions = _ensure_string_list(task_plan.get("constraints") or task_packet.get("constraints") or [])
    if not description and not conditions and not text:
        return None
    return OperationalScenario(
        scenario_id="primary",
        description=description or _truncate(text, limit=160),
        operating_conditions=conditions,
        environment="isolated_workspace" if task_plan or task_packet else None,
        usage_mode="implementation" if task_plan or task_packet else None,
    )


def _derive_boundary_conditions(operational_context: OperationalContext) -> list[str]:
    rows: list[str] = []
    for scenario in operational_context.scenarios:
        if not scenario.operating_conditions:
            rows.append(f"Scenario {scenario.scenario_id}: {scenario.description}")
            continue
        for condition in scenario.operating_conditions:
            rows.append(f"Scenario {scenario.scenario_id}: {condition}")
    return rows


def _engineering_summary(problem_brief: ProblemBrief, blocking_unknowns: list[UnknownItem]) -> str:
    return (
        f"{problem_brief.title}: {len(problem_brief.success_criteria)} objectives, "
        f"{len(problem_brief.deliverables)} deliverables, "
        f"{len(blocking_unknowns)} blocking unknowns."
    )


def _criterion_target_summary(criterion: SuccessCriterion) -> str:
    parts: list[str] = []
    if criterion.target is not None:
        parts.append(f"target {criterion.target.value} {criterion.target.unit}")
    if criterion.minimum is not None:
        parts.append(f">= {criterion.minimum.value} {criterion.minimum.unit}")
    if criterion.maximum is not None:
        parts.append(f"<= {criterion.maximum.value} {criterion.maximum.unit}")
    return ", ".join(parts)


def _task_context_summary(
    problem_brief: ProblemBrief,
    engineering_state: EngineeringState,
    deliverable: DeliverableSpec,
) -> str:
    return (
        f"Need: {problem_brief.problem_statement.need}\n"
        f"Deliverable: {deliverable.description}\n"
        f"Boundary: {problem_brief.system_boundary.system_of_interest}\n"
        f"Objectives: {', '.join(obj.metric for obj in engineering_state.objectives)}\n"
        f"Governing refs: {problem_brief.problem_brief_id}, {engineering_state.engineering_state_id}"
    )


def _task_routing_for_deliverable(
    deliverable: DeliverableSpec,
) -> tuple[TaskType, Executor]:
    artifact_type = deliverable.artifact_type_hint
    if artifact_type is ArtifactType.VERIFICATION_REPORT:
        return TaskType.VALIDATION, Executor.DETERMINISTIC_VALIDATOR
    if artifact_type is ArtifactType.DOCUMENT_EXTRACT:
        return TaskType.MULTIMODAL_EXTRACTION, Executor.MULTIMODAL_MODEL
    if artifact_type in {
        ArtifactType.RESEARCH_DIGEST,
        ArtifactType.CLAIMS_REGISTRY,
        ArtifactType.DECISION_LOG,
    }:
        return TaskType.RESEARCH_SYNTHESIS, Executor.LOCAL_GENERAL_MODEL
    return TaskType.CODEGEN, Executor.CODING_MODEL


def _highest_priority(criteria: list[SuccessCriterion]) -> Priority | None:
    order = {
        Priority.LOW: 0,
        Priority.MEDIUM: 1,
        Priority.HIGH: 2,
        Priority.CRITICAL: 3,
    }
    best: Priority | None = None
    for criterion in criteria:
        if criterion.priority is None:
            continue
        if best is None or order[criterion.priority] > order[best]:
            best = criterion.priority
    return best


def _to_state_variable(variable: DesignVariableSpec, problem_brief_ref: str) -> StateVariable:
    return StateVariable(
        id=variable.variable_id,
        description=variable.description,
        role=variable.category,
        unit=variable.unit,
        bounds=variable.bounds,
        source_artifact_ref=problem_brief_ref,
    )


def _normalize_state_constraint_kind(kind: str | None) -> str | None:
    if kind in {"physical", "geometric", "regulatory", "economic"}:
        return kind
    if kind is None:
        return None
    return "other"


def _artifact_ref(prefix: str, identifier: Any) -> str:
    return f"artifact://{prefix}/{identifier}"


def _latest_user_content(messages: list[dict[str, Any]] | None) -> str:
    if not messages:
        return ""
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content") or "")
    return str(messages[-1].get("content") or "")


def _collect_wiki_edit_candidates(
    *,
    context: dict[str, Any],
    project_context: dict[str, Any],
    task_packet: dict[str, Any] | None,
    task_plan: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Collect explicit wiki edit candidates passed by clients or upstream automation."""
    candidates: list[dict[str, Any]] = []
    for source in (
        context.get("wiki_edit_candidates"),
        project_context.get("wiki_edit_candidates"),
        (task_packet or {}).get("wiki_edit_candidates"),
        (task_plan or {}).get("wiki_edit_candidates"),
    ):
        if not isinstance(source, list):
            continue
        for item in source:
            if isinstance(item, dict):
                candidates.append(item)
    return candidates


def _create_wiki_edit_proposals(
    *,
    candidates: list[dict[str, Any]],
    selected_refs: list[str],
    created_by: str,
) -> list[dict[str, Any]]:
    """Persist proposal queue entries for explicit edit candidates."""
    proposals: list[dict[str, Any]] = []
    selected = {ref for ref in selected_refs if ref}
    for candidate in candidates:
        target_ref = str(candidate.get("target_ref") or "").strip()
        target_path = str(candidate.get("target_path") or "").strip()
        title = str(candidate.get("title") or "").strip()
        summary = str(candidate.get("summary") or "").strip()
        proposed_content = str(candidate.get("proposed_content") or "").strip()
        rationale = str(candidate.get("rationale") or "").strip()
        provenance_refs = candidate.get("provenance_refs")
        if (
            not target_ref
            or not target_path
            or not title
            or not summary
            or not proposed_content
            or not rationale
            or not isinstance(provenance_refs, list)
            or not provenance_refs
        ):
            continue
        if selected and target_ref not in selected:
            continue
        try:
            edit_kind = WikiEditKind(str(candidate.get("edit_kind") or "update").lower())
        except ValueError:
            edit_kind = WikiEditKind.UPDATE
        proposal = create_proposal(
            target_ref=target_ref,
            target_path=target_path,
            title=title,
            summary=summary,
            proposed_content=proposed_content,
            rationale=rationale,
            provenance_refs=[str(ref) for ref in provenance_refs if str(ref).strip()],
            created_by=created_by,
            edit_kind=edit_kind,
            confidence=float(candidate.get("confidence", 0.5)),
            proposed_patch=(
                str(candidate.get("proposed_patch"))
                if candidate.get("proposed_patch") is not None
                else None
            ),
        )
        proposals.append(proposal.model_dump(mode="json"))
    return proposals


def _derive_title(text: str) -> str:
    if not text:
        return ""
    first_line = text.strip().splitlines()[0]
    return _truncate(first_line, limit=80)


def _derive_system_of_interest(
    text: str,
    task_plan: dict[str, Any],
    task_packet: dict[str, Any],
) -> str:
    if task_plan or task_packet:
        return "governed_repository_change"
    return _truncate(text, limit=60)


def _truncate(value: str, *, limit: int) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _ensure_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest_for_inputs(text: str, task_packet: dict[str, Any], task_plan: dict[str, Any]) -> str | None:
    payload = {
        "text": text,
        "task_packet": task_packet,
        "task_plan": task_plan,
    }
    encoded = repr(payload).encode("utf-8")
    return sha256(encoded).hexdigest() if encoded else None


def _deep_merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(left)
    for key, value in right.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged
