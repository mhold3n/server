"""Utilities for parsing OpenClaw-style `op://` references.

The OpenClaw secret map uses references like:

  op://<vault>/<item>/<field>

1Password CLI also supports shorter forms; we support:
  op://<vault>/<item>
and let the caller provide `field` via the `key` argument.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OpRef:
    vault: str
    item: str
    field: str | None = None


def parse_op_ref(op_ref: str) -> OpRef:
    """Parse an `op://` reference.

    Returns:
      OpRef with optional field.
    """

    raw = op_ref.strip()
    if not raw.startswith("op://"):
        raise ValueError("op_ref must start with 'op://'")

    # op refs may contain URL-encoded characters; we keep it simple and
    # split on slashes.
    rest = raw[len("op://") :]
    parts = [p for p in rest.split("/") if p]
    if len(parts) < 2 or len(parts) > 3:
        raise ValueError(
            "op_ref must look like op://<vault>/<item>[/<field>] "
            f"(got: {op_ref!r})"
        )

    vault = parts[0]
    item = parts[1]
    field = parts[2] if len(parts) == 3 else None
    return OpRef(vault=vault, item=item, field=field)

