"""Workspace isolation and Git delivery utilities."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import (
    ArtifactRecord,
    CommandExecution,
    FileChangeRecord,
    FileChangeType,
    ProjectGithubSettings,
    ProjectRecord,
    PublishMode,
    PublishRequest,
    PublishResult,
    TaskRecord,
    WorkspaceRecord,
)


class WorkspaceError(RuntimeError):
    """Raised when workspace isolation or Git operations fail."""

    def __init__(self, message: str, command: CommandExecution | None = None):
        super().__init__(message)
        self.command = command


@dataclass(frozen=True)
class ProjectInspection:
    """Resolved Git metadata for a project checkout."""

    top_level: Path
    default_branch: str
    remote_name: str
    remote_url: str | None
    github: ProjectGithubSettings
    verification_commands: list[str]


class WorkspaceManager:
    """Manage isolated task worktrees under the development plane root."""

    def __init__(self, *, devplane_root: Path, control_plane_root: Path):
        self.devplane_root = devplane_root.resolve()
        self.devplane_root.mkdir(parents=True, exist_ok=True)
        self.control_plane_root = control_plane_root.resolve()

    def inspect_project(
        self,
        project_path: Path,
        *,
        remote_name: str,
        requested_default_branch: str | None,
    ) -> ProjectInspection:
        """Validate and inspect a registered canonical checkout."""
        top_level = Path(
            self._run_git(
                project_path,
                ["rev-parse", "--show-toplevel"],
            ).stdout_excerpt or ""
        ).resolve()
        self._assert_project_is_isolated(top_level)
        self._assert_clean_worktree(top_level)
        remote_url = self._optional_git_output(
            top_level,
            ["config", "--get", f"remote.{remote_name}.url"],
        )
        default_branch = requested_default_branch or self._resolve_default_branch(
            top_level, remote_name
        )
        return ProjectInspection(
            top_level=top_level,
            default_branch=default_branch,
            remote_name=remote_name,
            remote_url=remote_url,
            github=self._parse_github(remote_url, default_branch),
            verification_commands=self._suggest_verification_commands(top_level),
        )

    def create_workspace(
        self,
        *,
        project: ProjectRecord,
        branch_name: str,
        task_id: str,
    ) -> tuple[WorkspaceRecord, list[CommandExecution]]:
        """Create a dedicated git worktree for the task."""
        workspace_dir = (Path(project.workspace_root) / "tasks" / task_id).resolve()
        workspace_dir.parent.mkdir(parents=True, exist_ok=True)
        if workspace_dir.exists() and any(workspace_dir.iterdir()):
            record = WorkspaceRecord(
                canonical_repo_path=project.canonical_repo_path,
                worktree_path=str(workspace_dir),
                branch_name=branch_name,
                base_branch=project.default_branch,
                remote_name=project.remote_name,
            )
            return (record, [])

        start_ref = self._resolve_start_ref(Path(project.canonical_repo_path), project)
        command = self._run_git(
            Path(project.canonical_repo_path),
            ["worktree", "add", "-b", branch_name, str(workspace_dir), start_ref],
        )
        record = WorkspaceRecord(
            canonical_repo_path=project.canonical_repo_path,
            worktree_path=str(workspace_dir),
            branch_name=branch_name,
            base_branch=project.default_branch,
            remote_name=project.remote_name,
        )
        return (record, [command])

    def write_task_packet(
        self,
        *,
        workspace: WorkspaceRecord,
        task: TaskRecord,
        engineering_bundle: dict[str, Any] | None = None,
    ) -> list[ArtifactRecord]:
        """Write the task packet and any governing engineering artifacts."""
        packet_dir = Path(workspace.worktree_path) / ".birtha"
        packet_dir.mkdir(parents=True, exist_ok=True)
        packet_path = packet_dir / "task-packet.json"
        artifacts: list[ArtifactRecord] = []
        manifest: dict[str, Any]
        if engineering_bundle:
            artifacts.extend(
                self._write_engineering_artifacts(
                    packet_dir=packet_dir,
                    engineering_bundle=engineering_bundle,
                )
            )
            task_packets = engineering_bundle.get("task_packets") or []
            active_task_packet = next(
                (
                    packet
                    for packet in task_packets
                    if packet.get("task_type") != "VALIDATION"
                ),
                task_packets[0] if task_packets else None,
            )
            manifest = {
                "task_id": task.task_id,
                "project_id": task.project_id,
                "state": task.state,
                "reasoning_tier": getattr(task.dossier, "reasoning_tier", None),
                "plan": task.plan.model_dump(mode="json") if task.plan else None,
                "patch_plan": (
                    task.patch_plan.model_dump(mode="json") if task.patch_plan else None
                ),
                "clarifications": task.clarifications.model_dump(mode="json"),
                "problem_brief_ref": engineering_bundle.get("problem_brief_ref"),
                "problem_brief": engineering_bundle.get("problem_brief"),
                "engineering_state_ref": engineering_bundle.get("engineering_state_ref"),
                "engineering_state": engineering_bundle.get("engineering_state"),
                "task_queue": engineering_bundle.get("task_queue"),
                "task_packet_refs": engineering_bundle.get("task_packet_refs", []),
                "task_packets_path": str(packet_dir / "task-packets"),
                "active_task_packet_ref": (
                    f"artifact://task_packet/{active_task_packet['task_packet_id']}"
                    if active_task_packet
                    else None
                ),
                "active_task_packet": active_task_packet,
                "required_gates": engineering_bundle.get("required_gates", []),
                "ready_for_task_decomposition": engineering_bundle.get(
                    "ready_for_task_decomposition", False
                ),
                "escalation_packets": getattr(task.dossier, "escalation_packets", []),
                "api_brain_verdict": getattr(task.dossier, "api_brain_verdict", None),
                "dossier_path": str(packet_dir / "dossier.json"),
            }
        else:
            manifest = {
                "task_id": task.task_id,
                "project_id": task.project_id,
                "state": task.state,
                "reasoning_tier": getattr(task.dossier, "reasoning_tier", None),
                "plan": task.plan.model_dump(mode="json") if task.plan else None,
                "patch_plan": (
                    task.patch_plan.model_dump(mode="json") if task.patch_plan else None
                ),
                "clarifications": task.clarifications.model_dump(mode="json"),
                "escalation_packets": getattr(task.dossier, "escalation_packets", []),
                "api_brain_verdict": getattr(task.dossier, "api_brain_verdict", None),
                "dossier_path": str(packet_dir / "dossier.json"),
            }
        packet_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        dossier_path = packet_dir / "dossier.json"
        dossier_path.write_text(
            task.dossier.model_dump_json(indent=2), encoding="utf-8"
        )
        artifacts.insert(
            0,
            ArtifactRecord(
                name="task-packet",
                path=str(packet_path),
                kind="task_packet",
                description="OpenClaw/operator task packet for the isolated workspace",
            ),
        )
        return artifacts

    def _write_engineering_artifacts(
        self,
        *,
        packet_dir: Path,
        engineering_bundle: dict[str, Any],
    ) -> list[ArtifactRecord]:
        """Persist governing control-plane artifacts alongside the task manifest."""
        artifacts: list[ArtifactRecord] = []
        created_at = engineering_bundle.get("problem_brief", {}).get("created_at")
        updated_at = engineering_bundle.get("problem_brief", {}).get("updated_at")

        def _typed_record(
            *,
            name: str,
            file_path: Path,
            artifact_type: str,
            payload: dict[str, Any],
            input_refs: list[str],
        ) -> ArtifactRecord:
            return ArtifactRecord(
                name=name,
                path=str(file_path),
                kind=artifact_type.lower(),
                artifact_id=str(
                    payload.get(
                        f"{artifact_type.lower()}_id",
                        payload.get("task_packet_id")
                        or payload.get("task_queue_id")
                        or payload.get("problem_brief_id")
                        or payload.get("engineering_state_id"),
                    )
                ),
                artifact_type=artifact_type,
                schema_version=str(payload.get("schema_version", "1.0.0")),
                artifact_status="ACTIVE",
                validation_state="VALID",
                producer={
                    "component": "devplane.workspace_manager",
                    "executor": "local_general_model",
                },
                input_artifact_refs=input_refs,
                payload=payload,
                created_at=created_at,
                updated_at=updated_at,
                description=f"Persisted {artifact_type} artifact for the engineering-governed task run.",
            )

        problem_brief = engineering_bundle.get("problem_brief")
        if isinstance(problem_brief, dict):
            problem_brief_path = packet_dir / "problem-brief.json"
            problem_brief_path.write_text(
                json.dumps(problem_brief, indent=2),
                encoding="utf-8",
            )
            artifacts.append(
                _typed_record(
                    name="problem-brief",
                    file_path=problem_brief_path,
                    artifact_type="PROBLEM_BRIEF",
                    payload=problem_brief,
                    input_refs=[],
                )
            )

        engineering_state = engineering_bundle.get("engineering_state")
        if isinstance(engineering_state, dict):
            engineering_state_path = packet_dir / "engineering-state.json"
            engineering_state_path.write_text(
                json.dumps(engineering_state, indent=2),
                encoding="utf-8",
            )
            artifacts.append(
                _typed_record(
                    name="engineering-state",
                    file_path=engineering_state_path,
                    artifact_type="ENGINEERING_STATE",
                    payload=engineering_state,
                    input_refs=[engineering_bundle.get("problem_brief_ref")] if engineering_bundle.get("problem_brief_ref") else [],
                )
            )

        task_queue = engineering_bundle.get("task_queue")
        if isinstance(task_queue, dict):
            task_queue_path = packet_dir / "task-queue.json"
            task_queue_path.write_text(
                json.dumps(task_queue, indent=2),
                encoding="utf-8",
            )
            artifacts.append(
                _typed_record(
                    name="task-queue",
                    file_path=task_queue_path,
                    artifact_type="TASK_QUEUE",
                    payload=task_queue,
                    input_refs=[
                        ref
                        for ref in [
                            engineering_bundle.get("problem_brief_ref"),
                            engineering_bundle.get("engineering_state_ref"),
                        ]
                        if ref
                    ],
                )
            )

        task_packets = engineering_bundle.get("task_packets") or []
        if task_packets:
            task_packets_dir = packet_dir / "task-packets"
            task_packets_dir.mkdir(parents=True, exist_ok=True)
            for packet in task_packets:
                task_packet_path = task_packets_dir / f"{packet['task_packet_id']}.json"
                task_packet_path.write_text(
                    json.dumps(packet, indent=2),
                    encoding="utf-8",
                )
                artifacts.append(
                    _typed_record(
                        name=f"task-packet-{packet['task_packet_id']}",
                        file_path=task_packet_path,
                        artifact_type="TASK_PACKET",
                        payload=packet,
                        input_refs=packet.get("input_artifact_refs", []),
                    )
                )
        return artifacts

    def detect_file_changes(self, workspace: WorkspaceRecord) -> list[FileChangeRecord]:
        """Return normalized file changes from git status porcelain output."""
        output = self._optional_git_output(
            Path(workspace.worktree_path),
            ["status", "--porcelain"],
        )
        if not output:
            return []
        changes: list[FileChangeRecord] = []
        for line in output.splitlines():
            if len(line) < 4:
                continue
            status = line[:2]
            path = line[3:]
            changes.append(
                FileChangeRecord(
                    path=path,
                    change_type=self._map_porcelain_status(status),
                    git_status=status,
                )
            )
        return changes

    def publish_workspace(
        self,
        *,
        project: ProjectRecord,
        workspace: WorkspaceRecord,
        request: PublishRequest,
    ) -> tuple[PublishResult, list[CommandExecution]]:
        """Commit, optionally push, and optionally create a PR for the task branch."""
        commands: list[CommandExecution] = []
        branch_name = workspace.branch_name
        worktree_path = Path(workspace.worktree_path)
        has_changes = bool(self.detect_file_changes(workspace))
        if has_changes:
            commands.append(self._run_git(worktree_path, ["add", "-A"]))
            commit_message = request.commit_message or f"Implement task {branch_name}"
            commands.append(self._run_git(worktree_path, ["commit", "-m", commit_message]))

        commit_sha = self._optional_git_output(worktree_path, ["rev-parse", "HEAD"])
        result = PublishResult(
            mode=PublishMode.LOCAL if not request.push else PublishMode.REMOTE,
            branch_name=branch_name,
            remote_name=request.remote_name or project.remote_name,
            commit_sha=commit_sha,
        )
        if request.push:
            try:
                commands.append(
                    self._run_git(
                        worktree_path,
                        ["push", "-u", result.remote_name, branch_name],
                    )
                )
                result.pushed = True
            except WorkspaceError as exc:
                result.errors.append(str(exc))

        if request.create_pr:
            pr_url, pr_commands, errors = self._create_pr(
                workspace=workspace,
                project=project,
                request=request,
            )
            commands.extend(pr_commands)
            result.pr_url = pr_url
            result.errors.extend(errors)

        return (result, commands)

    def _create_pr(
        self,
        *,
        workspace: WorkspaceRecord,
        project: ProjectRecord,
        request: PublishRequest,
    ) -> tuple[str | None, list[CommandExecution], list[str]]:
        errors: list[str] = []
        commands: list[CommandExecution] = []
        gh = shutil.which("gh")
        if gh is None:
            return (None, commands, ["GitHub CLI 'gh' is not installed"])

        title = request.pr_title or f"{project.name}: {workspace.branch_name}"
        body = request.pr_body or "Automated task delivery from the Birtha dev plane."
        process = subprocess.run(
            [
                gh,
                "pr",
                "create",
                "--title",
                title,
                "--body",
                body,
                "--base",
                project.github.default_pr_base or project.default_branch,
                "--head",
                workspace.branch_name,
                "--json",
                "url",
                "--jq",
                ".url",
            ],
            cwd=workspace.worktree_path,
            check=False,
            capture_output=True,
            text=True,
        )
        command = CommandExecution(
            command=" ".join(process.args),
            cwd=workspace.worktree_path,
            exit_code=process.returncode,
            stdout_excerpt=(process.stdout or "")[:2000] or None,
            stderr_excerpt=(process.stderr or "")[:2000] or None,
        )
        commands.append(command)
        if process.returncode != 0:
            errors.append(command.stderr_excerpt or "Failed to create pull request")
            return (None, commands, errors)
        pr_url = (process.stdout or "").strip() or None
        return (pr_url, commands, errors)

    def _run_git(self, cwd: Path, args: list[str]) -> CommandExecution:
        # Git operations must not depend on developer-global config such as commit
        # signing helpers (e.g. 1Password SSH signing) being present on the host.
        env = dict(os.environ)
        env["GIT_CONFIG_GLOBAL"] = os.devnull
        env["GIT_CONFIG_SYSTEM"] = os.devnull
        process = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        command = CommandExecution(
            command=" ".join(["git", *args]),
            cwd=str(cwd),
            exit_code=process.returncode,
            stdout_excerpt=(process.stdout or "").strip()[:2000] or None,
            stderr_excerpt=(process.stderr or "").strip()[:2000] or None,
        )
        if process.returncode != 0:
            raise WorkspaceError(command.stderr_excerpt or "Git command failed", command)
        return command

    def _optional_git_output(self, cwd: Path, args: list[str]) -> str | None:
        env = dict(os.environ)
        env["GIT_CONFIG_GLOBAL"] = os.devnull
        env["GIT_CONFIG_SYSTEM"] = os.devnull
        process = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        if process.returncode != 0:
            return None
        return (process.stdout or "").strip() or None

    def _resolve_default_branch(self, cwd: Path, remote_name: str) -> str:
        remote_head = self._optional_git_output(
            cwd, ["symbolic-ref", f"refs/remotes/{remote_name}/HEAD"]
        )
        if remote_head and "/" in remote_head:
            return remote_head.split("/")[-1]
        head_name = self._optional_git_output(cwd, ["rev-parse", "--abbrev-ref", "HEAD"])
        return head_name or "main"

    def _resolve_start_ref(self, cwd: Path, project: ProjectRecord) -> str:
        local_ref = self._optional_git_output(cwd, ["rev-parse", "--verify", project.default_branch])
        if local_ref:
            return project.default_branch
        remote_ref = f"{project.remote_name}/{project.default_branch}"
        remote_verified = self._optional_git_output(cwd, ["rev-parse", "--verify", remote_ref])
        if remote_verified:
            return remote_ref
        raise WorkspaceError(
            f"Unable to resolve base ref '{project.default_branch}' for {project.name}"
        )

    def _assert_project_is_isolated(self, top_level: Path) -> None:
        if self._is_relative_to(top_level, self.control_plane_root):
            raise WorkspaceError(
                "Registered projects must live outside the control-plane repository"
            )

    def _assert_clean_worktree(self, cwd: Path) -> None:
        status = self._optional_git_output(cwd, ["status", "--porcelain"])
        if status:
            raise WorkspaceError(
                "Canonical project checkout must be clean before registration"
            )

    def _parse_github(
        self, remote_url: str | None, default_branch: str
    ) -> ProjectGithubSettings:
        if not remote_url:
            return ProjectGithubSettings(default_pr_base=default_branch)
        cleaned = remote_url.removesuffix(".git")
        owner = None
        repo = None
        if cleaned.startswith("git@github.com:"):
            _, rest = cleaned.split(":", 1)
            parts = rest.split("/", 1)
            if len(parts) == 2:
                owner, repo = parts
        elif "github.com/" in cleaned:
            rest = cleaned.split("github.com/", 1)[1]
            parts = rest.split("/", 1)
            if len(parts) == 2:
                owner, repo = parts
        return ProjectGithubSettings(
            owner=owner,
            repo=repo,
            default_pr_base=default_branch,
        )

    def _suggest_verification_commands(self, cwd: Path) -> list[str]:
        commands: list[str] = []
        package_json = cwd / "package.json"
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}
            scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
            if isinstance(scripts, dict):
                if "lint" in scripts:
                    commands.append("npm run lint")
                if "test" in scripts:
                    commands.append("npm test")

        if (cwd / "pytest.ini").exists() or (cwd / "tests").exists():
            commands.append("pytest -q")
        if (cwd / "pyproject.toml").exists():
            pyproject = (cwd / "pyproject.toml").read_text(encoding="utf-8")
            if "[tool.ruff" in pyproject:
                commands.append("ruff check .")
            if "[tool.mypy" in pyproject:
                commands.append("mypy .")
        return commands

    def _map_porcelain_status(self, status: str) -> FileChangeType:
        normalized = status.strip()
        if normalized == "??":
            return FileChangeType.UNTRACKED
        if "R" in normalized:
            return FileChangeType.RENAMED
        if "D" in normalized:
            return FileChangeType.DELETED
        if "A" in normalized:
            return FileChangeType.ADDED
        if "M" in normalized:
            return FileChangeType.MODIFIED
        return FileChangeType.UNKNOWN

    def _is_relative_to(self, candidate: Path, parent: Path) -> bool:
        try:
            candidate.relative_to(parent)
            return True
        except ValueError:
            return False
