"""Service layer for the OpenClaw-first development plane."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from .models import (
    ArtifactRecord,
    ClarificationAnswer,
    ExecutionMode,
    FileChangeRecord,
    ProjectCreateRequest,
    ProjectRecord,
    PublishRequest,
    RunCompleteRequest,
    RunEventRequest,
    CostLedgerEntry,
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
            request=request_record,
            clarifications=clarifications,
            plan=plan,
            patch_plan=patch_plan,
        )
        task = TaskRecord(
            task_id=task_id,
            project_id=project.project_id,
            state=state,
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
        artifact = self.workspace_manager.write_task_packet(workspace=workspace, task=task)
        run_id = str(uuid4())
        run = RunRecord(
            run_id=run_id,
            task_id=task.task_id,
            project_id=task.project_id,
            phase=RunPhase.PLANNING,
            workspace=workspace,
            execution_mode=request.execution_mode,
            agent_session_id=request.agent_session_id,
            artifacts=[artifact],
            commands=commands,
            logs=[
                RunLogEntry(
                    phase=RunPhase.PLANNING,
                    message="Workspace provisioned and task packet written",
                    details={"workspace_path": workspace.worktree_path},
                )
            ],
        )
        task.current_run_id = run_id
        task.dossier.workspace = workspace
        task.dossier.run_ids.append(run_id)
        task.dossier.artifacts.append(artifact)
        task.dossier.commands.extend(commands)
        task.dossier.logs.extend(run.logs)
        task.dossier.state = task.state
        task.dossier.updated_at = task.updated_at
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
        if request.phase is not None:
            run.phase = request.phase
            task.state = self._task_state_for_phase(request.phase)
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

    def _merge_file_changes(
        self,
        current: list[FileChangeRecord],
        incoming: list[FileChangeRecord],
    ) -> list[FileChangeRecord]:
        merged: dict[str, FileChangeRecord] = {record.path: record for record in current}
        for record in incoming:
            merged[record.path] = record
        return list(merged.values())
