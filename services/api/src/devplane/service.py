"""Service layer for the OpenClaw-first development plane."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from ..control_plane.engineering import intake_engineering_request
from .models import (
    ArtifactRecord,
    ClarificationAnswer,
    ClarificationQuestion,
    CostLedgerEntry,
    EngagementMode,
    EngagementModeSource,
    EngineeringSessionRecord,
    ExecutionMode,
    FileChangeRecord,
    PendingModeChange,
    ProjectCreateRequest,
    ProjectRecord,
    PublishRequest,
    RunCompleteRequest,
    RunEventRequest,
    RunLogEntry,
    RunPhase,
    RunRecord,
    TaskClarification,
    TaskCreateRequest,
    TaskDossier,
    TaskRecord,
    TaskRequestRecord,
    TaskRunLaunchRequest,
    TaskState,
    VerificationResult,
    utc_now,
)
from .planner import TaskPlanner, slugify
from .store import DevPlaneStore
from .workspace import WorkspaceError, WorkspaceManager


class DevPlaneError(RuntimeError):
    """Domain error carrying an HTTP-friendly status code."""

    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


_ENGINEERING_CHAT_PROJECT_ID = "proj_engineering_chat"
_ENGINEERING_CHAT_PROJECT_NAME = "Engineering Chat Sessions"


class DevPlaneService:
    """Coordinate project registry, task lifecycle, and run dossiers."""

    def __init__(
        self,
        *,
        db_path: Path,
        devplane_root: Path,
        control_plane_root: Path,
        default_remote: str,
    ):
        self.store = DevPlaneStore(db_path)
        self.workspace_manager = WorkspaceManager(
            devplane_root=devplane_root,
            control_plane_root=control_plane_root,
        )
        self.planner = TaskPlanner()
        self.devplane_root = devplane_root
        self.default_remote = default_remote
        self.signature = (
            str(db_path.resolve()),
            str(devplane_root.resolve()),
            str(control_plane_root.resolve()),
            default_remote,
        )

    def register_project(self, request: ProjectCreateRequest) -> ProjectRecord:
        """Register an external project checkout."""
        repo_path = Path(request.canonical_repo_path).expanduser().resolve()
        if not repo_path.exists():
            raise DevPlaneError(f"Project path does not exist: {repo_path}", status_code=404)
        try:
            inspection = self.workspace_manager.inspect_project(
                repo_path,
                remote_name=request.remote_name or self.default_remote,
                requested_default_branch=request.default_branch,
            )
        except WorkspaceError as exc:
            raise DevPlaneError(str(exc), status_code=409) from exc

        existing = next(
            (
                project
                for project in self.store.list_projects()
                if Path(project.canonical_repo_path).resolve() == inspection.top_level
            ),
            None,
        )
        project_id = existing.project_id if existing else f"proj_{slugify(request.name)}"
        workspace_root = self.devplane_root / project_id
        github = inspection.github.model_copy(
            update={
                "owner": request.github_owner or inspection.github.owner,
                "repo": request.github_repo or inspection.github.repo,
            }
        )
        project = ProjectRecord(
            project_id=project_id,
            name=request.name,
            canonical_repo_path=str(inspection.top_level),
            default_branch=inspection.default_branch,
            remote_name=inspection.remote_name,
            remote_url=inspection.remote_url,
            workspace_root=str(workspace_root),
            github=github,
            created_at=existing.created_at if existing else utc_now(),
            updated_at=utc_now(),
        )
        self.store.save_project(project)
        return project

    def list_projects(self) -> list[ProjectRecord]:
        return self.store.list_projects()

    def get_project(self, project_id: str) -> ProjectRecord:
        project = self.store.get_project(project_id)
        if project is None:
            raise DevPlaneError(f"Unknown project: {project_id}", status_code=404)
        return project

    def ensure_engineering_chat_session(
        self,
        *,
        user_intent: str,
        context: dict | None = None,
        session_id: str | None = None,
        promotion_reason: str | None = None,
        engagement_mode: str | EngagementMode | None = None,
        engagement_mode_source: str | EngagementModeSource | None = None,
        engagement_mode_confidence: float | None = None,
        engagement_mode_reasons: list[str] | None = None,
        minimum_engagement_mode: str | EngagementMode | None = None,
        pending_mode_change: dict | PendingModeChange | None = None,
    ) -> tuple[TaskRecord, RunRecord]:
        """Create or resume a visible DevPlane-backed strict-engineering session."""
        project = self._ensure_engineering_chat_project()
        normalized_mode = self._normalize_engagement_mode(
            engagement_mode,
            default=EngagementMode.STRICT_ENGINEERING,
        )
        normalized_source = self._normalize_engagement_mode_source(engagement_mode_source)
        normalized_minimum_mode = self._normalize_engagement_mode(
            minimum_engagement_mode,
            default=normalized_mode,
        )
        pending_change = self._normalize_pending_mode_change(pending_mode_change)
        task = self.store.get_task(session_id) if session_id else None
        if task is None:
            task_id = session_id or str(uuid4())
            request_record = TaskRequestRecord(
                task_id=task_id,
                project_id=project.project_id,
                user_intent=user_intent.strip(),
                context=dict(context or {}),
            )
            dossier = TaskDossier(
                task_id=task_id,
                project_id=project.project_id,
                state=TaskState.PLANNING,
                engagement_mode=normalized_mode,
                engagement_mode_source=normalized_source,
                engagement_mode_confidence=engagement_mode_confidence,
                engagement_mode_reasons=list(engagement_mode_reasons or []),
                minimum_engagement_mode=normalized_minimum_mode,
                pending_mode_change=pending_change,
                reasoning_tier="engineering_control_plane",
                request=request_record,
                clarifications=TaskClarification(),
                engineering_session=EngineeringSessionRecord(
                    engineering_session_id=task_id,
                    promotion_reason=promotion_reason,
                    status="pending",
                    engagement_mode=normalized_mode,
                    engagement_mode_source=normalized_source,
                    engagement_mode_confidence=engagement_mode_confidence,
                    engagement_mode_reasons=list(engagement_mode_reasons or []),
                    minimum_engagement_mode=normalized_minimum_mode,
                    pending_mode_change=pending_change,
                ),
            )
            task = TaskRecord(
                task_id=task_id,
                project_id=project.project_id,
                state=TaskState.PLANNING,
                engagement_mode=normalized_mode,
                engagement_mode_source=normalized_source,
                engagement_mode_confidence=engagement_mode_confidence,
                engagement_mode_reasons=list(engagement_mode_reasons or []),
                minimum_engagement_mode=normalized_minimum_mode,
                pending_mode_change=pending_change,
                request=request_record,
                clarifications=TaskClarification(),
                dossier=dossier,
            )
        else:
            task.request.user_intent = user_intent.strip() or task.request.user_intent
            task.request.context = {**task.request.context, **dict(context or {})}
            if task.dossier.engineering_session is None:
                task.dossier.engineering_session = EngineeringSessionRecord(
                    engineering_session_id=task.task_id,
                    promotion_reason=promotion_reason,
                    status="pending",
                    engagement_mode=normalized_mode,
                    engagement_mode_source=normalized_source,
                    engagement_mode_confidence=engagement_mode_confidence,
                    engagement_mode_reasons=list(engagement_mode_reasons or []),
                    minimum_engagement_mode=normalized_minimum_mode,
                    pending_mode_change=pending_change,
                )

        run = self.get_run(task.current_run_id) if task.current_run_id else None
        if run is None:
            run = RunRecord(
                run_id=str(uuid4()),
                task_id=task.task_id,
                project_id=task.project_id,
                phase=RunPhase.PLANNING,
                engagement_mode=normalized_mode,
                engagement_mode_source=normalized_source,
                engagement_mode_confidence=engagement_mode_confidence,
                engagement_mode_reasons=list(engagement_mode_reasons or []),
                minimum_engagement_mode=normalized_minimum_mode,
                pending_mode_change=pending_change,
                execution_mode=ExecutionMode.EXTERNAL,
                logs=[
                    RunLogEntry(
                        phase=RunPhase.PLANNING,
                        message="Strict engineering chat session created.",
                        details={"promotion_reason": promotion_reason},
                    )
                ],
            )
            task.current_run_id = run.run_id
            if run.run_id not in task.dossier.run_ids:
                task.dossier.run_ids.append(run.run_id)

        session = task.dossier.engineering_session or EngineeringSessionRecord(
            engineering_session_id=task.task_id,
            promotion_reason=promotion_reason,
            status="pending",
        )
        session.run_id = run.run_id
        session.promotion_reason = promotion_reason or session.promotion_reason
        session.updated_at = utc_now()
        task.dossier.engineering_session = session
        task.dossier.reasoning_tier = "engineering_control_plane"
        self._apply_mode_metadata(
            task=task,
            dossier=task.dossier,
            run=run,
            session=session,
            engagement_mode=normalized_mode,
            engagement_mode_source=normalized_source,
            engagement_mode_confidence=engagement_mode_confidence,
            engagement_mode_reasons=engagement_mode_reasons or [],
            minimum_engagement_mode=normalized_minimum_mode,
            pending_mode_change=pending_change,
        )
        task.dossier.updated_at = utc_now()
        task.updated_at = task.dossier.updated_at
        self.store.save_run(run)
        self.store.save_task(task)
        return task, run

    def load_engineering_session_snapshot(
        self,
        *,
        session_id: str | None = None,
        task_id: str | None = None,
    ) -> dict[str, object] | None:
        """Return the durable strict-engineering artifact snapshot for a session/task."""
        target = session_id or task_id
        if not target:
            return None
        task = self.store.get_task(target)
        if task is None:
            return None
        session = task.dossier.engineering_session
        latest_problem_brief = self._latest_typed_payload(task.dossier, "PROBLEM_BRIEF")
        latest_knowledge_assessment = self._latest_typed_payload(
            task.dossier,
            "KNOWLEDGE_POOL_ASSESSMENT",
        )
        latest_response_control = self._latest_typed_payload(
            task.dossier,
            "RESPONSE_CONTROL_ASSESSMENT",
        )
        latest_role_contexts = {
            str(payload.get("role")): payload
            for payload in self._typed_payloads(task.dossier, "ROLE_CONTEXT_BUNDLE")
            if isinstance(payload.get("role"), str)
        }
        latest_engineering_state = self._latest_typed_payload(task.dossier, "ENGINEERING_STATE")
        latest_task_queue = self._latest_typed_payload(task.dossier, "TASK_QUEUE")
        latest_task_packets = self._typed_payloads(task.dossier, "TASK_PACKET")
        if session is None and not any(
            [
                latest_problem_brief,
                latest_knowledge_assessment,
                latest_response_control,
                latest_role_contexts,
                latest_engineering_state,
                latest_task_queue,
                latest_task_packets,
            ]
        ):
            return None
        return {
            "problem_brief": (session.problem_brief if session else None) or latest_problem_brief,
            "knowledge_pool_assessment": (
                session.knowledge_pool_assessment if session else None
            )
            or latest_knowledge_assessment,
            "response_control_ref": (
                session.response_control_ref if session else None
            )
            or task.response_control_ref
            or task.dossier.response_control_ref
            or (
                "artifact://response-control-assessment/"
                f"{latest_response_control['response_control_assessment_id']}"
                if latest_response_control
                and latest_response_control.get("response_control_assessment_id")
                else None
            ),
            "response_mode": (
                session.response_mode if session else None
            )
            or task.response_mode
            or task.dossier.response_mode
            or (
                str(
                    (
                        latest_response_control.get("mode_selection", {})
                        if latest_response_control
                        else {}
                    ).get("selected_mode")
                )
                if latest_response_control
                else None
            ),
            "selected_knowledge_pool_refs": (
                list(session.selected_knowledge_pool_refs) if session else []
            )
            or list(task.selected_knowledge_pool_refs)
            or list(task.dossier.selected_knowledge_pool_refs)
            or (
                list(
                    (
                        latest_response_control.get("knowledge_pool_selection", {})
                        if latest_response_control
                        else {}
                    ).get("selected_pool_refs", [])
                )
                if latest_response_control
                else []
            ),
            "selected_module_refs": (
                list(session.selected_module_refs) if session else []
            )
            or list(task.selected_module_refs)
            or list(task.dossier.selected_module_refs)
            or (
                list(
                    (
                        latest_response_control.get("module_selection", {})
                        if latest_response_control
                        else {}
                    ).get("selected_module_refs", [])
                )
                if latest_response_control
                else []
            ),
            "selected_technique_refs": (
                list(session.selected_technique_refs) if session else []
            )
            or list(task.selected_technique_refs)
            or list(task.dossier.selected_technique_refs)
            or (
                list(
                    (
                        latest_response_control.get("technique_selection", {})
                        if latest_response_control
                        else {}
                    ).get("selected_technique_refs", [])
                )
                if latest_response_control
                else []
            ),
            "selected_theory_refs": (
                list(session.selected_theory_refs) if session else []
            )
            or list(task.selected_theory_refs)
            or list(task.dossier.selected_theory_refs)
            or (
                list(
                    (
                        latest_response_control.get("knowledge_pool_selection", {})
                        if latest_response_control
                        else {}
                    ).get("selected_theory_refs", [])
                )
                if latest_response_control
                else []
            ),
            "knowledge_pool_assessment_ref": (
                session.knowledge_pool_assessment_ref if session else None
            )
            or task.knowledge_pool_assessment_ref
            or task.dossier.knowledge_pool_assessment_ref
            or (
                f"artifact://knowledge_pool_assessment/{latest_knowledge_assessment['knowledge_pool_assessment_id']}"
                if latest_knowledge_assessment
                and latest_knowledge_assessment.get("knowledge_pool_assessment_id")
                else None
            ),
            "knowledge_pool_coverage": (
                session.knowledge_pool_coverage if session else None
            )
            or task.knowledge_pool_coverage
            or task.dossier.knowledge_pool_coverage
            or (
                str(latest_knowledge_assessment.get("coverage_class"))
                if latest_knowledge_assessment
                else None
            ),
            "knowledge_candidate_refs": (
                list(session.knowledge_candidate_refs) if session else []
            )
            or list(task.knowledge_candidate_refs)
            or list(task.dossier.knowledge_candidate_refs)
            or (
                list(latest_knowledge_assessment.get("candidate_pack_refs", []))
                if latest_knowledge_assessment
                else []
            ),
            "knowledge_role_contexts": latest_role_contexts,
            "knowledge_role_context_refs": (
                list(session.knowledge_role_context_refs) if session else []
            )
            or list(task.knowledge_role_context_refs)
            or list(task.dossier.knowledge_role_context_refs)
            or [
                f"artifact://role_context_bundle/{payload['role_context_bundle_id']}"
                for payload in latest_role_contexts.values()
                if payload.get("role_context_bundle_id")
            ],
            "knowledge_gaps": (
                list(session.knowledge_gaps) if session else []
            )
            or list(task.knowledge_gaps)
            or list(task.dossier.knowledge_gaps)
            or (
                list(latest_knowledge_assessment.get("knowledge_gaps", []))
                if latest_knowledge_assessment
                else []
            ),
            "knowledge_required": (
                session.knowledge_required if session else False
            )
            or task.knowledge_required
            or task.dossier.knowledge_required
            or bool(
                latest_knowledge_assessment and latest_knowledge_assessment.get("required_for_mode")
            ),
            "engineering_state": (
                session.engineering_state if session else None
            ) or latest_engineering_state,
            "task_queue": (session.task_queue if session else None) or latest_task_queue,
            "task_packets": (session.task_packets if session else []) or latest_task_packets,
            "active_task_packet": session.active_task_packet if session else None,
            "active_task_packet_ref": session.active_task_packet_ref if session else None,
            "active_selected_executor": session.active_selected_executor if session else None,
            "clarification_questions": session.clarification_questions if session else [],
            "required_gates": session.required_gates if session else [],
            "verification_outcome": session.verification_outcome if session else None,
            "verification_report": session.verification_report if session else None,
            "verification_report_ref": session.verification_report_ref if session else None,
            "escalation_packet": session.escalation_packet if session else None,
            "escalation_packet_ref": session.escalation_packet_ref if session else None,
            "status": session.status if session else None,
            "engagement_mode": task.engagement_mode.value,
            "engagement_mode_source": (
                task.engagement_mode_source.value if task.engagement_mode_source else None
            ),
            "engagement_mode_confidence": task.engagement_mode_confidence,
            "engagement_mode_reasons": list(task.engagement_mode_reasons),
            "minimum_engagement_mode": (
                task.minimum_engagement_mode.value if task.minimum_engagement_mode else None
            ),
            "pending_mode_change": (
                task.pending_mode_change.model_dump(mode="json")
                if task.pending_mode_change is not None
                else None
            ),
            "lifecycle_reason": session.lifecycle_reason if session else task.lifecycle_reason,
            "lifecycle_detail": dict(
                session.lifecycle_detail if session else task.lifecycle_detail
            ),
        }

    def sync_engineering_chat_session(
        self,
        *,
        task_id: str,
        run_id: str | None,
        workflow_result: dict[str, object],
    ) -> TaskRecord:
        """Persist strict-engineering workflow refs/state into the visible DevPlane dossier."""
        task = self.get_task(task_id)
        run = self.get_run(run_id) if run_id else None
        referential_state = workflow_result.get("referential_state", {})
        ref_state = referential_state if isinstance(referential_state, dict) else {}
        task_packets = workflow_result.get("task_packets", [])
        packets = task_packets if isinstance(task_packets, list) else []
        active_packet_id = ref_state.get("active_task_packet_id")
        active_packet_ref = ref_state.get("active_task_packet_ref")
        active_packet = next(
            (
                packet
                for packet in packets
                if isinstance(packet, dict) and packet.get("task_packet_id") == active_packet_id
            ),
            None,
        )
        if active_packet is None and packets:
            active_packet = packets[0] if isinstance(packets[0], dict) else None
        active_selected_executor = ref_state.get("selected_executor")
        if not active_selected_executor and isinstance(active_packet, dict):
            routing = active_packet.get("routing_metadata")
            if isinstance(routing, dict):
                selected = routing.get("selected_executor")
                if isinstance(selected, str) and selected.strip():
                    active_selected_executor = selected.strip()

        session = task.dossier.engineering_session or EngineeringSessionRecord(
            engineering_session_id=task.task_id,
            run_id=run.run_id if run else None,
            promotion_reason=None,
        )
        session.engagement_mode = self._normalize_engagement_mode(
            workflow_result.get("engagement_mode"),
            default=session.engagement_mode,
        )
        session.engagement_mode_source = self._normalize_engagement_mode_source(
            workflow_result.get("engagement_mode_source"),
            default=session.engagement_mode_source,
        )
        session.engagement_mode_confidence = self._coalesce_optional_float(
            workflow_result.get("engagement_mode_confidence"),
            session.engagement_mode_confidence,
        )
        session.engagement_mode_reasons = self._coalesce_string_list(
            workflow_result.get("engagement_mode_reasons"),
            session.engagement_mode_reasons,
        )
        session.minimum_engagement_mode = self._normalize_engagement_mode(
            workflow_result.get("minimum_engagement_mode"),
            default=session.minimum_engagement_mode or session.engagement_mode,
        )
        session.pending_mode_change = self._normalize_pending_mode_change(
            workflow_result.get("pending_mode_change"),
            default=session.pending_mode_change,
        )
        session.run_id = run.run_id if run else session.run_id
        if workflow_result.get("problem_brief") is not None:
            session.problem_brief = workflow_result.get("problem_brief")  # type: ignore[assignment]
        if workflow_result.get("knowledge_pool_assessment") is not None:
            session.knowledge_pool_assessment = workflow_result.get(  # type: ignore[assignment]
                "knowledge_pool_assessment"
            )
        if workflow_result.get("engineering_state") is not None:
            session.engineering_state = workflow_result.get("engineering_state")  # type: ignore[assignment]
        if workflow_result.get("task_queue") is not None:
            session.task_queue = workflow_result.get("task_queue")  # type: ignore[assignment]
        session.task_packets = [packet for packet in packets if isinstance(packet, dict)]
        session.problem_brief_ref = ref_state.get("problem_brief_ref") or session.problem_brief_ref
        if workflow_result.get("response_mode") is not None:
            session.response_mode = str(workflow_result.get("response_mode"))
        session.response_control_ref = (
            ref_state.get("response_control_ref")
            or workflow_result.get("response_control_ref")
            or session.response_control_ref
        )
        for field_name in (
            "selected_knowledge_pool_refs",
            "selected_module_refs",
            "selected_technique_refs",
            "selected_theory_refs",
        ):
            refs = workflow_result.get(field_name)
            if isinstance(refs, list):
                setattr(session, field_name, [str(ref) for ref in refs if str(ref).strip()])
        session.knowledge_pool_assessment_ref = (
            ref_state.get("knowledge_pool_assessment_ref")
            or workflow_result.get("knowledge_pool_assessment_ref")
            or session.knowledge_pool_assessment_ref
        )
        if (
            session.knowledge_pool_assessment_ref is None
            and isinstance(session.knowledge_pool_assessment, dict)
            and session.knowledge_pool_assessment.get("knowledge_pool_assessment_id")
        ):
            session.knowledge_pool_assessment_ref = (
                "artifact://knowledge_pool_assessment/"
                f"{session.knowledge_pool_assessment['knowledge_pool_assessment_id']}"
            )
        if workflow_result.get("knowledge_pool_coverage") is not None:
            session.knowledge_pool_coverage = str(workflow_result.get("knowledge_pool_coverage"))
        knowledge_candidate_refs = workflow_result.get("knowledge_candidate_refs")
        if isinstance(knowledge_candidate_refs, list):
            session.knowledge_candidate_refs = [
                str(ref) for ref in knowledge_candidate_refs if str(ref).strip()
            ]
        elif isinstance(session.knowledge_pool_assessment, dict):
            session.knowledge_candidate_refs = [
                str(ref)
                for ref in session.knowledge_pool_assessment.get("candidate_pack_refs", [])
                if str(ref).strip()
            ]
        knowledge_role_context_refs = workflow_result.get("knowledge_role_context_refs")
        if isinstance(knowledge_role_context_refs, list):
            session.knowledge_role_context_refs = [
                str(ref) for ref in knowledge_role_context_refs if str(ref).strip()
            ]
        elif isinstance(workflow_result.get("knowledge_role_contexts"), dict):
            session.knowledge_role_context_refs = [
                f"artifact://role_context_bundle/{payload['role_context_bundle_id']}"
                for payload in workflow_result.get("knowledge_role_contexts", {}).values()
                if isinstance(payload, dict) and payload.get("role_context_bundle_id")
            ]
        knowledge_gaps = workflow_result.get("knowledge_gaps")
        if isinstance(knowledge_gaps, list):
            session.knowledge_gaps = [
                str(gap) for gap in knowledge_gaps if str(gap).strip()
            ]
        elif isinstance(session.knowledge_pool_assessment, dict):
            session.knowledge_gaps = [
                str(gap)
                for gap in session.knowledge_pool_assessment.get("knowledge_gaps", [])
                if str(gap).strip()
            ]
        if workflow_result.get("knowledge_required") is not None:
            session.knowledge_required = bool(workflow_result.get("knowledge_required"))
        elif isinstance(session.knowledge_pool_assessment, dict):
            session.knowledge_required = bool(
                session.knowledge_pool_assessment.get("required_for_mode")
            )
        session.engineering_state_ref = (
            ref_state.get("engineering_state_ref") or session.engineering_state_ref
        )
        session.active_task_packet = active_packet
        session.active_task_packet_ref = active_packet_ref or (
            f"artifact://task_packet/{active_packet_id}" if active_packet_id else None
        )
        session.active_selected_executor = (
            str(active_selected_executor).strip() if active_selected_executor else None
        )
        clarification_questions = workflow_result.get("clarification_questions", [])
        session.clarification_questions = [
            str(question)
            for question in clarification_questions
            if isinstance(question, str) and question.strip()
        ]
        required_gates = workflow_result.get("required_gates", [])
        session.required_gates = [
            gate for gate in required_gates if isinstance(gate, dict)
        ]
        session.verification_outcome = (
            workflow_result.get("verification_outcome")  # type: ignore[assignment]
            if workflow_result.get("verification_outcome") is not None
            else session.verification_outcome
        )
        if workflow_result.get("verification_report") is not None:
            session.verification_report = workflow_result.get("verification_report")  # type: ignore[assignment]
        session.verification_report_ref = ref_state.get("verification_report_ref") or (
            f"artifact://verification_report/{session.verification_report.get('verification_report_id')}"
            if isinstance(session.verification_report, dict)
            and session.verification_report.get("verification_report_id")
            else session.verification_report_ref
        )
        if workflow_result.get("escalation_packet") is not None:
            session.escalation_packet = workflow_result.get("escalation_packet")  # type: ignore[assignment]
        session.escalation_packet_ref = ref_state.get("escalation_packet_ref") or (
            f"artifact://escalation_record/{session.escalation_packet.get('escalation_packet_id')}"
            if isinstance(session.escalation_packet, dict)
            and session.escalation_packet.get("escalation_packet_id")
            else session.escalation_packet_ref
        )
        if workflow_result.get("lifecycle_reason") is not None:
            session.lifecycle_reason = str(workflow_result.get("lifecycle_reason"))
        if isinstance(workflow_result.get("lifecycle_detail"), dict):
            session.lifecycle_detail = dict(workflow_result.get("lifecycle_detail") or {})
        verification_outcome = str(session.verification_outcome or "").upper()
        if session.clarification_questions:
            session.status = "clarification_required"
            session.lifecycle_reason = session.lifecycle_reason or "clarification_required"
        elif session.required_gates and not ref_state.get("ready_for_task_decomposition"):
            session.status = "blocked"
            session.lifecycle_reason = session.lifecycle_reason or "governance_gate"
        elif verification_outcome == "PASS":
            session.status = "ready"
            session.lifecycle_reason = None
            session.lifecycle_detail = {}
        elif verification_outcome == "ESCALATE":
            session.status = "escalated"
            session.lifecycle_reason = session.lifecycle_reason or "awaiting_strategic_review"
        elif verification_outcome == "BLOCKED":
            session.status = "blocked"
            session.lifecycle_reason = session.lifecycle_reason or "governance_gate"
        elif verification_outcome in {"REWORK", "FAILED"}:
            session.status = "blocked"
            session.lifecycle_reason = session.lifecycle_reason or "verification_rework_required"
        elif session.active_task_packet_ref:
            session.status = "executing"
        else:
            session.status = "ready"
        session.updated_at = utc_now()
        task.dossier.engineering_session = session
        task.clarifications.questions = [
            ClarificationQuestion(
                question_id=f"engineering_{index}",
                prompt=question,
                field="engineering_session",
                required=True,
            )
            for index, question in enumerate(session.clarification_questions, start=1)
        ]
        task.clarifications.answers = [
            answer
            for answer in task.clarifications.answers
            if answer.question_id not in {q.question_id for q in task.clarifications.questions}
        ]
        if session.status == "clarification_required":
            task.state = TaskState.PENDING_CLARIFICATION
        elif session.active_task_packet_ref:
            task.state = TaskState.IMPLEMENTING
        elif session.status == "ready":
            task.state = TaskState.READY
        elif session.status == "blocked":
            task.state = TaskState.BLOCKED
        elif session.status == "escalated":
            task.state = TaskState.ESCALATED
        elif session.verification_report is not None:
            task.state = TaskState.VERIFYING
        else:
            task.state = TaskState.PLANNING
        self._apply_mode_metadata(
            task=task,
            dossier=task.dossier,
            run=run,
            session=session,
            engagement_mode=session.engagement_mode,
            engagement_mode_source=session.engagement_mode_source,
            engagement_mode_confidence=session.engagement_mode_confidence,
            engagement_mode_reasons=session.engagement_mode_reasons,
            minimum_engagement_mode=session.minimum_engagement_mode,
            pending_mode_change=session.pending_mode_change,
            lifecycle_reason=session.lifecycle_reason,
            lifecycle_detail=session.lifecycle_detail,
        )
        self._apply_response_control_metadata(
            task=task,
            dossier=task.dossier,
            run=run,
            session=session,
            response_mode=session.response_mode,
            response_control_ref=session.response_control_ref,
            selected_knowledge_pool_refs=session.selected_knowledge_pool_refs,
            selected_module_refs=session.selected_module_refs,
            selected_technique_refs=session.selected_technique_refs,
            selected_theory_refs=session.selected_theory_refs,
        )
        self._apply_knowledge_metadata(
            task=task,
            dossier=task.dossier,
            run=run,
            session=session,
            knowledge_pool_assessment=session.knowledge_pool_assessment,
            knowledge_pool_assessment_ref=session.knowledge_pool_assessment_ref,
            knowledge_pool_coverage=session.knowledge_pool_coverage,
            knowledge_candidate_refs=session.knowledge_candidate_refs,
            knowledge_role_context_refs=session.knowledge_role_context_refs,
            knowledge_gaps=session.knowledge_gaps,
            knowledge_required=session.knowledge_required,
        )
        task.dossier.state = task.state
        now = utc_now()
        task.updated_at = now
        task.dossier.updated_at = now
        if run is not None:
            if task.state == TaskState.PENDING_CLARIFICATION:
                run.phase = RunPhase.PLANNING
            elif task.state == TaskState.VERIFYING:
                run.phase = RunPhase.VERIFYING
            elif task.state == TaskState.IMPLEMENTING:
                run.phase = RunPhase.IMPLEMENTING
            elif task.state == TaskState.BLOCKED:
                run.phase = RunPhase.BLOCKED
            elif task.state == TaskState.ESCALATED:
                run.phase = RunPhase.ESCALATED
            else:
                run.phase = RunPhase.PLANNING
            run.updated_at = now
            self.store.save_run(run)
        self.store.save_task(task)
        return task

    def submit_task(self, request: TaskCreateRequest) -> TaskRecord:
        """Create a task, optionally blocking for clarification."""
        project = self.get_project(request.project_id)
        task_id = str(uuid4())
        request_record = TaskRequestRecord(
            task_id=task_id,
            project_id=project.project_id,
            user_intent=request.user_intent.strip(),
            repo_ref_hint=request.repo_ref_hint,
            context=request.context,
            risk_hints=request.risk_hints,
        )
        verification_plan = self.workspace_manager.inspect_project(
            Path(project.canonical_repo_path),
            remote_name=project.remote_name,
            requested_default_branch=project.default_branch,
        ).verification_commands
        questions = self.planner.build_questions(
            request,
            project=project,
            existing_answers=[],
        )
        clarifications = TaskClarification(questions=questions)
        state = TaskState.PENDING_CLARIFICATION if questions else TaskState.READY
        plan = None
        patch_plan = None
        if not questions:
            plan, patch_plan = self.planner.build_plan(
                request,
                project=project,
                discovered_verification=verification_plan,
                answers=[],
            )
        dossier = TaskDossier(
            task_id=task_id,
            project_id=project.project_id,
            state=state,
            engagement_mode=request.engagement_mode,
            request=request_record,
            clarifications=clarifications,
            plan=plan,
            patch_plan=patch_plan,
        )
        task = TaskRecord(
            task_id=task_id,
            project_id=project.project_id,
            state=state,
            engagement_mode=request.engagement_mode,
            request=request_record,
            clarifications=clarifications,
            plan=plan,
            patch_plan=patch_plan,
            dossier=dossier,
        )
        self.store.save_task(task)
        return task

    def list_tasks(self) -> list[TaskRecord]:
        return self.store.list_tasks()

    def get_task(self, task_id: str) -> TaskRecord:
        task = self.store.get_task(task_id)
        if task is None:
            raise DevPlaneError(f"Unknown task: {task_id}", status_code=404)
        return task

    def answer_clarifications(
        self, task_id: str, answers: list[ClarificationAnswer]
    ) -> TaskRecord:
        """Resolve task clarifications and rebuild the canonical plan."""
        task = self.get_task(task_id)
        if task.state != TaskState.PENDING_CLARIFICATION:
            raise DevPlaneError(
                f"Task {task_id} is not waiting for clarification",
                status_code=409,
            )
        project = self.get_project(task.project_id)
        request = TaskCreateRequest(
            project_id=task.project_id,
            user_intent=task.request.user_intent,
            repo_ref_hint=task.request.repo_ref_hint,
            context=task.request.context,
            risk_hints=task.request.risk_hints,
        )
        verification_plan = self.workspace_manager.inspect_project(
            Path(project.canonical_repo_path),
            remote_name=project.remote_name,
            requested_default_branch=project.default_branch,
        ).verification_commands
        updated_answers = [*task.clarifications.answers, *answers]
        task.plan, task.patch_plan = self.planner.build_plan(
            request,
            project=project,
            discovered_verification=verification_plan,
            answers=updated_answers,
        )
        task.clarifications = TaskClarification(questions=[], answers=updated_answers)
        task.state = TaskState.READY
        task.updated_at = utc_now()
        task.dossier.state = task.state
        task.dossier.clarifications = task.clarifications
        task.dossier.plan = task.plan
        task.dossier.patch_plan = task.patch_plan
        task.dossier.updated_at = task.updated_at
        self.store.save_task(task)
        return task

    def launch_task(self, task_id: str, request: TaskRunLaunchRequest) -> RunRecord:
        """Provision the isolated workspace and create a run record."""
        task = self.get_task(task_id)
        if task.state == TaskState.PENDING_CLARIFICATION:
            raise DevPlaneError(
                "Task must be clarified before execution can start",
                status_code=409,
            )
        if task.current_run_id and not request.force_new_run:
            existing = self.get_run(task.current_run_id)
            if existing.phase not in {RunPhase.FAILED, RunPhase.CANCELLED}:
                return existing

        project = self.get_project(task.project_id)
        if task.plan is None:
            raise DevPlaneError("Task plan is missing", status_code=409)
        try:
            workspace, commands = self.workspace_manager.create_workspace(
                project=project,
                branch_name=task.plan.planned_branch or f"birtha/{task.task_id[:8]}",
                task_id=task.task_id,
            )
        except WorkspaceError as exc:
            raise DevPlaneError(str(exc), status_code=409) from exc

        task.state = TaskState.PLANNING
        task.updated_at = utc_now()
        engineering_bundle = intake_engineering_request(
            user_input=task.request.user_intent,
            context={
                "target_paths": [
                    patch.file_path for patch in (task.patch_plan.patches if task.patch_plan else [])
                ],
            },
            task_plan=task.plan.model_dump(mode="json") if task.plan else None,
            project_context={
                "project_id": project.project_id,
                "project_name": project.name,
            },
            engagement_mode=(
                request.engagement_mode.value
                if request.engagement_mode is not None
                else task.engagement_mode.value
            ),
            engagement_mode_source=(
                task.engagement_mode_source.value if task.engagement_mode_source else None
            ),
            engagement_mode_confidence=task.engagement_mode_confidence,
            engagement_mode_reasons=task.engagement_mode_reasons,
            minimum_engagement_mode=(
                task.minimum_engagement_mode.value if task.minimum_engagement_mode else None
            ),
            pending_mode_change=(
                task.pending_mode_change.model_dump(mode="json")
                if task.pending_mode_change is not None
                else None
            ),
        )
        if not engineering_bundle.get("problem_brief_valid"):
            prompts = engineering_bundle.get("clarification_questions", [])
            detail = "; ".join(prompts) if prompts else "Problem brief is incomplete."
            raise DevPlaneError(
                f"Task cannot launch until strict engineering clarification is complete: {detail}",
                status_code=409,
            )
        if not engineering_bundle.get("ready_for_task_decomposition"):
            raise DevPlaneError(
                "Task cannot launch because engineering_state is not ready for task decomposition",
                status_code=409,
            )
        artifacts = self.workspace_manager.write_task_packet(
            workspace=workspace,
            task=task,
            engineering_bundle=engineering_bundle,
        )
        run_id = str(uuid4())
        run = RunRecord(
            run_id=run_id,
            task_id=task.task_id,
            project_id=task.project_id,
            phase=RunPhase.PLANNING,
            engagement_mode=request.engagement_mode or task.engagement_mode,
            engagement_mode_source=task.engagement_mode_source,
            engagement_mode_confidence=task.engagement_mode_confidence,
            engagement_mode_reasons=list(task.engagement_mode_reasons),
            minimum_engagement_mode=task.minimum_engagement_mode,
            pending_mode_change=task.pending_mode_change,
            lifecycle_reason=task.lifecycle_reason,
            lifecycle_detail=dict(task.lifecycle_detail),
            knowledge_pool_assessment_ref=engineering_bundle.get("knowledge_pool_assessment_ref"),
            knowledge_pool_coverage=engineering_bundle.get("knowledge_pool_coverage"),
            knowledge_candidate_refs=list(engineering_bundle.get("knowledge_candidate_refs") or []),
            knowledge_role_context_refs=list(
                engineering_bundle.get("knowledge_role_context_refs") or []
            ),
            knowledge_gaps=list(engineering_bundle.get("knowledge_gaps") or []),
            knowledge_required=bool(engineering_bundle.get("knowledge_required")),
            response_mode=engineering_bundle.get("response_mode"),
            response_control_ref=engineering_bundle.get("response_control_ref"),
            selected_knowledge_pool_refs=list(
                engineering_bundle.get("selected_knowledge_pool_refs") or []
            ),
            selected_module_refs=list(engineering_bundle.get("selected_module_refs") or []),
            selected_technique_refs=list(
                engineering_bundle.get("selected_technique_refs") or []
            ),
            selected_theory_refs=list(engineering_bundle.get("selected_theory_refs") or []),
            workspace=workspace,
            execution_mode=request.execution_mode,
            agent_session_id=request.agent_session_id,
            artifacts=artifacts,
            commands=commands,
            logs=[
                RunLogEntry(
                    phase=RunPhase.PLANNING,
                    message="Workspace provisioned and engineering-governed task packet written",
                    details={
                        "workspace_path": workspace.worktree_path,
                        "problem_brief_ref": engineering_bundle.get("problem_brief_ref"),
                        "engineering_state_ref": engineering_bundle.get("engineering_state_ref"),
                    },
                )
            ],
        )
        task.current_run_id = run_id
        task.dossier.workspace = workspace
        task.dossier.run_ids.append(run_id)
        task.dossier.artifacts.extend(artifacts)
        for artifact in artifacts:
            if artifact.artifact_id and artifact.artifact_type:
                task.dossier.typed_artifacts.append(artifact.model_dump(mode="json"))
        task.dossier.commands.extend(commands)
        task.dossier.logs.extend(run.logs)
        task.dossier.state = task.state
        task.dossier.updated_at = task.updated_at
        self._apply_mode_metadata(
            task=task,
            dossier=task.dossier,
            run=run,
            engagement_mode=run.engagement_mode,
            engagement_mode_source=run.engagement_mode_source,
            engagement_mode_confidence=run.engagement_mode_confidence,
            engagement_mode_reasons=run.engagement_mode_reasons,
            minimum_engagement_mode=run.minimum_engagement_mode,
            pending_mode_change=run.pending_mode_change,
            lifecycle_reason=run.lifecycle_reason,
            lifecycle_detail=run.lifecycle_detail,
        )
        self._apply_knowledge_metadata(
            task=task,
            dossier=task.dossier,
            run=run,
            session=task.dossier.engineering_session,
            knowledge_pool_assessment=engineering_bundle.get("knowledge_pool_assessment"),
            knowledge_pool_assessment_ref=engineering_bundle.get("knowledge_pool_assessment_ref"),
            knowledge_pool_coverage=engineering_bundle.get("knowledge_pool_coverage"),
            knowledge_candidate_refs=engineering_bundle.get("knowledge_candidate_refs"),
            knowledge_role_context_refs=engineering_bundle.get("knowledge_role_context_refs"),
            knowledge_gaps=engineering_bundle.get("knowledge_gaps"),
            knowledge_required=engineering_bundle.get("knowledge_required"),
        )
        self._apply_response_control_metadata(
            task=task,
            dossier=task.dossier,
            run=run,
            session=task.dossier.engineering_session,
            response_mode=engineering_bundle.get("response_mode"),
            response_control_ref=engineering_bundle.get("response_control_ref"),
            selected_knowledge_pool_refs=engineering_bundle.get("selected_knowledge_pool_refs"),
            selected_module_refs=engineering_bundle.get("selected_module_refs"),
            selected_technique_refs=engineering_bundle.get("selected_technique_refs"),
            selected_theory_refs=engineering_bundle.get("selected_theory_refs"),
        )
        self.store.save_run(run)
        self.store.save_task(task)
        return run

    def attach_backend_run(
        self,
        run_id: str,
        *,
        backend_run_id: str,
        execution_backend: str,
    ) -> RunRecord:
        """Bind an internal execution-backend run id to a control-plane run."""
        run = self.get_run(run_id)
        run.backend_run_id = backend_run_id
        run.execution_backend = execution_backend
        run.updated_at = utc_now()
        if run.execution_mode != ExecutionMode.EXTERNAL:
            run.execution_mode = ExecutionMode.INTERNAL
        self.store.save_run(run)
        return run

    def list_runs(self) -> list[RunRecord]:
        return self.store.list_runs()

    def get_run(self, run_id: str) -> RunRecord:
        run = self.store.get_run(run_id)
        if run is None:
            raise DevPlaneError(f"Unknown run: {run_id}", status_code=404)
        return run

    def sync_backend_run(
        self,
        run_id: str,
        *,
        phase: RunPhase | None = None,
        status: TaskState | None = None,
        summary: str | None = None,
        files_changed: list[FileChangeRecord] | None = None,
        verification_results: list[VerificationResult] | None = None,
        artifacts: list[ArtifactRecord] | None = None,
    ) -> RunRecord:
        """Apply execution-backend status to the persisted control-plane records."""
        if status is not None and status in {
            TaskState.READY_TO_PUBLISH,
            TaskState.FAILED,
            TaskState.CANCELLED,
        }:
            return self.complete_run(
                run_id,
                RunCompleteRequest(
                    status=status,
                    summary=summary,
                    phase=phase,
                    files_changed=files_changed or [],
                    verification_results=verification_results or [],
                    artifacts=artifacts or [],
                ),
            )
        if phase is not None or summary or files_changed or verification_results or artifacts:
            return self.append_run_event(
                run_id,
                RunEventRequest(
                    phase=phase,
                    status=status,
                    message=summary,
                    files_changed=files_changed or [],
                    verification_results=verification_results or [],
                    artifacts=artifacts or [],
                ),
            )
        return self.get_run(run_id)

    def append_run_event(self, run_id: str, request: RunEventRequest) -> RunRecord:
        """Merge an incremental run update into the run and task dossier."""
        run = self.get_run(run_id)
        task = self.get_task(run.task_id)
        if request.status is not None:
            task.state = request.status
        elif request.phase is not None:
            task.state = self._task_state_for_phase(request.phase)
        if request.phase is not None:
            run.phase = request.phase
        elif request.status is not None:
            run.phase = self._phase_for_nonterminal_state(request.status, default=run.phase)
        if request.engagement_mode is not None or request.minimum_engagement_mode is not None:
            self._apply_mode_metadata(
                task=task,
                dossier=task.dossier,
                run=run,
                session=task.dossier.engineering_session,
                engagement_mode=request.engagement_mode or run.engagement_mode,
                engagement_mode_source=request.engagement_mode_source or run.engagement_mode_source,
                engagement_mode_confidence=(
                    request.engagement_mode_confidence
                    if request.engagement_mode_confidence is not None
                    else run.engagement_mode_confidence
                ),
                engagement_mode_reasons=(
                    request.engagement_mode_reasons or run.engagement_mode_reasons
                ),
                minimum_engagement_mode=(
                    request.minimum_engagement_mode or run.minimum_engagement_mode
                ),
                pending_mode_change=(
                    request.pending_mode_change or run.pending_mode_change
                ),
                lifecycle_reason=request.lifecycle_reason,
                lifecycle_detail=request.lifecycle_detail,
            )
        elif request.lifecycle_reason is not None or request.lifecycle_detail:
            self._apply_mode_metadata(
                task=task,
                dossier=task.dossier,
                run=run,
                session=task.dossier.engineering_session,
                engagement_mode=run.engagement_mode,
                engagement_mode_source=run.engagement_mode_source,
                engagement_mode_confidence=run.engagement_mode_confidence,
                engagement_mode_reasons=run.engagement_mode_reasons,
                minimum_engagement_mode=run.minimum_engagement_mode,
                pending_mode_change=run.pending_mode_change,
                lifecycle_reason=request.lifecycle_reason,
                lifecycle_detail=request.lifecycle_detail,
            )
        if request.message:
            log = RunLogEntry(
                phase=request.phase or run.phase,
                level=request.level,
                message=request.message,
                details=request.details,
            )
            run.logs.append(log)
            task.dossier.logs.append(log)
        run.commands.extend(request.commands)
        run.files_changed.extend(request.files_changed)
        run.verification_results.extend(request.verification_results)
        run.artifacts.extend(request.artifacts)
        run.cost_ledger.extend(request.cost_ledger)
        task.dossier.commands.extend(request.commands)
        task.dossier.files_changed = self._merge_file_changes(
            task.dossier.files_changed, request.files_changed
        )
        task.dossier.verification_results.extend(request.verification_results)
        task.dossier.artifacts.extend(request.artifacts)
        task.dossier.cost_ledger.extend(request.cost_ledger)
        # Mirror typed control-plane envelopes into dossier.typed_artifacts for orchestration queries.
        for art in request.artifacts:
            if art.artifact_id and art.artifact_type:
                task.dossier.typed_artifacts.append(art.model_dump(mode="json"))
        run.updated_at = utc_now()
        task.updated_at = run.updated_at
        task.dossier.state = task.state
        task.dossier.updated_at = task.updated_at
        self.store.save_run(run)
        self.store.save_task(task)
        return run

    def complete_run(self, run_id: str, request: RunCompleteRequest) -> RunRecord:
        """Finalize a run and move the task to its next durable state."""
        if request.status not in {
            TaskState.READY_TO_PUBLISH,
            TaskState.FAILED,
            TaskState.CANCELLED,
        }:
            raise DevPlaneError(
                "Run completion status must be ready_to_publish, failed, or cancelled"
            )
        run = self.get_run(run_id)
        task = self.get_task(run.task_id)
        run.phase = request.phase or self._phase_for_state(request.status)
        self._apply_mode_metadata(
            task=task,
            dossier=task.dossier,
            run=run,
            session=task.dossier.engineering_session,
            engagement_mode=run.engagement_mode,
            engagement_mode_source=run.engagement_mode_source,
            engagement_mode_confidence=run.engagement_mode_confidence,
            engagement_mode_reasons=run.engagement_mode_reasons,
            minimum_engagement_mode=run.minimum_engagement_mode,
            pending_mode_change=run.pending_mode_change,
            lifecycle_reason=request.lifecycle_reason,
            lifecycle_detail=request.lifecycle_detail,
        )
        if request.summary:
            log = RunLogEntry(
                phase=run.phase,
                message=request.summary,
                details={"status": request.status},
            )
            run.logs.append(log)
            task.dossier.logs.append(log)
            task.dossier.final_outcome = request.summary
        if run.workspace is not None and not request.files_changed:
            request = request.model_copy(
                update={"files_changed": self.workspace_manager.detect_file_changes(run.workspace)}
            )
        run.files_changed = self._merge_file_changes(run.files_changed, request.files_changed)
        run.verification_results.extend(request.verification_results)
        run.artifacts.extend(request.artifacts)
        run.updated_at = utc_now()
        run.finished_at = run.updated_at
        task.state = request.status
        task.updated_at = run.updated_at
        task.dossier.state = task.state
        task.dossier.files_changed = self._merge_file_changes(
            task.dossier.files_changed, run.files_changed
        )
        task.dossier.verification_results.extend(request.verification_results)
        task.dossier.artifacts.extend(request.artifacts)
        task.dossier.updated_at = task.updated_at
        self.store.save_run(run)
        self.store.save_task(task)
        return run

    def cancel_task(self, task_id: str) -> TaskRecord:
        """Cancel the active task/run without destroying workspace state."""
        task = self.get_task(task_id)
        task.state = TaskState.CANCELLED
        task.updated_at = utc_now()
        task.dossier.state = task.state
        task.dossier.updated_at = task.updated_at
        if task.current_run_id:
            run = self.get_run(task.current_run_id)
            run.phase = RunPhase.CANCELLED
            run.updated_at = task.updated_at
            run.finished_at = run.updated_at
            self.store.save_run(run)
        self.store.save_task(task)
        return task

    def publish_task(self, task_id: str, request: PublishRequest) -> TaskRecord:
        """Commit and deliver the task branch, optionally creating a PR."""
        task = self.get_task(task_id)
        if task.state not in {
            TaskState.READY_TO_PUBLISH,
            TaskState.IMPLEMENTING,
            TaskState.VERIFYING,
        }:
            raise DevPlaneError(
                f"Task {task_id} is not in a publishable state",
                status_code=409,
            )
        if task.dossier.workspace is None:
            raise DevPlaneError("Task has no provisioned workspace", status_code=409)
        project = self.get_project(task.project_id)
        workspace = task.dossier.workspace
        result, commands = self.workspace_manager.publish_workspace(
            project=project,
            workspace=workspace,
            request=request,
        )
        task.state = TaskState.PUBLISHED
        task.updated_at = utc_now()
        task.dossier.state = task.state
        task.dossier.publish_result = result
        task.dossier.commands.extend(commands)
        task.dossier.files_changed = self._merge_file_changes(
            task.dossier.files_changed,
            self.workspace_manager.detect_file_changes(workspace),
        )
        task.dossier.updated_at = task.updated_at
        if task.current_run_id:
            run = self.get_run(task.current_run_id)
            run.phase = RunPhase.PUBLISHED
            run.publish_result = result
            run.commands.extend(commands)
            run.updated_at = task.updated_at
            self.store.save_run(run)
        self.store.save_task(task)
        return task

    def get_dossier(self, task_id: str) -> TaskDossier:
        return self.get_task(task_id).dossier

    def append_cost_ledger(
        self,
        task_id: str,
        *,
        entry: CostLedgerEntry,
        run_id: str | None = None,
    ) -> TaskRecord:
        """Append a cost ledger entry to the task dossier and optional run."""
        task = self.get_task(task_id)
        task.dossier.cost_ledger.append(entry)
        task.updated_at = utc_now()
        task.dossier.updated_at = task.updated_at
        if run_id:
            run = self.get_run(run_id)
            run.cost_ledger.append(entry)
            run.updated_at = task.updated_at
            self.store.save_run(run)
        self.store.save_task(task)
        return task

    def _task_state_for_phase(self, phase: RunPhase) -> TaskState:
        mapping = {
            RunPhase.PLANNING: TaskState.PLANNING,
            RunPhase.IMPLEMENTING: TaskState.IMPLEMENTING,
            RunPhase.VERIFYING: TaskState.VERIFYING,
            RunPhase.BLOCKED: TaskState.BLOCKED,
            RunPhase.ESCALATED: TaskState.ESCALATED,
            RunPhase.READY_TO_PUBLISH: TaskState.READY_TO_PUBLISH,
            RunPhase.PUBLISHED: TaskState.PUBLISHED,
            RunPhase.FAILED: TaskState.FAILED,
            RunPhase.CANCELLED: TaskState.CANCELLED,
        }
        return mapping[phase]

    def _phase_for_state(self, state: TaskState) -> RunPhase:
        mapping = {
            TaskState.READY_TO_PUBLISH: RunPhase.READY_TO_PUBLISH,
            TaskState.FAILED: RunPhase.FAILED,
            TaskState.CANCELLED: RunPhase.CANCELLED,
            TaskState.PUBLISHED: RunPhase.PUBLISHED,
        }
        return mapping[state]

    def _phase_for_nonterminal_state(
        self,
        state: TaskState,
        *,
        default: RunPhase,
    ) -> RunPhase:
        mapping = {
            TaskState.PENDING_CLARIFICATION: RunPhase.PLANNING,
            TaskState.PLANNING: RunPhase.PLANNING,
            TaskState.IMPLEMENTING: RunPhase.IMPLEMENTING,
            TaskState.VERIFYING: RunPhase.VERIFYING,
            TaskState.BLOCKED: RunPhase.BLOCKED,
            TaskState.ESCALATED: RunPhase.ESCALATED,
            TaskState.READY: RunPhase.PLANNING,
        }
        return mapping.get(state, default)

    def _normalize_engagement_mode(
        self,
        mode: str | EngagementMode | None,
        *,
        default: EngagementMode,
    ) -> EngagementMode:
        if isinstance(mode, EngagementMode):
            return mode
        if isinstance(mode, str) and mode.strip():
            try:
                return EngagementMode(mode.strip().lower())
            except ValueError:
                return default
        return default

    def _normalize_engagement_mode_source(
        self,
        source: str | EngagementModeSource | None,
        *,
        default: EngagementModeSource | None = None,
    ) -> EngagementModeSource | None:
        if isinstance(source, EngagementModeSource):
            return source
        if isinstance(source, str) and source.strip():
            try:
                return EngagementModeSource(source.strip().lower())
            except ValueError:
                return default
        return default

    def _normalize_pending_mode_change(
        self,
        value: dict | PendingModeChange | None,
        *,
        default: PendingModeChange | None = None,
    ) -> PendingModeChange | None:
        if isinstance(value, PendingModeChange):
            return value
        if isinstance(value, dict) and value:
            return PendingModeChange.model_validate(value)
        return default

    def _coalesce_optional_float(
        self,
        value: object,
        fallback: float | None,
    ) -> float | None:
        if value is None:
            return fallback
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return fallback
        return max(0.0, min(1.0, numeric))

    def _coalesce_string_list(
        self,
        value: object,
        fallback: list[str],
    ) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return list(fallback)

    def _apply_mode_metadata(
        self,
        *,
        task: TaskRecord,
        dossier: TaskDossier,
        run: RunRecord | None = None,
        session: EngineeringSessionRecord | None = None,
        engagement_mode: str | EngagementMode,
        engagement_mode_source: str | EngagementModeSource | None = None,
        engagement_mode_confidence: float | None = None,
        engagement_mode_reasons: list[str] | None = None,
        minimum_engagement_mode: str | EngagementMode | None = None,
        pending_mode_change: dict | PendingModeChange | None = None,
        lifecycle_reason: str | None = None,
        lifecycle_detail: dict | None = None,
    ) -> None:
        normalized_mode = self._normalize_engagement_mode(
            engagement_mode,
            default=task.engagement_mode,
        )
        normalized_source = self._normalize_engagement_mode_source(
            engagement_mode_source,
            default=task.engagement_mode_source,
        )
        normalized_minimum = self._normalize_engagement_mode(
            minimum_engagement_mode,
            default=normalized_mode,
        )
        normalized_pending = self._normalize_pending_mode_change(
            pending_mode_change,
            default=task.pending_mode_change,
        )
        reasons = self._coalesce_string_list(
            engagement_mode_reasons,
            task.engagement_mode_reasons,
        )
        detail = dict(lifecycle_detail or {})
        targets: list[object] = [task, dossier]
        if run is not None:
            targets.append(run)
        if session is not None:
            targets.append(session)
        for target in targets:
            target.engagement_mode = normalized_mode
            target.engagement_mode_source = normalized_source
            target.engagement_mode_confidence = self._coalesce_optional_float(
                engagement_mode_confidence,
                getattr(target, "engagement_mode_confidence", None),
            )
            target.engagement_mode_reasons = list(reasons)
            target.minimum_engagement_mode = normalized_minimum
            target.pending_mode_change = normalized_pending
            if lifecycle_reason is not None:
                target.lifecycle_reason = lifecycle_reason
            if lifecycle_detail is not None:
                target.lifecycle_detail = dict(detail)

    def _apply_knowledge_metadata(
        self,
        *,
        task: TaskRecord,
        dossier: TaskDossier,
        run: RunRecord | None = None,
        session: EngineeringSessionRecord | None = None,
        knowledge_pool_assessment: dict | None = None,
        knowledge_pool_assessment_ref: str | None = None,
        knowledge_pool_coverage: str | None = None,
        knowledge_candidate_refs: list[str] | None = None,
        knowledge_role_context_refs: list[str] | None = None,
        knowledge_gaps: list[str] | None = None,
        knowledge_required: bool | None = None,
    ) -> None:
        candidate_refs = self._coalesce_string_list(
            knowledge_candidate_refs,
            task.knowledge_candidate_refs,
        )
        role_context_refs = self._coalesce_string_list(
            knowledge_role_context_refs,
            task.knowledge_role_context_refs,
        )
        gaps = self._coalesce_string_list(knowledge_gaps, task.knowledge_gaps)
        required = (
            bool(knowledge_required)
            if knowledge_required is not None
            else (
                session.knowledge_required
                if session is not None
                else task.knowledge_required
            )
        )
        targets: list[object] = [task, dossier]
        if run is not None:
            targets.append(run)
        if session is not None:
            targets.append(session)
        for target in targets:
            if hasattr(target, "knowledge_pool_assessment") and knowledge_pool_assessment is not None:
                target.knowledge_pool_assessment = dict(knowledge_pool_assessment)
            if knowledge_pool_assessment_ref is not None:
                target.knowledge_pool_assessment_ref = str(knowledge_pool_assessment_ref)
            if knowledge_pool_coverage is not None:
                target.knowledge_pool_coverage = str(knowledge_pool_coverage)
            target.knowledge_candidate_refs = list(candidate_refs)
            target.knowledge_role_context_refs = list(role_context_refs)
            target.knowledge_gaps = list(gaps)
            target.knowledge_required = required

    def _apply_response_control_metadata(
        self,
        *,
        task: TaskRecord,
        dossier: TaskDossier,
        run: RunRecord | None = None,
        session: EngineeringSessionRecord | None = None,
        response_mode: str | None = None,
        response_control_ref: str | None = None,
        selected_knowledge_pool_refs: list[str] | None = None,
        selected_module_refs: list[str] | None = None,
        selected_technique_refs: list[str] | None = None,
        selected_theory_refs: list[str] | None = None,
    ) -> None:
        pool_refs = self._coalesce_string_list(
            selected_knowledge_pool_refs,
            task.selected_knowledge_pool_refs,
        )
        module_refs = self._coalesce_string_list(selected_module_refs, task.selected_module_refs)
        technique_refs = self._coalesce_string_list(
            selected_technique_refs,
            task.selected_technique_refs,
        )
        theory_refs = self._coalesce_string_list(selected_theory_refs, task.selected_theory_refs)
        targets: list[object] = [task, dossier]
        if run is not None:
            targets.append(run)
        if session is not None:
            targets.append(session)
        for target in targets:
            if response_mode is not None:
                target.response_mode = str(response_mode)
            if response_control_ref is not None:
                target.response_control_ref = str(response_control_ref)
            target.selected_knowledge_pool_refs = list(pool_refs)
            target.selected_module_refs = list(module_refs)
            target.selected_technique_refs = list(technique_refs)
            target.selected_theory_refs = list(theory_refs)

    def _merge_file_changes(
        self,
        current: list[FileChangeRecord],
        incoming: list[FileChangeRecord],
    ) -> list[FileChangeRecord]:
        merged: dict[str, FileChangeRecord] = {record.path: record for record in current}
        for record in incoming:
            merged[record.path] = record
        return list(merged.values())

    def _ensure_engineering_chat_project(self) -> ProjectRecord:
        existing = self.store.get_project(_ENGINEERING_CHAT_PROJECT_ID)
        project_root = (self.devplane_root / _ENGINEERING_CHAT_PROJECT_ID).resolve()
        project_root.mkdir(parents=True, exist_ok=True)
        if existing is not None:
            if Path(existing.canonical_repo_path) != project_root:
                existing.canonical_repo_path = str(project_root)
                existing.workspace_root = str(project_root)
                existing.updated_at = utc_now()
                self.store.save_project(existing)
            return existing
        project = ProjectRecord(
            project_id=_ENGINEERING_CHAT_PROJECT_ID,
            name=_ENGINEERING_CHAT_PROJECT_NAME,
            canonical_repo_path=str(project_root),
            default_branch="main",
            remote_name="origin",
            remote_url=None,
            workspace_root=str(project_root),
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.store.save_project(project)
        return project

    def _typed_payloads(self, dossier: TaskDossier, artifact_type: str) -> list[dict[str, object]]:
        payloads: list[dict[str, object]] = []
        for artifact in dossier.typed_artifacts:
            if not isinstance(artifact, dict):
                continue
            if artifact.get("artifact_type") != artifact_type:
                continue
            payload = artifact.get("payload")
            if isinstance(payload, dict):
                payloads.append(payload)
        return payloads

    def _latest_typed_payload(
        self,
        dossier: TaskDossier,
        artifact_type: str,
    ) -> dict[str, object] | None:
        payloads = self._typed_payloads(dossier, artifact_type)
        return payloads[-1] if payloads else None
