#!/usr/bin/env python3
"""Validate wiki proposal queue files against contract schema and policy rules."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
API_ROOT = REPO_ROOT / "services" / "api-service"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from src.control_plane.wiki_proposals import list_proposals  # noqa: E402


def main() -> int:
    try:
        proposals = list_proposals()
    except Exception as exc:  # noqa: BLE001
        print(f"wiki proposal validation failed: {exc}", file=sys.stderr)
        return 1

    for proposal in proposals:
        target = str(proposal.target_path)
        if "/_proposals/" in target or target.endswith("/_proposals"):
            print(
                f"invalid target_path for {proposal.wiki_edit_proposal_id}: {target}",
                file=sys.stderr,
            )
            return 1
    print(f"Validated {len(proposals)} wiki proposal file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
