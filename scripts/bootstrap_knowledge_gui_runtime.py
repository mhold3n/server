#!/usr/bin/env python3
"""Build a generated noVNC/OpenClaw sibling GUI runtime."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
API_SRC = REPO_ROOT / "services" / "api-service"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from src.control_plane.knowledge_pool import load_knowledge_pool  # noqa: E402


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gui-session-ref", required=True)
    parser.add_argument(
        "--skip-base",
        action="store_true",
        help="Do not bootstrap the linked base CLI/runtime environment before building the GUI image.",
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

    if not args.skip_base:
        _run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "bootstrap_knowledge_runtime.py"),
                "--environment-ref",
                gui.base_environment_ref,
            ]
        )

    gui_base_manifest = REPO_ROOT / "knowledge" / "coding-tools" / "runtime" / "docker" / "gui" / "base.Dockerfile"
    if gui_base_manifest.exists():
        _run(
            [
                "docker",
                "build",
                "--platform",
                gui.docker_platform,
                "-f",
                str(gui_base_manifest),
                "-t",
                "birtha/knowledge-gui-base:1.0.0",
                str(REPO_ROOT),
            ]
        )

    manifest = _resolve_path(gui.manifest_path)
    _run(
        [
            "docker",
            "build",
            "--platform",
            gui.docker_platform,
            "-f",
            str(manifest),
            "-t",
            gui.docker_image,
            str(REPO_ROOT),
        ]
    )
    print(f"Built GUI runtime {gui.docker_image} for {args.gui_session_ref}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
