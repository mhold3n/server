"""Development plane control API for projects, tasks, and runs."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..config import settings
from ..devplane import (
    ClarificationAnswer,
    DevPlaneError,
    DevPlaneService,
    ExecutionMode,
    ProjectCreateRequest,
    ProjectRecord,
    PublishRequest,
    RunCompleteRequest,
    RunEventRequest,
    RunPhase,
    RunRecord,
    TaskCreateRequest,
    TaskDossier,
    TaskRecord,
    TaskRunLaunchRequest,
    TaskState,
)
from ..devplane.executor_client import (
    BackendRunSnapshot,
    DevPlaneExecutionClient,
    ExecutionBackendError,
)

router = APIRouter(prefix="/api/dev", tags=["DevPlane"])

_service: DevPlaneService | None = None
_execution_client: DevPlaneExecutionClient | None = None
_TERMINAL_PHASES = {
    "ready_to_publish",
    "published",
    "failed",
    "cancelled",
}


def reset_devplane_service_for_tests() -> None:
    """Reset the lazily created dev-plane service (test helper)."""
    global _execution_client, _service
    _service = None
    _execution_client = None


def get_service() -> DevPlaneService:
    """Return the lazily initialized dev-plane service singleton."""
    global _service
    # When running in-container, this file resolves to /app/src/routes/devplane.py,
    # so parents only goes up to /app (parents[2]). Older code assumed a deeper
    # monorepo path and crashed with IndexError, yielding 500s on /api/ai/query.
    resolved = Path(__file__).resolve()
    control_plane_root = (
        resolved.parents[4] if len(resolved.parents) > 4 else resolved.parents[2]
    )
    desired = (
        str(Path(settings.devplane_db_path).expanduser().resolve()),
        str(Path(settings.devplane_root).expanduser().resolve()),
        str(control_plane_root.resolve()),
        settings.devplane_default_remote,
    )
    if _service is None or _service.signature != desired:
        _service = DevPlaneService(
            db_path=Path(settings.devplane_db_path).expanduser(),
            devplane_root=Path(settings.devplane_root).expanduser(),
            control_plane_root=control_plane_root,
            default_remote=settings.devplane_default_remote,
        )
    return _service


def get_execution_client() -> DevPlaneExecutionClient:
    """Return the lazily initialized execution backend client."""
    global _execution_client
    if _execution_client is None:
        _execution_client = DevPlaneExecutionClient(
            base_url=settings.agent_platform_url,
        )
    return _execution_client


def _raise_http(exc: DevPlaneError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _task_packet_path(run: RunRecord) -> str | None:
    """Return the task-packet artifact path when present."""
    for artifact in run.artifacts:
        if artifact.kind == "task_packet":
            return artifact.path
    return None


def _sync_run_snapshot(
    service: DevPlaneService,
    run: RunRecord,
    snapshot: BackendRunSnapshot,
) -> RunRecord:
    """Apply an execution-backend snapshot to the local control-plane run."""
    phase = snapshot.phase
    status = snapshot.task_state()
    if (
        phase is None
        and status is None
        and not snapshot.summary
        and not snapshot.files_changed
        and not snapshot.verification_results
        and not snapshot.artifacts
    ):
        return run

    return service.sync_backend_run(
        run.run_id,
        phase=phase,
        status=status,
        summary=snapshot.summary,
        files_changed=snapshot.files_changed,
        verification_results=snapshot.verification_results,
        artifacts=snapshot.artifacts,
    )


@router.get("/projects", response_model=list[ProjectRecord])
async def list_projects() -> list[ProjectRecord]:
    return get_service().list_projects()


@router.post("/projects", response_model=ProjectRecord)
async def register_project(request: ProjectCreateRequest) -> ProjectRecord:
    try:
        return get_service().register_project(request)
    except DevPlaneError as exc:
        _raise_http(exc)


@router.get("/projects/{project_id}", response_model=ProjectRecord)
async def get_project(project_id: str) -> ProjectRecord:
    try:
        return get_service().get_project(project_id)
    except DevPlaneError as exc:
        _raise_http(exc)


@router.get("/tasks", response_model=list[TaskRecord])
async def list_tasks() -> list[TaskRecord]:
    return get_service().list_tasks()


@router.post("/tasks", response_model=TaskRecord)
async def submit_task(request: TaskCreateRequest) -> TaskRecord:
    try:
        return get_service().submit_task(request)
    except DevPlaneError as exc:
        _raise_http(exc)


@router.get("/tasks/{task_id}", response_model=TaskRecord)
async def get_task(task_id: str) -> TaskRecord:
    try:
        return get_service().get_task(task_id)
    except DevPlaneError as exc:
        _raise_http(exc)


@router.post("/tasks/{task_id}/answer", response_model=TaskRecord)
async def answer_clarifications(
    task_id: str, answers: list[ClarificationAnswer]
) -> TaskRecord:
    try:
        return get_service().answer_clarifications(task_id, answers)
    except DevPlaneError as exc:
        _raise_http(exc)


@router.post("/tasks/{task_id}/resume", response_model=RunRecord)
async def resume_task(task_id: str, request: TaskRunLaunchRequest) -> RunRecord:
    service = get_service()
    try:
        run = service.launch_task(task_id, request)
    except DevPlaneError as exc:
        _raise_http(exc)
    if request.execution_mode == ExecutionMode.EXTERNAL:
        return run
    if run.backend_run_id and run.phase.value not in _TERMINAL_PHASES:
        try:
            snapshot = await get_execution_client().get_run(run.backend_run_id)
            return _sync_run_snapshot(service, run, snapshot)
        except ExecutionBackendError:
            return run

    task = service.get_task(task_id)
    if task.plan is None:
        raise HTTPException(status_code=409, detail="Task plan is missing")

    try:
        snapshot = await get_execution_client().start_run(
            run=run,
            plan=task.plan,
            patch_plan=task.patch_plan,
            callback_base_url=settings.devplane_public_base_url.rstrip("/"),
            task_packet_path=_task_packet_path(run),
        )
        run = service.attach_backend_run(
            run.run_id,
            backend_run_id=snapshot.run_id,
            execution_backend="agent-platform",
        )
        return _sync_run_snapshot(service, run, snapshot)
    except ExecutionBackendError as exc:
        service.sync_backend_run(
            run.run_id,
            phase=RunPhase.FAILED,
            status=TaskState.FAILED,
            summary=f"Internal execution dispatch failed: {exc}",
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/cancel", response_model=TaskRecord)
async def cancel_task(task_id: str) -> TaskRecord:
    service = get_service()
    try:
        task = service.get_task(task_id)
    except DevPlaneError as exc:
        _raise_http(exc)
    if task.current_run_id:
        run = service.get_run(task.current_run_id)
        if run.backend_run_id and run.phase.value not in _TERMINAL_PHASES:
            try:
                await get_execution_client().cancel_run(run.backend_run_id)
            except ExecutionBackendError:
                pass
    try:
        return service.cancel_task(task_id)
    except DevPlaneError as exc:
        _raise_http(exc)


@router.get("/tasks/{task_id}/dossier", response_model=TaskDossier)
async def get_dossier(task_id: str) -> TaskDossier:
    try:
        return get_service().get_dossier(task_id)
    except DevPlaneError as exc:
        _raise_http(exc)


@router.post("/tasks/{task_id}/publish", response_model=TaskRecord)
async def publish_task(task_id: str, request: PublishRequest) -> TaskRecord:
    try:
        return get_service().publish_task(task_id, request)
    except DevPlaneError as exc:
        _raise_http(exc)


@router.get("/runs", response_model=list[RunRecord])
async def list_runs() -> list[RunRecord]:
    return get_service().list_runs()


@router.get("/runs/{run_id}", response_model=RunRecord)
async def get_run(run_id: str) -> RunRecord:
    service = get_service()
    try:
        run = service.get_run(run_id)
    except DevPlaneError as exc:
        _raise_http(exc)
    if run.backend_run_id and run.phase.value not in _TERMINAL_PHASES:
        try:
            snapshot = await get_execution_client().get_run(run.backend_run_id)
            run = _sync_run_snapshot(service, run, snapshot)
        except ExecutionBackendError:
            pass
    return run


@router.post("/runs/{run_id}/events", response_model=RunRecord)
async def append_run_event(run_id: str, request: RunEventRequest) -> RunRecord:
    try:
        return get_service().append_run_event(run_id, request)
    except DevPlaneError as exc:
        _raise_http(exc)


@router.post("/runs/{run_id}/complete", response_model=RunRecord)
async def complete_run(run_id: str, request: RunCompleteRequest) -> RunRecord:
    try:
        return get_service().complete_run(run_id, request)
    except DevPlaneError as exc:
        _raise_http(exc)
