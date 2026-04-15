#!/usr/bin/env python3
"""Launch a container GUI session and optionally probe it through OpenClaw browser control."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
API_SRC = REPO_ROOT / "services" / "api-service"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from src.control_plane.knowledge_pool import load_knowledge_pool  # noqa: E402


def _openclaw_target_id(stdout: str) -> str | None:
    try:
        trace = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    result = trace.get("result") if isinstance(trace, dict) else None
    nested_stdout = result.get("stdout") if isinstance(result, dict) else None
    if not isinstance(nested_stdout, str):
        return None
    match = re.search(r"^id:\s*(?P<target_id>[0-9A-Fa-f]+)\s*$", nested_stdout, re.MULTILINE)
    return match.group("target_id") if match else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-ref", required=True)
    parser.add_argument("--allow-unverified", action="store_true")
    parser.add_argument("--openclaw", action="store_true")
    parser.add_argument("--keep-open", action="store_true")
    args = parser.parse_args()

    catalog = load_knowledge_pool()
    gui = catalog.resolve_gui_session(args.target_ref, {"verified_only": not args.allow_unverified})
    gui_ref = f"artifact://gui-session-spec/{gui.gui_session_spec_id}"
    handle = catalog.launch_gui_session(gui_ref, {})
    try:
        time.sleep(2)
        result: dict[str, object] = {
            "gui_session_ref": gui_ref,
            "url": handle.url,
            "container_id": handle.container_id,
            "artifact_output_dir": handle.artifact_output_dir,
        }
        if args.openclaw:
            artifact_dir = Path(handle.artifact_output_dir)
            trace_path = artifact_dir / "openclaw-open.json"
            open_result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "openclaw_container_gui_control.py"),
                    "--action",
                    "open",
                    "--payload-json",
                    json.dumps({"url": handle.url}),
                    "--trace-path",
                    str(trace_path),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            result["openclaw_returncode"] = open_result.returncode
            result["openclaw_stdout"] = open_result.stdout
            result["openclaw_stderr"] = open_result.stderr
            if open_result.returncode != 0:
                print(json.dumps(result, indent=2, sort_keys=True))
                return open_result.returncode
            target_id = _openclaw_target_id(open_result.stdout)
            if target_id:
                result["openclaw_target_id"] = target_id
                preconnect_snapshot_path = artifact_dir / "openclaw-preconnect-snapshot.txt"
                preconnect_trace_path = artifact_dir / "openclaw-preconnect-snapshot.json"
                preconnect_result = subprocess.run(
                    [
                        sys.executable,
                        str(REPO_ROOT / "scripts" / "openclaw_container_gui_control.py"),
                        "--action",
                        "snapshot",
                        "--payload-json",
                        json.dumps({"output": str(preconnect_snapshot_path), "target_id": target_id}),
                        "--trace-path",
                        str(preconnect_trace_path),
                    ],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                result["openclaw_preconnect_snapshot_returncode"] = preconnect_result.returncode
                result["openclaw_preconnect_snapshot_stdout"] = preconnect_result.stdout
                result["openclaw_preconnect_snapshot_stderr"] = preconnect_result.stderr
                gui_action_trace_path = artifact_dir / "openclaw-gui-action-press.json"
                gui_action_result = subprocess.run(
                    [
                        sys.executable,
                        str(REPO_ROOT / "scripts" / "openclaw_container_gui_control.py"),
                        "--action",
                        "press",
                        "--payload-json",
                        json.dumps({"key": "Tab", "target_id": target_id}),
                        "--trace-path",
                        str(gui_action_trace_path),
                    ],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                result["openclaw_gui_action_returncode"] = gui_action_result.returncode
                result["openclaw_gui_action_stdout"] = gui_action_result.stdout
                result["openclaw_gui_action_stderr"] = gui_action_result.stderr
                if gui_action_result.returncode != 0:
                    print(json.dumps(result, indent=2, sort_keys=True))
                    return gui_action_result.returncode
            time.sleep(2)
            screenshot_path = artifact_dir / "openclaw-novnc-screenshot.png"
            screenshot_trace_path = artifact_dir / "openclaw-screenshot.json"
            screenshot_payload = {"output": str(screenshot_path)}
            if target_id:
                screenshot_payload["target_id"] = target_id
            screenshot_result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "openclaw_container_gui_control.py"),
                    "--action",
                    "screenshot",
                    "--payload-json",
                    json.dumps(screenshot_payload),
                    "--trace-path",
                    str(screenshot_trace_path),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            result["openclaw_screenshot_returncode"] = screenshot_result.returncode
            result["openclaw_screenshot_stdout"] = screenshot_result.stdout
            result["openclaw_screenshot_stderr"] = screenshot_result.stderr
            if screenshot_result.returncode != 0:
                fallback_path = artifact_dir / "container-display-fallback.png"
                fallback_result = subprocess.run(
                    [
                        "docker",
                        "exec",
                        handle.container_id,
                        "sh",
                        "-lc",
                        f"scrot /artifacts/{fallback_path.name}",
                    ],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                result["container_display_fallback_returncode"] = fallback_result.returncode
                result["container_display_fallback_stdout"] = fallback_result.stdout
                result["container_display_fallback_stderr"] = fallback_result.stderr
                if fallback_result.returncode != 0:
                    print(json.dumps(result, indent=2, sort_keys=True))
                    return screenshot_result.returncode
                result["openclaw_screenshot_warning"] = (
                    "OpenClaw browser screenshot failed; captured the container display with scrot instead."
                )

            snapshot_path = artifact_dir / "openclaw-novnc-snapshot.txt"
            snapshot_trace_path = artifact_dir / "openclaw-snapshot.json"
            snapshot_payload = {"output": str(snapshot_path)}
            if target_id:
                snapshot_payload["target_id"] = target_id
            snapshot_result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "openclaw_container_gui_control.py"),
                    "--action",
                    "snapshot",
                    "--payload-json",
                    json.dumps(snapshot_payload),
                    "--trace-path",
                    str(snapshot_trace_path),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            result["openclaw_snapshot_returncode"] = snapshot_result.returncode
            result["openclaw_snapshot_stdout"] = snapshot_result.stdout
            result["openclaw_snapshot_stderr"] = snapshot_result.stderr
            if snapshot_result.returncode != 0:
                print(json.dumps(result, indent=2, sort_keys=True))
                return snapshot_result.returncode
            result["openclaw_artifacts"] = [
                str(trace_path),
                str(artifact_dir / "openclaw-preconnect-snapshot.txt"),
                str(artifact_dir / "openclaw-preconnect-snapshot.json"),
                str(artifact_dir / "openclaw-gui-action-press.json"),
                str(screenshot_trace_path),
                str(snapshot_path),
                str(snapshot_trace_path),
            ]
            if "openclaw_screenshot_warning" in result:
                result["openclaw_artifacts"].append(
                    str(artifact_dir / "container-display-fallback.png")
                )
            else:
                result["openclaw_artifacts"].append(str(screenshot_path))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    finally:
        if not args.keep_open:
            catalog.close_gui_session(handle.container_id)


if __name__ == "__main__":
    raise SystemExit(main())
