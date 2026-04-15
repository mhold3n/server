#!/usr/bin/env python3
"""Validate the active Docker topology without starting containers.

Uses ``docker compose --project-directory <repo root>`` so build contexts and
``${COMPOSE_DATA_ROOT:-.docker-data}/...`` binds match Makefile / CI behavior.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

COMPOSE_COMBINATIONS: dict[str, list[str]] = {
    "full-dev": [
        "docker-compose.yml",
        "docker/compose-profiles/docker-compose.platform.yml",
        "docker/compose-profiles/docker-compose.ai.yml",
        "docker/compose-profiles/docker-compose.local-ai.yml",
    ],
    "ci": ["docker/compose-profiles/docker-compose.ci.yml"],
    "worker": ["docker/compose-profiles/docker-compose.worker.yml"],
    "server": [
        "docker-compose.yml",
        "docker/compose-profiles/docker-compose.platform.yml",
        "docker/compose-profiles/docker-compose.ai.yml",
        "docker/compose-profiles/docker-compose.server.yml",
    ],
}

MISSING_BIND_PREFIXES = (
    ".cache/",
    ".docker-data/",
    "data/",
    "logs",
    "plugins",
)

PINNED_RUNTIME_IMAGES = ("vllm/vllm-openai", "ollama/ollama")


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)


def _compose_args(files: list[str]) -> list[str]:
    args = ["docker", "compose", "--project-directory", str(ROOT)]
    for file in files:
        args.extend(["-f", file])
    return args


def _fail(message: str) -> None:
    print(f"Docker topology validation failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def _require_compose_config(name: str, files: list[str]) -> dict[str, Any]:
    quiet = _run([*_compose_args(files), "config", "--quiet"])
    if quiet.returncode != 0:
        _fail(f"{name} compose config is invalid:\n{quiet.stderr.strip() or quiet.stdout.strip()}")

    rendered = _run([*_compose_args(files), "config", "--format", "json"])
    if rendered.returncode != 0:
        _fail(f"{name} compose JSON render failed:\n{rendered.stderr.strip() or rendered.stdout.strip()}")
    return json.loads(rendered.stdout)


def _is_allowed_missing_bind(source: Path) -> bool:
    try:
        rel = source.relative_to(ROOT).as_posix()
    except ValueError:
        return True
    return rel.startswith(MISSING_BIND_PREFIXES)


def _validate_build(name: str, service: str, build: Any) -> None:
    if not build:
        return
    if isinstance(build, str):
        context = Path(build)
        dockerfile = "Dockerfile"
    else:
        context = Path(str(build.get("context", ".")))
        dockerfile = str(build.get("dockerfile", "Dockerfile"))
    context = context if context.is_absolute() else (ROOT / context)
    dockerfile_path = Path(dockerfile)
    if not dockerfile_path.is_absolute():
        dockerfile_path = context / dockerfile
    if not context.exists():
        _fail(f"{name}/{service} build context is missing: {context}")
    if not dockerfile_path.exists():
        _fail(f"{name}/{service} Dockerfile is missing: {dockerfile_path}")


def _validate_volumes(name: str, service: str, volumes: list[dict[str, Any]]) -> None:
    for volume in volumes:
        if volume.get("type") != "bind":
            continue
        source_raw = volume.get("source")
        if not source_raw:
            continue
        source = Path(str(source_raw))
        if not source.exists() and not _is_allowed_missing_bind(source):
            _fail(f"{name}/{service} bind source is missing: {source}")


def _validate_runtime_image(name: str, service: str, image: str | None) -> None:
    if not image:
        return
    for runtime_image in PINNED_RUNTIME_IMAGES:
        if runtime_image in image and "@sha256:" not in image:
            _fail(f"{name}/{service} references {runtime_image} without a sha256 digest")


def _validate_rendered_config(name: str, rendered: dict[str, Any]) -> None:
    services = rendered.get("services", {})
    if not isinstance(services, dict):
        _fail(f"{name} rendered config has no services map")
    for service_name, service in services.items():
        if not isinstance(service, dict):
            continue
        _validate_build(name, service_name, service.get("build"))
        _validate_volumes(name, service_name, list(service.get("volumes", []) or []))
        _validate_runtime_image(name, service_name, service.get("image"))


def main() -> int:
    if _run(["docker", "compose", "version"]).returncode != 0:
        _fail("docker compose is not available")

    for name, files in COMPOSE_COMBINATIONS.items():
        rendered = _require_compose_config(name, files)
        _validate_rendered_config(name, rendered)
        print(f"OK: {name}")

    print("Docker topology validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
