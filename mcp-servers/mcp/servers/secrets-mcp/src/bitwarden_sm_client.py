"""Bitwarden Secrets Manager client using the supported `bws` CLI.

Rationale:
- Bitwarden documents `bws` as the primary automation interface for Secrets Manager.
- Using `bws` avoids hard-coding unstable HTTP endpoints and auth flows.

Auth:
- `BWS_ACCESS_TOKEN` must be present in the environment.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any

import structlog

from .bws_ref import BwsRef, parse_bws_ref

logger = structlog.get_logger()


@dataclass(frozen=True)
class BwsConfig:
    access_token: str
    bws_bin: str
    timeout_seconds: float


class BitwardenSmClient:
    def __init__(self) -> None:
        access_token = os.getenv("BWS_ACCESS_TOKEN", "").strip()
        self._cfg = BwsConfig(
            access_token=access_token,
            bws_bin=os.getenv("BWS_BIN", "bws").strip() or "bws",
            timeout_seconds=float(os.getenv("BWS_TIMEOUT_SECONDS", "15")),
        )

    def _require_token(self) -> None:
        if self._cfg.access_token == "":
            raise RuntimeError(
                "BWS_ACCESS_TOKEN is required for Bitwarden Secrets Manager"
            )

    def _run_bws(self, args: list[str]) -> str:
        self._require_token()
        env = dict(os.environ)
        env["BWS_ACCESS_TOKEN"] = self._cfg.access_token
        proc = subprocess.run(
            [self._cfg.bws_bin, *args],
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=self._cfg.timeout_seconds,
        )
        if proc.returncode != 0:
            msg = (
                proc.stderr or proc.stdout or f"bws exited {proc.returncode}"
            ).strip()
            raise RuntimeError(msg)
        return (proc.stdout or "").strip()

    async def health_check(self) -> bool:
        if self._cfg.access_token == "":
            return False
        try:
            # A lightweight call that validates auth without requiring secret IDs.
            self._run_bws(["secret", "list"])
            return True
        except Exception:
            logger.exception("Bitwarden SM health check failed")
            return False

    def _parse_secret_object(self, text: str) -> dict[str, Any]:
        try:
            data = json.loads(text)
        except Exception as exc:
            raise RuntimeError(f"bws returned non-JSON output: {exc}") from exc
        if not isinstance(data, dict):
            raise RuntimeError("bws secret get returned non-object JSON")
        return data

    async def get_secret(self, path: str, key: str | None = None) -> str:
        # `key` is ignored for bws:// refs; secret UUID uniquely identifies the secret.
        if path.startswith("bws://"):
            ref = parse_bws_ref(path)
            secret_id = ref.secret_id
        else:
            # Allow shorthand: "<projectUuid>/<secretUuid>"
            parts = [p for p in path.split("/") if p]
            if len(parts) != 2:
                raise ValueError(
                    "path must be bws://project/<projectUuid>/secret/<secretUuid> "
                    "or <projectUuid>/<secretUuid>"
                )
            secret_id = parts[1]

        out = self._run_bws(["secret", "get", secret_id])
        obj = self._parse_secret_object(out)
        value = obj.get("value")
        if value is None:
            return ""
        return str(value)

    async def list_secrets(self, path: str) -> dict[str, Any]:
        # Accept either a project-scoped bws ref or a project UUID.
        project_id: str | None = None
        if path.startswith("bws://"):
            ref = parse_bws_ref(path)
            project_id = ref.project_id
        else:
            project_id = path.strip() or None

        args = ["secret", "list"]
        if project_id is not None:
            args.append(project_id)

        out = self._run_bws(args)
        data = json.loads(out) if out else []
        if not isinstance(data, list):
            raise RuntimeError("bws secret list returned non-array JSON")

        # Return a compact shape (IDs + keys); do not echo values.
        secrets: list[dict[str, str]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            sid = item.get("id")
            skey = item.get("key")
            pid = item.get("projectId")
            if isinstance(sid, str) and isinstance(skey, str):
                entry: dict[str, str] = {"id": sid, "key": skey}
                if isinstance(pid, str):
                    entry["projectId"] = pid
                secrets.append(entry)

        return {"projectId": project_id, "secrets": secrets, "count": len(secrets)}

    async def set_secret(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        # Update an existing secret by UUID. (Creating new secrets can be added later.)
        if not path.startswith("bws://"):
            raise ValueError("set_secret requires a bws:// reference")

        ref: BwsRef = parse_bws_ref(path)
        secret_id = ref.secret_id

        # Determine updated fields.
        # Preferred: {"value": "..."} or {"key": "...", "value": "...", "note": "..."}
        value = data.get("value")
        if value is None and len(data) == 1:
            value = next(iter(data.values()))
        if value is None:
            raise ValueError("set_secret requires 'value' (or a single-key object)")

        # bws edit needs the project's id for some operations; fetch current object to be safe.
        current = self._parse_secret_object(self._run_bws(["secret", "get", secret_id]))
        project_id = current.get("projectId")
        key = data.get("key") or current.get("key")
        note = data.get("note") if "note" in data else None

        args = ["secret", "edit", secret_id]
        if isinstance(key, str) and key:
            args += ["--key", key]
        args += ["--value", str(value)]
        if isinstance(note, str):
            args += ["--note", note]
        if isinstance(project_id, str) and project_id:
            args += ["--project-id", project_id]

        updated = self._parse_secret_object(self._run_bws(args))
        return {"updated": True, "id": updated.get("id", secret_id)}

    async def delete_secret(self, path: str) -> dict[str, Any]:
        if not path.startswith("bws://"):
            raise ValueError("delete_secret requires a bws:// reference")
        ref = parse_bws_ref(path)
        self._run_bws(["secret", "delete", ref.secret_id])
        return {"deleted": True, "id": ref.secret_id}
