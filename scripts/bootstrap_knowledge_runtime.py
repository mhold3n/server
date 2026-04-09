#!/usr/bin/env python3
"""Bootstrap a knowledge-runtime environment from a checked-in environment spec."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
API_SRC = REPO_ROOT / "services" / "api"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from src.control_plane.knowledge_pool import load_knowledge_pool, resolve_runtime  # noqa: E402


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment-ref", help="artifact://environment-spec/... ref")
    parser.add_argument("--module-ref", help="artifact://knowledge-pack/... or adapter ref")
    parser.add_argument(
        "--python-bin",
        default="python3.11",
        help="Python interpreter used when creating uv environments.",
    )
    args = parser.parse_args()

    if not args.environment_ref and not args.module_ref:
        parser.error("one of --environment-ref or --module-ref is required")

    catalog = load_knowledge_pool()
    if args.environment_ref:
        artifact = catalog.environment_specs.get(args.environment_ref)
        if artifact is None:
            raise ValueError(f"Unknown environment ref: {args.environment_ref}")
        environment = artifact.payload
    else:
        environment = resolve_runtime(
            args.module_ref,
            host_profile={"preferred_delivery_kinds": ["uv_venv", "dotnet_toolchain", "host_app", "docker_image"], "verified_only": False},
        )

    manifest_path = _resolve_path(environment.manifest_path)
    if environment.delivery_kind == "uv_venv":
        env_dir = _resolve_path(environment.runtime_locator)
        env_dir.parent.mkdir(parents=True, exist_ok=True)
        _run(["uv", "venv", "--clear", "--python", args.python_bin, str(env_dir)])
        _run(["uv", "pip", "install", "--python", str(env_dir / "bin" / "python"), "-r", str(manifest_path)])
        print(f"Bootstrapped uv runtime at {env_dir}")
        return 0

    if environment.delivery_kind == "dotnet_toolchain":
        _run(["dotnet", "restore", str(manifest_path)])
        _run(["dotnet", "build", str(manifest_path), "-c", "Release"])
        print(f"Bootstrapped dotnet runtime from {manifest_path}")
        return 0

    if environment.delivery_kind == "host_app":
        runtime_path = _resolve_path(environment.runtime_locator)
        launcher_path = _resolve_path(environment.launcher_ref)
        if not runtime_path.exists():
            raise RuntimeError(f"Host application runtime not found: {runtime_path}")
        if not launcher_path.exists():
            raise RuntimeError(f"Host application launcher not found: {launcher_path}")
        print(f"Verified host application runtime at {runtime_path}")
        return 0

    docker_bin = subprocess.run(
        ["which", "docker"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if docker_bin.returncode != 0:
        raise RuntimeError("docker CLI is not available in this environment")
    _run(["docker", "build", "-f", str(manifest_path), "-t", environment.runtime_locator, str(REPO_ROOT)])
    print(f"Built docker runtime {environment.runtime_locator}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
