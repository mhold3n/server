#!/usr/bin/env python3
"""JSON CLI for resolving, launching, verifying, and closing container GUI sessions."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
API_SRC = REPO_ROOT / "services" / "api-service"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from src.control_plane.knowledge_pool import load_knowledge_pool  # noqa: E402


def _emit(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    resolve_p = sub.add_parser("resolve")
    resolve_p.add_argument("--target-ref", required=True)
    resolve_p.add_argument("--allow-unverified", action="store_true")

    launch_p = sub.add_parser("launch")
    launch_p.add_argument("--target-ref", required=True)
    launch_p.add_argument("--allow-unverified", action="store_true")
    launch_p.add_argument("--novnc-port", type=int)
    launch_p.add_argument("--artifact-output-dir")

    verify_p = sub.add_parser("verify")
    verify_p.add_argument("--gui-session-ref", required=True)

    close_p = sub.add_parser("close")
    close_p.add_argument("--container", required=True)

    artifacts_p = sub.add_parser("artifacts")
    artifacts_p.add_argument("--gui-session-ref", required=True)

    args = parser.parse_args()
    catalog = load_knowledge_pool()

    if args.command == "resolve":
        gui = catalog.resolve_gui_session(
            args.target_ref,
            {"verified_only": not args.allow_unverified},
        )
        _emit(gui.model_dump(mode="json"))
        return 0

    if args.command == "launch":
        gui = catalog.resolve_gui_session(
            args.target_ref,
            {"verified_only": not args.allow_unverified},
        )
        launch_profile: dict[str, object] = {}
        if args.novnc_port:
            launch_profile["novnc_port"] = args.novnc_port
        if args.artifact_output_dir:
            launch_profile["artifact_output_dir"] = args.artifact_output_dir
        handle = catalog.launch_gui_session(
            f"artifact://gui-session-spec/{gui.gui_session_spec_id}",
            launch_profile,
        )
        _emit(handle.__dict__)
        return 0

    if args.command == "verify":
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "verify_knowledge_gui_runtime.py"),
                "--gui-session-ref",
                args.gui_session_ref,
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        _emit(
            {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        return result.returncode

    if args.command == "close":
        catalog.close_gui_session(args.container)
        _emit({"closed": args.container})
        return 0

    if args.command == "artifacts":
        artifact = catalog.gui_session_specs.get(args.gui_session_ref)
        if artifact is None:
            raise ValueError(f"Unknown GUI session ref: {args.gui_session_ref}")
        payload = artifact.payload
        path = Path(payload.artifact_output_dir)
        artifact_dir = path if path.is_absolute() else (REPO_ROOT / path).resolve()
        files = sorted(str(item) for item in artifact_dir.rglob("*") if item.is_file()) if artifact_dir.exists() else []
        _emit({"artifact_output_dir": str(artifact_dir), "files": files})
        return 0

    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
