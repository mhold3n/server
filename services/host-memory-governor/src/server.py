"""
Host Memory Governor (macOS).

This module is designed for other agents/operators:
- It runs outside Docker (ideally via launchd).
- It exposes a tiny HTTP API to report memory pressure and a safe optional headroom budget.
- It never kills processes. It only reports and recommends.

The orchestrator uses this service to decide whether it is safe to allow Ollama to load
and to scale up its effective footprint as memory becomes available.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse


def _run(cmd: List[str], timeout_s: float = 2.0) -> Tuple[int, str, str]:
    """Run a command and return (exit_code, stdout, stderr)."""
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _sysctl_int(key: str) -> Optional[int]:
    code, out, _ = _run(["sysctl", "-n", key])
    if code != 0:
        return None
    try:
        return int(out.strip())
    except ValueError:
        return None


def _vm_stat_pages() -> Tuple[Optional[int], Dict[str, int]]:
    """
    Parse `vm_stat` output into a page size and a dict of counters (in pages).
    """
    code, out, _ = _run(["vm_stat"])
    if code != 0:
        return None, {}

    page_size = None
    counters: Dict[str, int] = {}
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("Mach Virtual Memory Statistics:"):
            continue
        if "page size of" in line and "bytes" in line:
            # Example: "Mach Virtual Memory Statistics: (page size of 16384 bytes)"
            try:
                page_size = int(line.split("page size of", 1)[1].split("bytes", 1)[0].strip())
            except Exception:
                page_size = None
            continue
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        key = key.strip().lower().replace(" ", "_")
        value_str = rest.strip().strip(".")
        value_str = value_str.replace(".", "").replace(",", "")
        try:
            counters[key] = int(value_str)
        except ValueError:
            continue

    return page_size, counters


def _memory_pressure_level() -> Dict[str, Any]:
    """
    Best-effort memory pressure: uses `memory_pressure -Q` on macOS.
    """
    code, out, err = _run(["memory_pressure", "-Q"], timeout_s=2.0)
    if code != 0:
        return {"available": False, "error": err.strip() or "memory_pressure_failed"}

    # Output varies by macOS version; we normalize to a coarse level.
    normalized = "unknown"
    raw = out.strip()
    lowered = raw.lower()
    if "critical" in lowered:
        normalized = "critical"
    elif "warn" in lowered or "warning" in lowered:
        normalized = "warn"
    elif "normal" in lowered or "ok" in lowered:
        normalized = "normal"

    return {"available": True, "normalized": normalized, "raw": raw}


def _list_top_processes(limit: int) -> List[Dict[str, Any]]:
    """
    Return top processes by RSS (resident size), best-effort classification only.

    Classification intent:
    - `is_apple_native`: heuristic based on executable path prefix.
    - `is_docker_related`: heuristic based on process name/path.
    """
    # rss is in KB
    code, out, _ = _run(["ps", "-axo", "pid=,rss=,comm="], timeout_s=3.0)
    if code != 0:
        return []

    rows: List[Tuple[int, int, str]] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if len(parts) != 3:
            continue
        try:
            pid = int(parts[0])
            rss_kb = int(parts[1])
        except ValueError:
            continue
        comm = parts[2]
        rows.append((pid, rss_kb, comm))

    rows.sort(key=lambda r: r[1], reverse=True)
    rows = rows[: max(0, limit)]

    results: List[Dict[str, Any]] = []
    for pid, rss_kb, comm in rows:
        path = comm
        lowered = path.lower()
        is_apple_native = path.startswith("/System/") or path.startswith("/usr/libexec/") or path.startswith(
            "/usr/sbin/"
        )
        is_docker_related = ("docker" in lowered) or ("com.docker" in lowered)
        results.append(
            {
                "pid": pid,
                "rss_bytes": rss_kb * 1024,
                "comm": comm,
                "is_apple_native": is_apple_native,
                "is_non_apple": not is_apple_native,
                "is_docker_related": is_docker_related,
            }
        )
    return results


@dataclass(frozen=True)
class Policy:
    """
    The policy encodes 'essential' constraints into measurable thresholds.

    Values are conservative defaults for 32GB unified memory machines.
    """

    min_free_floor_bytes: int
    min_protected_bytes: int
    critical_pressure_disallow: bool
    warn_pressure_disallow: bool


DEFAULT_POLICY = Policy(
    min_free_floor_bytes=3 * 1024**3,  # keep at least ~3GB free-ish
    min_protected_bytes=12 * 1024**3,  # protect at least ~12GB for essential OS stability
    critical_pressure_disallow=True,
    warn_pressure_disallow=True,
)


def _compute_budget(policy: Policy) -> Dict[str, Any]:
    total = _sysctl_int("hw.memsize") or 0
    page_size, pages = _vm_stat_pages()

    # Best-effort 'available': free + inactive - speculative (macOS nuance).
    free_pages = pages.get("pages_free", 0)
    inactive_pages = pages.get("pages_inactive", 0)
    speculative_pages = pages.get("pages_speculative", 0)
    compressed_pages = pages.get("pages_stored_in_compressor", 0)
    wired_pages = pages.get("pages_wired_down", 0)

    if page_size:
        free_bytes = free_pages * page_size
        inactive_bytes = inactive_pages * page_size
        speculative_bytes = speculative_pages * page_size
        wired_bytes = wired_pages * page_size
        compressed_bytes = compressed_pages * page_size
    else:
        free_bytes = 0
        inactive_bytes = 0
        speculative_bytes = 0
        wired_bytes = 0
        compressed_bytes = 0

    # Very conservative protected baseline: max(static floor, wired+compressed+margin).
    dynamic_protected = wired_bytes + compressed_bytes + (2 * 1024**3)
    protected_bytes = max(policy.min_protected_bytes, dynamic_protected)

    # Optional headroom is what's left after protected + a free floor.
    optional_headroom = max(0, total - protected_bytes - policy.min_free_floor_bytes)

    pressure = _memory_pressure_level()
    disallow = False
    if pressure.get("available") is True:
        level = pressure.get("normalized")
        if level == "critical" and policy.critical_pressure_disallow:
            disallow = True
        if level == "warn" and policy.warn_pressure_disallow:
            disallow = True

    return {
        "total_bytes": total,
        "page_size_bytes": page_size,
        "vm": {
            "free_bytes": free_bytes,
            "inactive_bytes": inactive_bytes,
            "speculative_bytes": speculative_bytes,
            "wired_bytes": wired_bytes,
            "compressed_bytes": compressed_bytes,
        },
        "pressure": pressure,
        "protected_bytes": protected_bytes,
        "optional_headroom_bytes": optional_headroom,
        "disallow": disallow,
        "policy": {
            "min_free_floor_bytes": policy.min_free_floor_bytes,
            "min_protected_bytes": policy.min_protected_bytes,
        },
        "ts": int(time.time()),
    }


def _recommendation_for_ollama(budget: Dict[str, Any]) -> Dict[str, Any]:
    headroom = int(budget.get("optional_headroom_bytes") or 0)
    disallow = bool(budget.get("disallow"))

    if disallow or headroom < 2 * 1024**3:
        return {
            "allow_start": False,
            "target_profile": "blocked",
            "reason": "insufficient_headroom_or_pressure",
        }

    # Profiles map to orchestrator behavior (model selection + concurrency).
    if headroom < 6 * 1024**3:
        profile = "tiny"
    elif headroom < 10 * 1024**3:
        profile = "small"
    elif headroom < 16 * 1024**3:
        profile = "medium"
    else:
        profile = "large"

    return {
        "allow_start": True,
        "target_profile": profile,
        "reason": "headroom_available",
    }


class GovernorHandler(BaseHTTPRequestHandler):
    server_version = "HostMemoryGovernor/1.0"

    def _auth_ok(self) -> bool:
        token = getattr(self.server, "auth_token", "")
        if not token:
            return True
        header = self.headers.get("Authorization") or ""
        return header == f"Bearer {token}"

    def _json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if not self._auth_ok():
            self._json(401, {"error": "unauthorized"})
            return

        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._json(200, {"ok": True})
            return

        if parsed.path == "/v1/status":
            self._json(200, _compute_budget(DEFAULT_POLICY))
            return

        if parsed.path == "/v1/top":
            qs = parse_qs(parsed.query)
            try:
                limit = int(qs.get("limit", ["20"])[0])
            except ValueError:
                limit = 20
            limit = max(1, min(limit, 200))
            self._json(200, {"processes": _list_top_processes(limit)})
            return

        if parsed.path == "/v1/recommendation":
            qs = parse_qs(parsed.query)
            workload = (qs.get("workload", [""])[0] or "").strip().lower()
            budget = _compute_budget(DEFAULT_POLICY)
            if workload == "ollama":
                rec = _recommendation_for_ollama(budget)
            else:
                rec = {"allow_start": not bool(budget.get("disallow")), "target_profile": "default"}
            self._json(200, {"budget": budget, "recommendation": rec})
            return

        self._json(404, {"error": "not_found"})

    def log_message(self, fmt: str, *args: Any) -> None:
        # Quiet by default; launchd captures stdout/stderr if needed.
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("HOST_MEMORY_GOVERNOR_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("HOST_MEMORY_GOVERNOR_PORT", "8766")))
    parser.add_argument("--token", default=os.environ.get("HOST_MEMORY_GOVERNOR_TOKEN", ""))
    args = parser.parse_args()

    httpd = HTTPServer((args.host, args.port), GovernorHandler)
    setattr(httpd, "auth_token", args.token)
    httpd.serve_forever()


if __name__ == "__main__":
    main()

