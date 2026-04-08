"""Engineering-governed control-plane helpers.

This module turns existing control-plane contracts into executable policy:
legacy chat/task-plan/task-packet inputs are bridged into a structured
``problem_brief``; a deterministic derivation creates ``engineering_state``;
and decomposition into ``task_queue`` / ``task_packet`` is blocked until the
governing artifacts are valid and ready.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import uuid4

from .contracts import (
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
    EngineeringState,
    EvidenceInput,
    Executor,
    NormalizedBoundary,
    ObjectiveRecord,
    OpenIssueRecord,
    Priority,
    ProblemBrief,
    ProblemBriefProvenance,
    ProblemStatement,
    Producer,
    QueueStatus,
    RequiredDeliverable,
    RequiredGateRecord,
    RequiredOutputSpec,
    RoutingMetadata,
    Scope,
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
    EscalationPacket,
    EscalationReason,
    DesignSpace,
    DesignVariableSpec,
    OperationalContext,
    OperationalScenario,
    HumanApprovalBlock,
)
from .validation import (
    validate_engineering_state_json,
    validate_problem_brief_json,
    validate_task_packet_json,
    validate_task_queue_json,
)

_ENGINEERING_SESSIONS: dict[str, dict[str, Any]] = {}

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


def reset_engineering_sessions_for_tests() -> None:
    """Clear in-memory strict-engineering session state (test helper)."""
    _ENGINEERING_SESSIONS.clear()


def should_auto_promote_engineering(
    *,
    prompt: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return strict-mode routing decision for a chat request."""
    ctx = context or {}
    if ctx.get("strict_engineering") is True or ctx.get("engineering_mode") is True:
        return {"promote": True, "reason": "explicit_context_flag"}
    if ctx.get("expected_file_count", 0) and int(ctx["expected_file_count"]) > 1:
        return {"promote": True, "reason": "expected_multi_file_impact"}

    text = (prompt or _latest_user_content(messages)).strip()
    lower = text.lower()
    keyword_hits = [hint for hint in _ENGINEERING_HINTS if hint in lower]
    word_count = len(text.split())
    promote = bool(keyword_hits) and (
        word_count >= 16
        or "multi-file" in lower
        or "multiple files" in lower
        or ctx.get("likely_multi_file") is True
    )
    return {
        "promote": promote,
        "reason": "heuristic_engineering_prompt" if promote else "default_chat_path",
        "matched_hints": keyword_hits,
        "word_count": word_count,
    }


def intake_engineering_request(
    *,
    user_input: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    context: dict[str, Any] | None = None,
    session_id: str | None = None,
    task_packet: dict[str, Any] | None = None,
    task_plan: dict[str, Any] | None = None,
    project_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bridge legacy inputs into governing artifacts and enforce gates."""
    ctx = deepcopy(context or {})
    project_ctx = deepcopy(project_context or {})
    engineering_session_id = session_id or str(uuid4())
    snapshot = deepcopy(_ENGINEERING_SESSIONS.get(engineering_session_id, {}))
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
    }

    if missing_fields:
        _ENGINEERING_SESSIONS[engineering_session_id] = result
        return result

    pb_model = validate_problem_brief_json(bridged)
    state_model = derive_engineering_state(pb_model)
    result.update(
        {
            "problem_brief": pb_model.model_dump(mode="json", exclude_none=True),
            "problem_brief_valid": True,
            "engineering_state": state_model.model_dump(mode="json", exclude_none=True),
            "engineering_state_ref": _artifact_ref(
                "engineering_state",
                state_model.engineering_state_id,
            ),
            "ready_for_task_decomposition": state_model.ready_for_task_decomposition,
            "required_gates": [gate.model_dump(mode="json") for gate in state_model.required_gates],
        }
    )

    if state_model.ready_for_task_decomposition:
        task_queue, task_packets = build_task_queue(
            problem_brief=pb_model,
            engineering_state=state_model,
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

    _ENGINEERING_SESSIONS[engineering_session_id] = result
    return result


def derive_engineering_state(problem_brief: ProblemBrief | dict[str, Any]) -> EngineeringState:
    """Deterministically normalize a valid problem_brief into engineering_state."""
    pb = (
        problem_brief
        if isinstance(problem_brief, ProblemBrief)
        else validate_problem_brief_json(problem_brief)
    )
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

    state_payload = {
        "engineering_state_id": str(uuid4()),
        "schema_version": "1.0.0",
        "problem_brief_ref": problem_brief_ref,
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
        "summary_for_routing": _engineering_summary(pb, blocking_unknowns),
        "updated_at": _iso_now(),
    }
    if pb.trace_id:
        state_payload["trace_id"] = pb.trace_id
    return validate_engineering_state_json(state_payload)


def build_task_queue(
    *,
    problem_brief: ProblemBrief | dict[str, Any],
    engineering_state: EngineeringState | dict[str, Any],
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
            (
                context.get("included")
                or (task_packet.get("scope") or {}).get("included")
                or []
            )
        )
        excluded = _ensure_string_list(
            (
                context.get("excluded")
                or (task_packet.get("scope") or {}).get("excluded")
                or []
            )
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
) -> TaskPacket:
    task_type, executor = _task_routing_for_deliverable(deliverable)
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
