from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import settings
from ..devplane.models import ArtifactRecord, RunEventRequest
from .devplane import get_service

router = APIRouter(prefix="/api/automation", tags=["Automation"])

MAX_STDOUT_CHARS = 8_000
MAX_STDERR_CHARS = 8_000


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "...(truncated)"


def _ensure_under_devplane_root(path: str) -> str:
    root = Path(settings.devplane_root).resolve()
    target = Path(path).expanduser().resolve()
    if target == root:
        return str(target)
    if not str(target).startswith(str(root) + str(Path("/"))):
        # cross-platform-ish prefix check: use Path separator normalization
        if not str(target).startswith(str(root) + "/"):
            raise HTTPException(status_code=400, detail="path must be under devplane_root")
    return str(target)


def _run_command(cmd: list[str], *, timeout_s: float = 3600.0) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=504,
            detail={"error": "command timed out", "command": cmd, "stderr": str(exc)},
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "failed to execute command", "command": cmd, "stderr": str(exc)},
        ) from exc

    return {
        "returncode": int(proc.returncode),
        "stdout": _clip(proc.stdout or "", MAX_STDOUT_CHARS),
        "stderr": _clip(proc.stderr or "", MAX_STDERR_CHARS),
        "command": cmd,
    }


def _write_workspace_artifact(
    *,
    workspace_root: str,
    name: str,
    payload: dict[str, Any],
) -> ArtifactRecord:
    root = Path(_ensure_under_devplane_root(workspace_root)).resolve()
    out_dir = root / ".birtha" / "automation"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{name}.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return ArtifactRecord(
        name=name,
        path=str(out_path),
        kind="automation_result",
        description="Automation output artifact captured by the control plane",
    )


def _attach_artifact_to_run(*, run_id: str | None, artifact: ArtifactRecord) -> None:
    if not run_id:
        return
    svc = get_service()
    svc.append_run_event(
        run_id,
        RunEventRequest(
            message=f"Captured automation artifact: {artifact.name}",
            artifacts=[artifact],
        ),
    )


class MartyMediaCaptionsRequest(BaseModel):
    input_path: str = Field(..., description="Media file path (must be under devplane_root)")
    output_dir: str = Field(..., description="Output directory (must be under devplane_root)")
    workspace_root: str = Field(..., description="Workspace root (must be under devplane_root)")
    run_id: str | None = Field(default=None, description="Optional devplane run id to attach artifacts to")
    language: str = Field(..., pattern="^(en|es)$")
    model: str | None = None


@router.post("/martymedia/captions")
async def martymedia_captions(req: MartyMediaCaptionsRequest) -> dict[str, Any]:
    input_path = _ensure_under_devplane_root(req.input_path)
    output_dir = _ensure_under_devplane_root(req.output_dir)
    workspace_root = _ensure_under_devplane_root(req.workspace_root)

    cmd = [
        "martymedia-whisper",
        "--input",
        input_path,
        "--output-dir",
        output_dir,
        "--language",
        req.language,
    ]
    if req.model:
        cmd.extend(["--model", req.model])

    result = _run_command(cmd, timeout_s=6 * 60 * 60)
    ok = result["returncode"] == 0
    if not ok:
        raise HTTPException(status_code=502, detail={"ok": False, **result})
    # Try to parse martymedia JSON response.
    try:
        parsed = json.loads(result["stdout"])
    except Exception:
        parsed = None
    artifact = _write_workspace_artifact(
        workspace_root=workspace_root,
        name="martymedia_captions",
        payload={"ok": True, "result": parsed, **result},
    )
    _attach_artifact_to_run(run_id=req.run_id, artifact=artifact)
    return {"ok": True, "result": parsed, "artifact": artifact.model_dump(mode="json"), **result}


class LarrakDoctorRequest(BaseModel):
    skip_services: bool = False
    workspace_root: str | None = Field(default=None, description="Optional workspace root for artifacts")
    run_id: str | None = Field(default=None, description="Optional devplane run id to attach artifacts to")


@router.post("/larrak/doctor")
async def larrak_doctor(req: LarrakDoctorRequest) -> dict[str, Any]:
    cmd = ["larrak-audio", "doctor"]
    if req.skip_services:
        cmd.append("--skip-services")
    result = _run_command(cmd, timeout_s=120.0)
    ok = result["returncode"] == 0
    if not ok:
        raise HTTPException(status_code=502, detail={"ok": False, **result})
    if req.workspace_root:
        artifact = _write_workspace_artifact(
            workspace_root=req.workspace_root,
            name="larrak_doctor",
            payload={"ok": True, **result},
        )
        _attach_artifact_to_run(run_id=req.run_id, artifact=artifact)
        return {"ok": True, "artifact": artifact.model_dump(mode="json"), **result}
    return {"ok": True, **result}


class LarrakIngestRequest(BaseModel):
    source_path: str = Field(..., description="Source file path (must be under devplane_root)")
    source_type: str | None = Field(default=None, description="pdf|md|txt (optional)")
    marker_extra_args: list[str] = Field(default_factory=list)
    workspace_root: str = Field(..., description="Workspace root (must be under devplane_root)")
    run_id: str | None = Field(default=None, description="Optional devplane run id to attach artifacts to")


@router.post("/larrak/ingest")
async def larrak_ingest(req: LarrakIngestRequest) -> dict[str, Any]:
    source_path = _ensure_under_devplane_root(req.source_path)
    workspace_root = _ensure_under_devplane_root(req.workspace_root)
    cmd = ["larrak-audio", "ingest", "--source", source_path]
    if req.source_type:
        cmd.extend(["--type", req.source_type])
    for arg in req.marker_extra_args:
        cmd.extend(["--marker-extra-arg", arg])
    result = _run_command(cmd, timeout_s=6 * 60 * 60)
    ok = result["returncode"] == 0
    if not ok:
        raise HTTPException(status_code=502, detail={"ok": False, **result})
    artifact = _write_workspace_artifact(
        workspace_root=workspace_root,
        name="larrak_ingest",
        payload={"ok": True, **result},
    )
    _attach_artifact_to_run(run_id=req.run_id, artifact=artifact)
    return {"ok": True, "artifact": artifact.model_dump(mode="json"), **result}


class LarrakBuildRequest(BaseModel):
    source_id: str
    enhance: bool = True
    workspace_root: str = Field(..., description="Workspace root (must be under devplane_root)")
    run_id: str | None = Field(default=None, description="Optional devplane run id to attach artifacts to")


@router.post("/larrak/build")
async def larrak_build(req: LarrakBuildRequest) -> dict[str, Any]:
    workspace_root = _ensure_under_devplane_root(req.workspace_root)
    cmd = ["larrak-audio", "build", "--source-id", req.source_id, "--enhance", "on" if req.enhance else "off"]
    result = _run_command(cmd, timeout_s=6 * 60 * 60)
    ok = result["returncode"] == 0
    if not ok:
        raise HTTPException(status_code=502, detail={"ok": False, **result})
    artifact = _write_workspace_artifact(
        workspace_root=workspace_root,
        name="larrak_build",
        payload={"ok": True, **result},
    )
    _attach_artifact_to_run(run_id=req.run_id, artifact=artifact)
    return {"ok": True, "artifact": artifact.model_dump(mode="json"), **result}


class LarrakRunTestFilesRequest(BaseModel):
    input_dir: str = Field(..., description="Directory path (must be under devplane_root)")
    glob: str = "*.pdf"
    recursive: bool = False
    enhance: bool = True
    marker_extra_args: list[str] = Field(default_factory=list)
    summary_path: str | None = Field(default=None, description="Optional path (must be under devplane_root)")
    workspace_root: str = Field(..., description="Workspace root (must be under devplane_root)")
    run_id: str | None = Field(default=None, description="Optional devplane run id to attach artifacts to")


@router.post("/larrak/run-test-files")
async def larrak_run_test_files(req: LarrakRunTestFilesRequest) -> dict[str, Any]:
    input_dir = _ensure_under_devplane_root(req.input_dir)
    workspace_root = _ensure_under_devplane_root(req.workspace_root)
    cmd = ["larrak-audio", "run-test-files", "--input-dir", input_dir, "--glob", req.glob, "--enhance", "on" if req.enhance else "off"]
    if req.recursive:
        cmd.append("--recursive")
    for arg in req.marker_extra_args:
        cmd.extend(["--marker-extra-arg", arg])
    if req.summary_path:
        cmd.extend(["--summary-path", _ensure_under_devplane_root(req.summary_path)])
    result = _run_command(cmd, timeout_s=6 * 60 * 60)
    ok = result["returncode"] == 0
    if not ok:
        raise HTTPException(status_code=502, detail={"ok": False, **result})
    artifact = _write_workspace_artifact(
        workspace_root=workspace_root,
        name="larrak_run_test_files",
        payload={"ok": True, **result},
    )
    _attach_artifact_to_run(run_id=req.run_id, artifact=artifact)
    return {"ok": True, "artifact": artifact.model_dump(mode="json"), **result}

