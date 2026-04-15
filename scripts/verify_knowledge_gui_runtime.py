#!/usr/bin/env python3
"""Verify a generated noVNC/OpenClaw GUI runtime image."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
API_SRC = REPO_ROOT / "services" / "api-service"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from src.control_plane.knowledge_pool import load_knowledge_pool  # noqa: E402


ENVIRONMENT_SPECS_PATH = REPO_ROOT / "knowledge" / "coding-tools" / "environments" / "environment-specs.json"
VERIFICATION_REPORTS_PATH = REPO_ROOT / "knowledge" / "coding-tools" / "evidence" / "verification-reports.json"


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def _load_json_array(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_array(path: Path, records: list[dict]) -> None:
    path.write_text(json.dumps(records, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _mark_gui_environment_verified(gui) -> None:
    environment_refs = {gui.base_environment_ref, gui.gui_environment_ref}
    records = _load_json_array(ENVIRONMENT_SPECS_PATH)
    for record in records:
        payload = record.get("payload", {})
        environment_ref = f"artifact://environment-spec/{payload.get('environment_spec_id')}"
        if environment_ref in environment_refs:
            payload["gui_capability_state"] = "VERIFIED_CONTAINER_GUI"
            record["updated_at"] = datetime.now(UTC).isoformat()
    _write_json_array(ENVIRONMENT_SPECS_PATH, records)


def _mark_gui_report_pass(gui, gui_session_ref: str, detail: str) -> None:
    records = _load_json_array(VERIFICATION_REPORTS_PATH)
    for record in records:
        payload = record.get("payload", {})
        validated_refs = set(payload.get("validated_artifact_refs", []))
        if gui_session_ref not in validated_refs:
            continue
        payload.pop("blocking_findings", None)
        payload["created_at"] = datetime.now(UTC).isoformat()
        payload["gate_results"] = [
            {
                "artifact_ref": gui_session_ref,
                "detail": detail.strip() or "OK:container-gui-healthcheck",
                "gate_id": "container_gui_healthcheck",
                "gate_kind": "tests",
                "status": "PASS",
            }
        ]
        payload["outcome"] = "PASS"
        payload["reasons"] = [
            f"GUI session {gui.gui_session_spec_id} sibling container image built and passed the noVNC/Xvfb healthcheck on {gui.docker_platform}.",
            "Verification used the generated GUI session healthcheck command and did not rely on host desktop control.",
        ]
        payload["recommended_next_action"] = "accept_gui_session"
        record["updated_at"] = datetime.now(UTC).isoformat()
        break
    else:
        raise ValueError(f"No verification report found for {gui_session_ref}")
    _write_json_array(VERIFICATION_REPORTS_PATH, records)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gui-session-ref", required=True)
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Mark the linked GUI verification report and environment GUI state as passing when the healthcheck succeeds.",
    )
    args = parser.parse_args()

    catalog = load_knowledge_pool()
    artifact = catalog.gui_session_specs.get(args.gui_session_ref)
    if artifact is None:
        raise ValueError(f"Unknown GUI session ref: {args.gui_session_ref}")
    gui = artifact.payload

    docker_check = subprocess.run(
        ["which", "docker"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if docker_check.returncode != 0:
        raise RuntimeError("docker CLI is not available in this environment")

    artifact_dir = _resolve_path(gui.artifact_output_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    docker_cmd = [
        "docker",
        "run",
        "--rm",
        "--platform",
        gui.docker_platform,
        "-e",
        "NOVNC_PASSWORD=knowledge-gui-probe",
        "-e",
        f"KNOWLEDGE_GUI_SESSION_REF={args.gui_session_ref}",
        "-e",
        "KNOWLEDGE_GUI_ARTIFACT_DIR=/artifacts",
        "-v",
        f"{artifact_dir}:/artifacts",
        gui.docker_image,
        "/usr/local/bin/knowledge-gui-healthcheck",
    ]
    result = subprocess.run(
        docker_cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode == 0 and args.write_report:
        _mark_gui_report_pass(gui, args.gui_session_ref, result.stdout)
        _mark_gui_environment_verified(gui)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
