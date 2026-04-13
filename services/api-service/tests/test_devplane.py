from __future__ import annotations

import os
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from src.config import settings
from src.devplane.executor_client import BackendRunSnapshot
from src.main import app
from src.routes.devplane import reset_devplane_service_for_tests


def _run(cmd: list[str], cwd: Path) -> None:
    # Test repos should not depend on developer-global git config (e.g. commit signing).
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-b", "main"], repo)
    _run(["git", "config", "user.name", "Birtha Test"], repo)
    _run(["git", "config", "user.email", "birtha@example.com"], repo)
    (repo / "README.md").write_text("# Example\n", encoding="utf-8")
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_smoke.py").write_text(
        "def test_smoke():\n    assert True\n",
        encoding="utf-8",
    )
    _run(["git", "add", "."], repo)
    _run(["git", "commit", "-m", "Initial commit"], repo)


class _FakeExecutionClient:
    def __init__(self) -> None:
        self.started: list[str] = []
        self.cancelled: list[str] = []
        self.snapshots: dict[str, BackendRunSnapshot] = {}

    async def start_run(self, **kwargs) -> BackendRunSnapshot:
        run = kwargs["run"]
        backend_run_id = f"backend-{run.run_id}"
        self.started.append(run.run_id)
        snapshot = BackendRunSnapshot(
            run_id=backend_run_id,
            control_run_id=run.run_id,
            status="queued",
            phase="planning",
            summary="Internal execution accepted by agent-platform",
        )
        self.snapshots[backend_run_id] = snapshot
        return snapshot

    async def get_run(self, backend_run_id: str) -> BackendRunSnapshot:
        snapshot = self.snapshots[backend_run_id]
        return snapshot.model_copy(
            update={
                "status": "ready_to_publish",
                "phase": "ready_to_publish",
                "summary": "Internal execution completed",
                "verification_results": [
                    {
                        "name": "pytest",
                        "command": "pytest -q",
                        "status": "passed",
                    }
                ],
                "artifacts": [
                    {
                        "name": "agent-platform-output",
                        "path": "/tmp/agent-platform-output.md",
                        "kind": "run_summary",
                    }
                ],
            }
        )

    async def cancel_run(self, backend_run_id: str) -> BackendRunSnapshot:
        self.cancelled.append(backend_run_id)
        snapshot = self.snapshots[backend_run_id]
        return snapshot.model_copy(
            update={
                "status": "cancelled",
                "phase": "cancelled",
                "summary": "Cancellation requested",
            }
        )


def test_register_project_rejects_control_plane_repo(tmp_path: Path) -> None:
    original_root = settings.devplane_root
    original_db = settings.devplane_db_path
    settings.devplane_root = str(tmp_path / "devplane")
    settings.devplane_db_path = str(tmp_path / "devplane.sqlite3")
    reset_devplane_service_for_tests()
    client = TestClient(app)
    try:
        resp = client.post(
            "/api/dev/projects",
            json={
                "name": "control-plane",
                "canonical_repo_path": str(Path.cwd()),
            },
        )
        assert resp.status_code == 409
    finally:
        settings.devplane_root = original_root
        settings.devplane_db_path = original_db
        reset_devplane_service_for_tests()


def test_devplane_internal_dispatch_lifecycle_and_publish(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "project-alpha"
    _init_git_repo(repo)
    fake_client = _FakeExecutionClient()

    original_root = settings.devplane_root
    original_db = settings.devplane_db_path
    original_public_base = settings.devplane_public_base_url
    settings.devplane_root = str(tmp_path / "devplane")
    settings.devplane_db_path = str(tmp_path / "devplane.sqlite3")
    settings.devplane_public_base_url = "http://testserver"
    reset_devplane_service_for_tests()
    monkeypatch.setattr("src.routes.devplane.get_execution_client", lambda: fake_client)
    client = TestClient(app)

    try:
        register = client.post(
            "/api/dev/projects",
            json={
                "name": "project-alpha",
                "canonical_repo_path": str(repo),
            },
        )
        assert register.status_code == 200
        project = register.json()
        project_id = project["project_id"]
        assert project["default_branch"] == "main"

        task_resp = client.post(
            "/api/dev/tasks",
            json={
                "project_id": project_id,
                "user_intent": "Fix the pipeline",
            },
        )
        assert task_resp.status_code == 200
        task = task_resp.json()
        assert task["state"] == "pending_clarification"
        task_id = task["task_id"]
        assert len(task["clarifications"]["questions"]) >= 1

        clarified = client.post(
            f"/api/dev/tasks/{task_id}/answer",
            json=[
                {
                    "question_id": "objective_scope",
                    "answer": "Implement a dev-plane task packet workflow",
                },
                {
                    "question_id": "acceptance_criteria",
                    "answer": "The task packet is written and publish metadata is preserved",
                },
                {
                    "question_id": "constraints",
                    "answer": "Only touch the isolated workspace and capture commands in the dossier",
                },
            ],
        )
        assert clarified.status_code == 200
        clarified_task = clarified.json()
        assert clarified_task["state"] == "ready"
        assert "pytest -q" in clarified_task["plan"]["verification_plan"]

        run_resp = client.post(
            f"/api/dev/tasks/{task_id}/resume",
            json={},
        )
        assert run_resp.status_code == 200
        run = run_resp.json()
        run_id = run["run_id"]
        worktree_path = Path(run["workspace"]["worktree_path"])
        assert worktree_path.exists()
        assert (worktree_path / ".birtha" / "task-packet.json").exists()
        manifest = (worktree_path / ".birtha" / "task-packet.json").read_text(encoding="utf-8")
        assert "knowledge_pool_assessment_ref" in manifest
        assert run["backend_run_id"].startswith("backend-")
        assert run["execution_mode"] == "internal"
        assert run["knowledge_pool_assessment_ref"]
        assert "knowledge_pool_coverage" in run
        assert fake_client.started == [run_id]

        run_status = client.get(f"/api/dev/runs/{run_id}")
        assert run_status.status_code == 200
        synced_run = run_status.json()
        assert synced_run["phase"] == "ready_to_publish"

        dossier_resp = client.get(f"/api/dev/tasks/{task_id}/dossier")
        assert dossier_resp.status_code == 200
        dossier = dossier_resp.json()
        assert dossier["state"] == "ready_to_publish"
        assert dossier["artifacts"]
        assert dossier["knowledge_pool_assessment_ref"]
        assert "knowledge_pool_coverage" in dossier
        assert dossier["verification_results"][0]["status"] == "passed"

        publish_resp = client.post(
            f"/api/dev/tasks/{task_id}/publish",
            json={"push": False, "create_pr": False},
        )
        assert publish_resp.status_code == 200
        published = publish_resp.json()
        assert published["state"] == "published"
        assert published["dossier"]["publish_result"]["branch_name"].startswith("birtha/")
        assert published["dossier"]["publish_result"]["commit_sha"]

        reset_devplane_service_for_tests()
        recovered = client.get(f"/api/dev/tasks/{task_id}")
        assert recovered.status_code == 200
        assert recovered.json()["state"] == "published"
    finally:
        settings.devplane_root = original_root
        settings.devplane_db_path = original_db
        settings.devplane_public_base_url = original_public_base
        reset_devplane_service_for_tests()


def test_devplane_external_legacy_callbacks_still_work(tmp_path: Path) -> None:
    repo = tmp_path / "project-beta"
    _init_git_repo(repo)

    original_root = settings.devplane_root
    original_db = settings.devplane_db_path
    settings.devplane_root = str(tmp_path / "devplane")
    settings.devplane_db_path = str(tmp_path / "devplane.sqlite3")
    reset_devplane_service_for_tests()
    client = TestClient(app)

    try:
        project_id = client.post(
            "/api/dev/projects",
            json={"name": "project-beta", "canonical_repo_path": str(repo)},
        ).json()["project_id"]

        task_resp = client.post(
            "/api/dev/tasks",
            json={
                "project_id": project_id,
                "user_intent": "Update the project beta pipeline",
                "context": {
                    "acceptance_criteria": ["Document the work in the dossier"],
                    "constraints": ["Only capture external callback updates"],
                },
            },
        )
        assert task_resp.status_code == 200
        task = task_resp.json()
        if task["state"] == "pending_clarification":
            task = client.post(
                f"/api/dev/tasks/{task['task_id']}/answer",
                json=[
                    {
                        "question_id": "objective_scope",
                        "answer": "Capture external run callbacks",
                    }
                ],
            ).json()

        run_resp = client.post(
            f"/api/dev/tasks/{task['task_id']}/resume",
            json={
                "execution_mode": "external",
                "agent_session_id": "openclaw-session-1",
            },
        )
        assert run_resp.status_code == 200
        run = run_resp.json()
        assert run["execution_mode"] == "external"
        assert run["backend_run_id"] is None

        event_resp = client.post(
            f"/api/dev/runs/{run['run_id']}/events",
            json={
                "phase": "implementing",
                "message": "External operator reported progress",
                "commands": [
                    {
                        "command": "pytest -q",
                        "cwd": run["workspace"]["worktree_path"],
                        "exit_code": 0,
                        "source": "openclaw",
                    }
                ],
            },
        )
        assert event_resp.status_code == 200
        complete_resp = client.post(
            f"/api/dev/runs/{run['run_id']}/complete",
            json={
                "status": "ready_to_publish",
                "summary": "External run finished",
            },
        )
        assert complete_resp.status_code == 200
        dossier = client.get(f"/api/dev/tasks/{task['task_id']}/dossier").json()
        assert dossier["state"] == "ready_to_publish"
        assert dossier["commands"]
    finally:
        settings.devplane_root = original_root
        settings.devplane_db_path = original_db
        reset_devplane_service_for_tests()


def test_devplane_blocked_and_escalated_states_round_trip(tmp_path: Path) -> None:
    repo = tmp_path / "project-gamma"
    _init_git_repo(repo)

    original_root = settings.devplane_root
    original_db = settings.devplane_db_path
    settings.devplane_root = str(tmp_path / "devplane")
    settings.devplane_db_path = str(tmp_path / "devplane.sqlite3")
    reset_devplane_service_for_tests()
    client = TestClient(app)

    try:
        project_id = client.post(
            "/api/dev/projects",
            json={"name": "project-gamma", "canonical_repo_path": str(repo)},
        ).json()["project_id"]
        task = client.post(
            "/api/dev/tasks",
            json={
                "project_id": project_id,
                "user_intent": "Capture blocked and escalated lifecycle states",
                "engagement_mode": "engineering_task",
                "context": {
                    "acceptance_criteria": ["Expose blocked/escalated through the dossier"],
                    "constraints": ["Use the external callback flow"],
                },
            },
        ).json()
        if task["state"] == "pending_clarification":
            task = client.post(
                f"/api/dev/tasks/{task['task_id']}/answer",
                json=[{"question_id": "objective_scope", "answer": "Track lifecycle states"}],
            ).json()

        run = client.post(
            f"/api/dev/tasks/{task['task_id']}/resume",
            json={"execution_mode": "external"},
        ).json()

        blocked = client.post(
            f"/api/dev/runs/{run['run_id']}/events",
            json={
                "status": "blocked",
                "message": "Awaiting validator availability",
                "lifecycle_reason": "validator_unavailable",
                "lifecycle_detail": {"validator": "deterministic_validator"},
            },
        )
        assert blocked.status_code == 200
        blocked_run = blocked.json()
        assert blocked_run["phase"] == "blocked"
        task_after_block = client.get(f"/api/dev/tasks/{task['task_id']}").json()
        assert task_after_block["state"] == "blocked"
        assert task_after_block["lifecycle_reason"] == "validator_unavailable"

        escalated = client.post(
            f"/api/dev/runs/{run['run_id']}/events",
            json={
                "status": "escalated",
                "message": "Awaiting strategic review",
                "lifecycle_reason": "awaiting_strategic_review",
                "lifecycle_detail": {"packet": "artifact://escalation_record/esc-1"},
            },
        )
        assert escalated.status_code == 200
        escalated_run = escalated.json()
        assert escalated_run["phase"] == "escalated"
        assert escalated_run["lifecycle_reason"] == "awaiting_strategic_review"
        dossier = client.get(f"/api/dev/tasks/{task['task_id']}/dossier").json()
        assert dossier["state"] == "escalated"
        assert dossier["lifecycle_reason"] == "awaiting_strategic_review"

        invalid_complete = client.post(
            f"/api/dev/runs/{run['run_id']}/complete",
            json={"status": "blocked", "summary": "Should be rejected"},
        )
        assert invalid_complete.status_code == 400

        resumed = client.post(
            f"/api/dev/tasks/{task['task_id']}/resume",
            json={"execution_mode": "external"},
        )
        assert resumed.status_code == 200
        assert resumed.json()["run_id"] == run["run_id"]
    finally:
        settings.devplane_root = original_root
        settings.devplane_db_path = original_db
        reset_devplane_service_for_tests()
