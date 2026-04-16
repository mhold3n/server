from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from domain_engineering.core import intake_engineering_request

from src.devplane.executor_client import (
    DevPlaneExecutionClient,
    ExecutionBackendError,
)
from src.devplane.models import (
    PatchPlanRecord,
    ProjectGithubSettings,
    ProjectRecord,
    RunRecord,
    TaskDossier,
    TaskPlan,
    TaskRecord,
    TaskRequestRecord,
    TaskState,
    WorkspaceRecord,
)
from src.devplane.workspace import WorkspaceError, WorkspaceManager


def _git(cmd: list[str], cwd: Path) -> None:
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    subprocess.run(
        ["git", *cmd], cwd=str(cwd), env=env, check=True, capture_output=True
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.name", "Birtha Test"], repo)
    _git(["config", "user.email", "birtha@example.com"], repo)
    (repo / "README.md").write_text("# Example\n", encoding="utf-8")
    _git(["add", "."], repo)
    _git(["commit", "-m", "init"], repo)


def test_workspace_manager_parse_github_handles_ssh_and_https(tmp_path: Path) -> None:
    mgr = WorkspaceManager(
        devplane_root=tmp_path / "devplane", control_plane_root=tmp_path / "cp"
    )

    ssh = mgr._parse_github("git@github.com:acme/project.git", "main")
    assert isinstance(ssh, ProjectGithubSettings)
    assert ssh.owner == "acme"
    assert ssh.repo == "project"
    assert ssh.default_pr_base == "main"

    https = mgr._parse_github("https://github.com/acme/project.git", "develop")
    assert https.owner == "acme"
    assert https.repo == "project"
    assert https.default_pr_base == "develop"

    none = mgr._parse_github(None, "main")
    assert none.owner is None
    assert none.repo is None
    assert none.default_pr_base == "main"


def test_workspace_manager_resolve_default_branch_falls_back_to_head(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    mgr = WorkspaceManager(
        devplane_root=tmp_path / "devplane", control_plane_root=tmp_path / "cp"
    )
    # No remote HEAD configured → should fall back to local HEAD branch name.
    assert mgr._resolve_default_branch(repo, "origin") == "main"


def test_workspace_manager_detect_file_changes_and_task_packet(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    mgr = WorkspaceManager(
        devplane_root=tmp_path / "devplane", control_plane_root=tmp_path / "cp"
    )

    project = ProjectRecord(
        project_id="p1",
        name="proj",
        canonical_repo_path=str(repo),
        workspace_root=str(tmp_path / "workspaces"),
        default_branch="main",
        remote_name="origin",
        github=ProjectGithubSettings(default_pr_base="main"),
    )
    workspace, _commands = mgr.create_workspace(
        project=project, branch_name="task/p1", task_id="t1"
    )

    # Modify a file and ensure we detect changes.
    new_file = Path(workspace.worktree_path) / "NEWFILE.txt"
    new_file.write_text("x\n", encoding="utf-8")
    changes = mgr.detect_file_changes(workspace)
    assert any("NEWFILE.txt" in c.path for c in changes)

    # Ensure task packet writing produces JSON with expected fields.
    req = TaskRequestRecord(
        task_id="t1",
        project_id=project.project_id,
        user_intent="Do the thing",
    )
    dossier = TaskDossier(
        task_id="t1",
        project_id=project.project_id,
        state=TaskState.PLANNING,
        request=req,
        workspace=workspace,
    )
    task = TaskRecord(
        task_id="t1",
        project_id=project.project_id,
        state=TaskState.PLANNING,
        request=req,
        dossier=dossier,
    )
    engineering_bundle = intake_engineering_request(
        user_input=req.user_intent,
        task_plan=TaskPlan(
            project_id=project.project_id,
            objective="Implement a governed repository change",
            constraints=["Only touch the isolated workspace"],
            acceptance_criteria=["Verification commands pass"],
            implementation_outline=["Inspect the repo", "Apply the minimal change"],
            verification_plan=["git status --short"],
        ).model_dump(mode="json"),
        project_context={
            "project_id": project.project_id,
            "project_name": project.name,
        },
    )
    artifacts = mgr.write_task_packet(
        workspace=workspace,
        task=task,
        engineering_bundle=engineering_bundle,
    )
    artifact = next(item for item in artifacts if item.kind == "task_packet")
    packet_path = Path(artifact.path)
    body = json.loads(packet_path.read_text(encoding="utf-8"))
    assert body["task_id"] == "t1"
    assert body["project_id"] == "p1"
    assert body["dossier_path"].endswith("dossier.json")
    assert body["problem_brief_ref"].startswith("artifact://problem_brief/")
    assert body["engineering_state_ref"].startswith("artifact://engineering_state/")


def test_workspace_manager_create_workspace_returns_existing_dir_without_git(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    mgr = WorkspaceManager(
        devplane_root=tmp_path / "devplane", control_plane_root=tmp_path / "cp"
    )
    project = ProjectRecord(
        project_id="p1",
        name="proj",
        canonical_repo_path=str(repo),
        workspace_root=str(tmp_path / "workspaces"),
        default_branch="main",
        remote_name="origin",
        github=ProjectGithubSettings(default_pr_base="main"),
    )

    # Pre-create a non-empty workspace dir so create_workspace takes the early return path.
    existing_dir = Path(project.workspace_root) / "tasks" / "t2"
    existing_dir.mkdir(parents=True, exist_ok=True)
    (existing_dir / "sentinel.txt").write_text("x", encoding="utf-8")

    workspace, commands = mgr.create_workspace(
        project=project, branch_name="task/p1", task_id="t2"
    )
    assert workspace.worktree_path == str(existing_dir.resolve())
    assert commands == []


def test_workspace_manager_inspect_project_rejects_dirty_worktree(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "README.md").write_text("# dirty\n", encoding="utf-8")

    mgr = WorkspaceManager(
        devplane_root=tmp_path / "devplane", control_plane_root=tmp_path / "cp"
    )
    with pytest.raises(WorkspaceError):
        mgr.inspect_project(repo, remote_name="origin", requested_default_branch=None)


def test_workspace_manager_optional_git_output_and_run_git_error_paths(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    mgr = WorkspaceManager(
        devplane_root=tmp_path / "devplane", control_plane_root=tmp_path / "cp"
    )

    # Optional output should return None on failure.
    assert mgr._optional_git_output(repo, ["rev-parse", "--verify", "nope"]) is None

    # _run_git should raise WorkspaceError on failure.
    with pytest.raises(WorkspaceError):
        mgr._run_git(repo, ["rev-parse", "--verify", "nope"])


def test_workspace_manager_publish_workspace_push_and_pr_error_paths(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    mgr = WorkspaceManager(
        devplane_root=tmp_path / "devplane", control_plane_root=tmp_path / "cp"
    )

    project = ProjectRecord(
        project_id="p1",
        name="proj",
        canonical_repo_path=str(repo),
        workspace_root=str(tmp_path / "workspaces"),
        default_branch="main",
        remote_name="origin",
        github=ProjectGithubSettings(default_pr_base="main"),
    )
    workspace, _commands = mgr.create_workspace(
        project=project, branch_name="task/push", task_id="t3"
    )
    (Path(workspace.worktree_path) / "X.txt").write_text("x\n", encoding="utf-8")

    # Force PR creation path where gh is missing.
    from src.devplane.models import PublishRequest

    request = PublishRequest(push=True, create_pr=True, remote_name="origin")
    with patch("src.devplane.workspace.shutil.which", return_value=None):
        result, commands = mgr.publish_workspace(
            project=project, workspace=workspace, request=request
        )

    # Push will fail because there is no remote configured; PR will fail due to missing gh.
    assert result.branch_name == workspace.branch_name
    assert result.errors
    assert commands  # we should have recorded at least git add/commit attempts


def test_workspace_manager_create_pr_success_and_failure_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    mgr = WorkspaceManager(
        devplane_root=tmp_path / "devplane", control_plane_root=tmp_path / "cp"
    )

    project = ProjectRecord(
        project_id="p1",
        name="proj",
        canonical_repo_path=str(repo),
        workspace_root=str(tmp_path / "workspaces"),
        default_branch="main",
        remote_name="origin",
        github=ProjectGithubSettings(default_pr_base="main"),
    )
    workspace, _commands = mgr.create_workspace(
        project=project, branch_name="task/pr", task_id="t4"
    )

    from src.devplane.models import PublishRequest

    request = PublishRequest(push=False, create_pr=True)

    fake_completed = subprocess.CompletedProcess(
        args=["gh", "pr", "create"],
        returncode=0,
        stdout="https://example.invalid/pr/1\n",
        stderr="",
    )
    fake_failed = subprocess.CompletedProcess(
        args=["gh", "pr", "create"],
        returncode=1,
        stdout="",
        stderr="boom",
    )

    with patch("src.devplane.workspace.shutil.which", return_value="/usr/bin/gh"):
        with patch(
            "src.devplane.workspace.subprocess.run", return_value=fake_completed
        ):
            pr_url, commands, errors = mgr._create_pr(
                workspace=workspace, project=project, request=request
            )
            assert pr_url == "https://example.invalid/pr/1"
            assert commands
            assert errors == []

        with patch("src.devplane.workspace.subprocess.run", return_value=fake_failed):
            pr_url, commands, errors = mgr._create_pr(
                workspace=workspace, project=project, request=request
            )
            assert pr_url is None
            assert commands
            assert errors


def test_workspace_manager_publish_workspace_no_changes_local_mode(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    mgr = WorkspaceManager(
        devplane_root=tmp_path / "devplane", control_plane_root=tmp_path / "cp"
    )

    project = ProjectRecord(
        project_id="p1",
        name="proj",
        canonical_repo_path=str(repo),
        workspace_root=str(tmp_path / "workspaces"),
        default_branch="main",
        remote_name="origin",
        github=ProjectGithubSettings(default_pr_base="main"),
    )
    workspace, _commands = mgr.create_workspace(
        project=project, branch_name="task/clean", task_id="t5"
    )

    from src.devplane.models import PublishRequest

    request = PublishRequest(push=False, create_pr=False)
    result, commands = mgr.publish_workspace(
        project=project, workspace=workspace, request=request
    )
    assert result.mode.value in ("local", "LOCAL") or result.mode.name == "LOCAL"
    # No changes → no commit commands, but we still return a result.
    assert result.branch_name == workspace.branch_name


def test_workspace_manager_suggest_verification_commands_and_porcelain_mapping(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "tests").mkdir(parents=True, exist_ok=True)
    (repo / "package.json").write_text(
        json.dumps({"scripts": {"lint": "x", "test": "y"}}),
        encoding="utf-8",
    )
    (repo / "pyproject.toml").write_text("[tool.ruff]\n[tool.mypy]\n", encoding="utf-8")

    mgr = WorkspaceManager(
        devplane_root=tmp_path / "devplane", control_plane_root=tmp_path / "cp"
    )
    cmds = mgr._suggest_verification_commands(repo)
    assert "npm run lint" in cmds
    assert "npm test" in cmds
    assert "pytest -q" in cmds
    assert "ruff check ." in cmds
    assert "mypy ." in cmds

    assert mgr._map_porcelain_status("??") is not None
    assert mgr._map_porcelain_status("R ") is not None
    assert mgr._map_porcelain_status("D ") is not None
    assert mgr._map_porcelain_status("A ") is not None
    assert mgr._map_porcelain_status("M ") is not None
    assert mgr._map_porcelain_status("  ") is not None


def test_workspace_manager_detect_file_changes_skips_short_lines(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    mgr = WorkspaceManager(
        devplane_root=tmp_path / "devplane", control_plane_root=tmp_path / "cp"
    )
    workspace = WorkspaceRecord(
        canonical_repo_path=str(repo),
        worktree_path=str(repo),
        branch_name="b",
        base_branch="main",
        remote_name="origin",
    )
    with patch.object(mgr, "_optional_git_output", return_value="?\n?? X.txt\n"):
        changes = mgr.detect_file_changes(workspace)
    assert any(c.path == "X.txt" for c in changes)


@pytest.mark.asyncio
async def test_execution_client_errors_and_success(tmp_path: Path) -> None:
    base = "http://agent-platform.test"
    client = DevPlaneExecutionClient(base_url=base, timeout=1.0)

    # Run without workspace should fail fast.
    run = RunRecord(run_id="r1", task_id="t1", project_id="p1", workspace=None)
    with pytest.raises(ExecutionBackendError) as exc:
        await client.start_run(
            run=run,
            plan=TaskPlan(project_id="p1", objective="x"),
            patch_plan=None,
            callback_base_url="http://api.test",
            task_packet_path=None,
        )
    assert exc.value.status_code == 409

    # Exercise HTTP transport error path.
    run = run.model_copy(
        update={
            "workspace": WorkspaceRecord(
                canonical_repo_path="/tmp/x",
                worktree_path="/tmp/y",
                branch_name="b",
                base_branch="main",
                remote_name="origin",
            )
        }
    )
    with patch(
        "httpx.AsyncClient.request",
        new=AsyncMock(side_effect=httpx.ConnectError("nope")),
    ):
        with pytest.raises(ExecutionBackendError):
            await client.start_run(
                run=run,
                plan=TaskPlan(project_id="p1", objective="x"),
                patch_plan=PatchPlanRecord(patches=[]),
                callback_base_url="http://api.test",
                task_packet_path=None,
            )

    # Exercise non-2xx response path.
    async def _fake_request(*args, **kwargs):
        return httpx.Response(404, text="missing")

    with patch("httpx.AsyncClient.request", new=AsyncMock(side_effect=_fake_request)):
        with pytest.raises(ExecutionBackendError) as exc2:
            await client.get_run("backend-1")
        assert exc2.value.status_code == 404
