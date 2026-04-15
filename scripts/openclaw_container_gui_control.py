#!/usr/bin/env python3
"""Control a container noVNC desktop through OpenClaw's public browser CLI."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import shlex
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_ROOT = REPO_ROOT / ".cache" / "knowledge-runtime-logs"
OPENCLAW_GATEWAY_LOG = LOG_ROOT / "openclaw-gui-gateway.log"
OPENCLAW_GATEWAY_PID = LOG_ROOT / "openclaw-gui-gateway.pid"
DEFAULT_OPENCLAW_PROFILE = "dev"
DEFAULT_OPENCLAW_GATEWAY_PORT = "19001"


def _openclaw_cli() -> list[str]:
    env_cli = os.environ.get("OPENCLAW_CLI", "").strip()
    if env_cli:
        return shlex.split(env_cli)
    path_cli = shutil.which("openclaw")
    if path_cli:
        cli = [path_cli]
    else:
        local_bin = REPO_ROOT / "openclaw" / "packages" / "cli" / "dist" / "index.js"
        local_package = REPO_ROOT / "openclaw" / "dist" / "cli.js"
        if local_bin.exists():
            cli = ["node", str(local_bin)]
        elif local_package.exists():
            cli = ["node", str(local_package)]
        else:
            cli = ["openclaw"]
    profile = os.environ.get("OPENCLAW_GUI_PROFILE", DEFAULT_OPENCLAW_PROFILE).strip()
    if profile == "dev":
        return [*cli, "--dev"]
    if profile:
        return [*cli, "--profile", profile]
    return cli


def _gateway_command() -> list[str]:
    port = os.environ.get("OPENCLAW_GUI_GATEWAY_PORT", DEFAULT_OPENCLAW_GATEWAY_PORT).strip()
    return [
        *_openclaw_cli(),
        "gateway",
        "run",
        "--auth",
        "none",
        "--port",
        port,
        "--allow-unconfigured",
    ]


def _openclaw_env() -> dict[str, str]:
    env = dict(os.environ)
    if os.environ.get("OPENCLAW_CLI"):
        return env
    if env.get("OPENCLAW_GUI_PROFILE", DEFAULT_OPENCLAW_PROFILE).strip() == "dev":
        env.setdefault("OPENCLAW_GATEWAY_PORT", DEFAULT_OPENCLAW_GATEWAY_PORT)
    return env


def _probe_gateway() -> bool:
    try:
        result = subprocess.run(
            [*_openclaw_cli(), "browser", "--json", "status"],
            cwd=REPO_ROOT,
            env=_openclaw_env(),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def _pid_is_running(pid_path: Path) -> bool:
    if not pid_path.exists():
        return False
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
    except ValueError:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _ensure_gateway() -> dict[str, Any]:
    if _probe_gateway():
        return {"started": False, "ready": True, "log_path": str(OPENCLAW_GATEWAY_LOG)}

    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    if not _pid_is_running(OPENCLAW_GATEWAY_PID):
        with OPENCLAW_GATEWAY_LOG.open("a", encoding="utf-8") as log_handle:
            process = subprocess.Popen(
                _gateway_command(),
                cwd=REPO_ROOT,
                env=_openclaw_env(),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        OPENCLAW_GATEWAY_PID.write_text(f"{process.pid}\n", encoding="utf-8")

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if _probe_gateway():
            return {"started": True, "ready": True, "log_path": str(OPENCLAW_GATEWAY_LOG)}
        time.sleep(1)
    return {"started": True, "ready": False, "log_path": str(OPENCLAW_GATEWAY_LOG)}


def _expand_media_path(raw_path: str) -> Path:
    path = raw_path.strip()
    if path.startswith("~/"):
        return Path(path).expanduser()
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return (REPO_ROOT / candidate).resolve()


def _copy_screenshot_if_requested(result: dict[str, Any], output: str | None) -> None:
    if not output or int(result["returncode"]) != 0:
        return
    source: Path | None = None
    try:
        payload = json.loads(result["stdout"])
        if isinstance(payload, dict) and isinstance(payload.get("path"), str):
            source = _expand_media_path(payload["path"])
    except json.JSONDecodeError:
        media_match = re.search(r"MEDIA:(?P<path>.+)", result["stdout"])
        if media_match:
            source = _expand_media_path(media_match.group("path"))
    if source is None:
        result["postprocess_warning"] = "OpenClaw screenshot output did not include a media path."
        return
    destination = _expand_media_path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    result["copied_screenshot_to"] = str(destination)


def _run_openclaw(args: list[str], *, ensure_gateway: bool) -> dict[str, Any]:
    gateway: dict[str, Any] | None = None
    if ensure_gateway:
        gateway = _ensure_gateway()
        if not gateway.get("ready"):
            return {
                "command": [*_openclaw_cli(), "browser", *args],
                "returncode": 1,
                "stdout": "",
                "stderr": f"OpenClaw gateway was not ready; see {gateway.get('log_path')}",
                "gateway": gateway,
            }
    cmd = [*_openclaw_cli(), "browser", *args]
    try:
        result = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            env=_openclaw_env(),
            capture_output=True,
            text=True,
            timeout=int(os.environ.get("OPENCLAW_GUI_TIMEOUT_SECONDS", "60")),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "command": cmd,
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "OpenClaw browser command timed out.",
            "gateway": gateway,
        }
    return {
        "command": cmd,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "gateway": gateway,
    }


def _trace(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _action_args(action: str, payload: dict[str, Any]) -> list[str]:
    if action == "open":
        return ["open", str(payload["url"])]
    if action == "screenshot":
        target_id = str(payload.get("target_id") or "")
        if payload.get("output"):
            return ["--json", "screenshot", *([target_id] if target_id else [])]
        return ["screenshot", *([target_id] if target_id else [])]
    if action == "snapshot":
        args = ["snapshot"]
        if output := payload.get("output"):
            args.extend(["--out", str(output)])
        if target_id := payload.get("target_id"):
            args.extend(["--target-id", str(target_id)])
        return args
    if action == "click":
        args = ["click", str(payload["ref"])]
        if target_id := payload.get("target_id"):
            args.extend(["--target-id", str(target_id)])
        return args
    if action == "type":
        args = ["type", str(payload["ref"]), str(payload.get("text", ""))]
        if target_id := payload.get("target_id"):
            args.extend(["--target-id", str(target_id)])
        return args
    if action == "press":
        args = ["press", str(payload["key"])]
        if target_id := payload.get("target_id"):
            args.extend(["--target-id", str(target_id)])
        return args
    if action == "wait":
        args = ["wait"]
        if text := payload.get("text"):
            args.extend(["--text", str(text)])
        if time_ms := payload.get("time_ms"):
            args.extend(["--time", str(time_ms)])
        if url := payload.get("url"):
            args.extend(["--url", str(url)])
        if load := payload.get("load"):
            args.extend(["--load", str(load)])
        return args
    raise ValueError(f"Unsupported OpenClaw browser action: {action}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", required=True)
    parser.add_argument("--payload-json", default="{}")
    parser.add_argument("--trace-path")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.payload_json)
    trace_path = Path(args.trace_path) if args.trace_path else None
    started_at = datetime.now(UTC).isoformat()
    command_args = _action_args(args.action, payload)
    if args.dry_run:
        result = {
            "command": [*_openclaw_cli(), "browser", *command_args],
            "returncode": 0,
            "stdout": "",
            "stderr": "",
        }
    else:
        result = _run_openclaw(command_args, ensure_gateway=args.action != "help")
        if args.action == "screenshot":
            _copy_screenshot_if_requested(result, payload.get("output"))
    trace = {
        "action": args.action,
        "payload": payload,
        "provider": "openclaw_browser",
        "started_at": started_at,
        "completed_at": datetime.now(UTC).isoformat(),
        "result": result,
    }
    _trace(trace_path, trace)
    print(json.dumps(trace, sort_keys=True))
    return int(result["returncode"])


if __name__ == "__main__":
    raise SystemExit(main())
