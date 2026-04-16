#!/usr/bin/env python3
# pyright: reportMissingImports=false
"""
Compile orchestration wiki markdown into response-control JSON catalogs.

For agents and humans:
- Editable sources live under ``knowledge/wiki/orchestration/{modes,pools,...}/*.md``.
- Each file uses JSON frontmatter for the full machine card (same shape as JSON elements).
- Markdown after the closing ``---`` is narrative-only and is ignored for routing.
- Validated payloads are written to ``knowledge/response-control/*.json`` for
  ``ResponseControlCatalog.load`` in the API service.

Commands:
- default / no flag: write JSON from wiki sources.
- ``--check``: fail if committed JSON differs from compiled output (CI drift gate).
- ``--migrate-from-json``: one-time bootstrap: emit wiki ``.md`` files from current JSON.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, TypeVar

from response_control_framework.contracts import (
    KnowledgePoolPayload,
    ModuleCardPayload,
    ResponseModePayload,
    TechniqueCardPayload,
    TheoryCardPayload,
)

T = TypeVar("T")

SHARD_CONFIG: list[tuple[str, str, type[Any], str, Callable[[Any], str]]] = [
    ("modes", "modes.json", ResponseModePayload, "response_mode_id", lambda m: m.response_mode_id),
    ("pools", "knowledge-pools.json", KnowledgePoolPayload, "knowledge_pool_id", lambda m: m.knowledge_pool_id),
    ("modules", "modules.json", ModuleCardPayload, "module_card_id", lambda m: m.module_card_id),
    ("techniques", "techniques.json", TechniqueCardPayload, "technique_card_id", lambda m: m.technique_card_id),
    ("theory", "theory.json", TheoryCardPayload, "theory_card_id", lambda m: m.theory_card_id),
]

META_KEYS = frozenset({"wiki_zone", "wiki_shard"})

def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for path in [here, *here.parents]:
        if (path / "knowledge").exists() and (path / "services" / "response-control-framework").exists():
            return path
    raise RuntimeError("Could not locate repo root")

REPO_ROOT = _repo_root()
ORCHESTRATION_ROOT = REPO_ROOT / "knowledge" / "wiki" / "orchestration"
RESPONSE_CONTROL_DIR = REPO_ROOT / "knowledge" / "response-control"


# --- Path / filename helpers -------------------------------------------------


def _slugify(value: str) -> str:
    """Derive a safe filename stem from a card id."""
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip())
    return cleaned.strip("_") or "unnamed"


def _split_front_matter(raw: str, path: Path) -> tuple[dict[str, Any], str]:
    """Parse leading JSON front matter between ``---`` lines; body may be empty."""
    if not raw.startswith("---"):
        raise ValueError(f"{path}: file must start with front matter delimited by ---")
    rest = raw[3:].lstrip("\n")
    closing = "\n---\n"
    idx = rest.find(closing)
    if idx == -1:
        raise ValueError(f"{path}: missing closing --- delimiter for front matter")
    json_text = rest[:idx].strip()
    body = rest[idx + len(closing) :]
    data = json.loads(json_text)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: front matter must be a JSON object, got {type(data)}")
    return data, body


# --- Validation helpers ------------------------------------------------------


def _strip_meta(fm: dict[str, Any], path: Path, expected_shard: str) -> dict[str, Any]:
    zone = fm.get("wiki_zone")
    if zone is not None and str(zone) != "orchestration":
        raise ValueError(f"{path}: wiki_zone must be 'orchestration' or omitted, got {zone!r}")
    shard = fm.get("wiki_shard")
    if shard is not None and str(shard) != expected_shard:
        raise ValueError(
            f"{path}: wiki_shard {shard!r} does not match directory shard {expected_shard!r}",
        )
    return {k: v for k, v in fm.items() if k not in META_KEYS}


def _load_shard(shard: str, model: type[Any]) -> list[Any]:
    """Load and validate all markdown cards for one shard."""
    shard_dir = ORCHESTRATION_ROOT / shard
    if not shard_dir.is_dir():
        raise FileNotFoundError(f"Missing orchestration shard directory: {shard_dir}")
    items: list[Any] = []
    for path in sorted(shard_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        fm, _body = _split_front_matter(raw, path)
        payload = _strip_meta(fm, path, shard)
        items.append(model.model_validate(payload))
    id_field = next(s[3] for s in SHARD_CONFIG if s[0] == shard)
    items.sort(key=lambda m: getattr(m, id_field))
    return items


# --- Emit JSON (deterministic ordering for diffs and CI) ---------------------


def _canonical_json_lines(models: list[Any]) -> str:
    """Serialize validated models to stable JSON text (trailing newline)."""
    dumped = [m.model_dump(mode="json") for m in models]
    id_key = None
    if dumped:
        # Infer sort key from first object
        first = dumped[0]
        for candidate in (
            "response_mode_id",
            "knowledge_pool_id",
            "module_card_id",
            "technique_card_id",
            "theory_card_id",
        ):
            if candidate in first:
                id_key = candidate
                break
        if id_key:
            dumped = sorted(dumped, key=lambda row: str(row.get(id_key, "")))
    text = json.dumps(dumped, indent=2, sort_keys=True) + "\n"
    return text


def compile_all(write: bool) -> dict[str, str]:
    """Compile all shards; if write, persist to JSON files. Returns shard -> text."""
    outputs: dict[str, str] = {}
    for shard, json_name, model, _id_field, _sort_fn in SHARD_CONFIG:
        models = _load_shard(shard, model)
        text = _canonical_json_lines(models)
        outputs[json_name] = text
        if write:
            out_path = RESPONSE_CONTROL_DIR / json_name
            out_path.write_text(text, encoding="utf-8")
    return outputs


# --- Drift gate --------------------------------------------------------------


def run_check() -> int:
    """Return 0 if on-disk JSON matches compiled output."""
    compiled = compile_all(write=False)
    mismatches: list[str] = []
    for name, text in compiled.items():
        path = RESPONSE_CONTROL_DIR / name
        if not path.exists():
            mismatches.append(f"missing {path}")
            continue
        existing = path.read_text(encoding="utf-8")
        if existing != text:
            mismatches.append(f"drift: {path}")
    if mismatches:
        print("wiki-check failed:", file=sys.stderr)
        for line in mismatches:
            print(f"  {line}", file=sys.stderr)
        return 1
    return 0


# --- Bootstrap wiki sources from legacy JSON ---------------------------------


def migrate_from_json() -> None:
    """Emit ``knowledge/wiki/orchestration/<shard>/*.md`` from current JSON catalogs."""
    for shard, json_name, model, id_field, _ in SHARD_CONFIG:
        src = RESPONSE_CONTROL_DIR / json_name
        if not src.exists():
            raise FileNotFoundError(f"Missing JSON to migrate: {src}")
        records = json.loads(src.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError(f"{src} must contain a JSON array")
        out_dir = ORCHESTRATION_ROOT / shard
        out_dir.mkdir(parents=True, exist_ok=True)
        for item in records:
            validated = model.model_validate(item)
            payload = validated.model_dump(mode="json")
            slug = _slugify(str(payload[id_field]))
            fm: dict[str, Any] = {"wiki_zone": "orchestration", "wiki_shard": shard, **payload}
            summary = str(payload.get("summary", "")).strip()
            json_block = json.dumps(fm, indent=2, sort_keys=True)
            body = summary + "\n" if summary else "\n"
            content = f"---\n{json_block}\n---\n\n{body}"
            (out_dir / f"{slug}.md").write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare compiled JSON to committed files; exit 1 on drift.",
    )
    parser.add_argument(
        "--migrate-from-json",
        action="store_true",
        help="Create wiki markdown sources from knowledge/response-control JSON (bootstrap).",
    )
    args = parser.parse_args()

    if args.migrate_from_json:
        migrate_from_json()
        print("Migration wrote markdown under knowledge/wiki/orchestration/", file=sys.stderr)
        return 0

    if args.check:
        return run_check()

    RESPONSE_CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    compile_all(write=True)
    print(f"Wrote JSON under {RESPONSE_CONTROL_DIR}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
