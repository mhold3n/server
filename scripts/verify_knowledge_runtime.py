#!/usr/bin/env python3
"""Run a knowledge-runtime health check from a checked-in environment spec."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
API_SRC = REPO_ROOT / "services" / "api-service"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from src.control_plane.knowledge_pool import load_knowledge_pool  # noqa: E402


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment-ref", required=True)
    parser.add_argument("--imports", nargs="*", default=[])
    parser.add_argument("--dotnet-probe", action="store_true")
    parser.add_argument("--container-command", nargs=argparse.REMAINDER, default=[])
    parser.add_argument("--host-command")
    args = parser.parse_args()

    catalog = load_knowledge_pool()
    artifact = catalog.environment_specs.get(args.environment_ref)
    if artifact is None:
        raise ValueError(f"Unknown environment ref: {args.environment_ref}")
    environment = artifact.payload

    if environment.delivery_kind == "uv_venv":
        env_dir = _resolve_path(environment.runtime_locator)
        python_bin = env_dir / "bin" / "python"
        if not python_bin.exists():
            raise RuntimeError(f"Runtime python not found: {python_bin}")
        imports = args.imports or environment.module_ids
        code = [
            "import importlib",
            "import sys",
            "targets = sys.argv[1:]",
            "for target in targets:",
            "    importlib.import_module(target)",
            "print('OK:' + ','.join(targets))",
        ]
        result = subprocess.run(
            [str(python_bin), "-c", "\n".join(code), *imports],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        return result.returncode

    if environment.delivery_kind == "dotnet_toolchain":
        project_path = _resolve_path(environment.manifest_path)
        env = dict(os.environ)
        env.setdefault("DOTNET_ROLL_FORWARD", "Major")
        result = subprocess.run(
            ["dotnet", "run", "--project", str(project_path), "-c", "Release"],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        return result.returncode

    if environment.delivery_kind == "host_app":
        launcher_path = _resolve_path(environment.launcher_ref)
        if not launcher_path.exists():
            raise RuntimeError(f"Host application launcher not found: {launcher_path}")
        host_command = args.host_command or f'"{launcher_path}" --version'
        result = subprocess.run(
            host_command,
            cwd=REPO_ROOT,
            shell=True,
            text=True,
            capture_output=True,
            check=False,
        )
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        return result.returncode

    docker_bin = subprocess.run(
        ["which", "docker"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if docker_bin.returncode != 0:
        raise RuntimeError("docker CLI is not available in this environment")
    container_command = args.container_command or ["python", "--version"]
    docker_cmd = ["docker", "run", "--rm"]
    if environment.docker_platform:
        docker_cmd.extend(["--platform", environment.docker_platform])
    docker_cmd.extend([environment.runtime_locator, *container_command])
    result = subprocess.run(
        docker_cmd,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
