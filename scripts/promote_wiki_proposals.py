#!/usr/bin/env python3
"""Promote approved wiki edit proposals into canonical wiki + compiled catalogs."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

from response_control_framework.contracts import WikiEditProposalStatus  # noqa: E402
from response_control_framework.wiki_proposals import (  # noqa: E402
    list_proposals,
    update_proposal_status,
)


def _wiki_repo_root(repo_root: Path) -> Path:
    """Directory that contains ``knowledge/wiki`` (server + ``xlotyl/`` layout)."""
    xlotyl = repo_root / "xlotyl"
    if (xlotyl / "knowledge" / "wiki").is_dir():
        return xlotyl
    return repo_root


def _append_promoted_content(target_path: Path, content: str, proposal_id: str) -> bool:
    marker = f"<!-- promoted_from:{proposal_id} -->"
    existing = target_path.read_text(encoding="utf-8") if target_path.exists() else ""
    if marker in existing:
        return False
    block = (
        "\n\n## Promoted wiki edit\n\n"
        f"{marker}\n"
        f"{content.strip()}\n"
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(existing + block, encoding="utf-8")
    return True


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)


def promote(*, approver: str, open_pr: bool, pr_base: str) -> int:
    approved = list_proposals(status=WikiEditProposalStatus.APPROVED)
    changed = 0
    wiki_root = _wiki_repo_root(REPO_ROOT)
    for proposal in approved:
        target = wiki_root / proposal.target_path
        did_change = _append_promoted_content(
            target,
            proposal.proposed_content,
            str(proposal.wiki_edit_proposal_id),
        )
        if not did_change:
            continue
        changed += 1
        update_proposal_status(
            proposal_id=str(proposal.wiki_edit_proposal_id),
            status=WikiEditProposalStatus.PROMOTED,
            approver=approver,
            approval_notes=proposal.approval_notes,
            promotion_ref=f"promoted:{datetime.now(UTC).isoformat()}",
        )

    if changed == 0:
        sys.stderr.write("No approved proposals required promotion.\n")
        return 0

    _run([sys.executable, "scripts/sync_domain_orchestration_wiki.py"])
    _run([sys.executable, "scripts/wiki_compile_response_control.py"])
    _run([sys.executable, "scripts/wiki_compile_response_control.py", "--check"])
    sys.stderr.write(f"Promoted {changed} proposal(s) and refreshed response-control JSON.\n")

    if open_pr:
        branch = f"wiki/proposal-promotion-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        _run(["git", "checkout", "-b", branch])
        _run(["git", "add", "xlotyl/knowledge/wiki", "xlotyl/knowledge/response-control"])
        _run(["git", "commit", "-m", "[Feature] Add promote approved wiki proposals"])
        _run(["git", "push", "-u", "origin", branch])
        _run(
            [
                "gh",
                "pr",
                "create",
                "--base",
                pr_base,
                "--title",
                "[Feature] Add approved wiki proposal promotions",
                "--body",
                "Promotes approved wiki edit proposals into canonical wiki pages and recompiles response-control catalogs.",
            ]
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approver", default="automation.promote_wiki_proposals")
    parser.add_argument("--open-pr", action="store_true")
    parser.add_argument("--pr-base", default="main")
    args = parser.parse_args()
    return promote(approver=args.approver, open_pr=args.open_pr, pr_base=args.pr_base)


if __name__ == "__main__":
    raise SystemExit(main())
