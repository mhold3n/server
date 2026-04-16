"""Utilities for parsing Bitwarden Secrets Manager references.

We standardize on UUID-based references:

  bws://project/<projectUuid>/secret/<secretUuid>

The `bws` CLI ultimately only needs the secret UUID to retrieve values, but the
project UUID is kept for consistency and to make references self-describing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BwsRef:
    project_id: str
    secret_id: str


def parse_bws_ref(ref: str) -> BwsRef:
    raw = ref.strip()
    if not raw.startswith("bws://"):
        raise ValueError("bws ref must start with 'bws://'")

    rest = raw[len("bws://") :]
    parts = [p for p in rest.split("/") if p]
    if len(parts) != 4 or parts[0] != "project" or parts[2] != "secret":
        raise ValueError(
            "bws ref must look like bws://project/<projectUuid>/secret/<secretUuid>"
        )

    project_id = parts[1]
    secret_id = parts[3]
    if not project_id or not secret_id:
        raise ValueError("bws ref project/secret IDs must be non-empty")

    return BwsRef(project_id=project_id, secret_id=secret_id)
