#!/usr/bin/env python3
"""Copy orchestration wiki shards from domain packages into ``knowledge/wiki/orchestration``.

Domain packages own research/content cards under ``services/domain-*/wiki/orchestration/{shard}/``.
The super-project merge tree is the union of those files into the canonical orchestration
directory before :func:`wiki_compile` runs.

Run from the repository root (``python scripts/sync_domain_orchestration_wiki.py``).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

SHARDS = ("modes", "pools", "modules", "techniques", "theory")


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for path in [here, *here.parents]:
        if (path / "knowledge" / "wiki").is_dir() and (path / "services").is_dir():
            return path
    raise RuntimeError("Could not locate repository root")


def sync_domain_wiki(*, repo_root: Path | None = None, dry_run: bool = False) -> list[Path]:
    """Copy ``*.md`` from each domain package into ``knowledge/wiki/orchestration``."""
    root = repo_root or _repo_root()
    domain_roots = [
        root / "services" / "domain-research" / "wiki" / "orchestration",
        root / "services" / "domain-content" / "wiki" / "orchestration",
    ]
    dest_root = root / "knowledge" / "wiki" / "orchestration"
    copied: list[Path] = []
    for domain_root in domain_roots:
        if not domain_root.is_dir():
            continue
        for shard in SHARDS:
            shard_src = domain_root / shard
            if not shard_src.is_dir():
                continue
            shard_dest = dest_root / shard
            if not dry_run:
                shard_dest.mkdir(parents=True, exist_ok=True)
            for path in sorted(shard_src.glob("*.md")):
                target = shard_dest / path.name
                if dry_run:
                    copied.append(target)
                    continue
                shutil.copy2(path, target)
                copied.append(target)
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print targets that would be written without copying.",
    )
    args = parser.parse_args()
    paths = sync_domain_wiki(dry_run=args.dry_run)
    print(f"sync_domain_orchestration_wiki: {len(paths)} file(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
