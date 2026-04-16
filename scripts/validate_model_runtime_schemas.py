#!/usr/bin/env python3
"""
Validate model-runtime JSON Schemas (Draft 2020-12) and golden fixtures.

Merges control-plane common + model-runtime registry for $ref resolution.
Run from repo root: python scripts/validate_model_runtime_schemas.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError, ValidationError
except ImportError:
    print("Install jsonschema: pip install jsonschema", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _control_plane_v1_dir(repo: Path) -> Path:
    candidates = (
        repo
        / "xlotyl"
        / "services"
        / "response-control-framework"
        / "schemas"
        / "control-plane"
        / "v1",
        repo / "services" / "response-control-framework" / "schemas" / "control-plane" / "v1",
        repo / "schemas" / "control-plane" / "v1",
    )
    for p in candidates:
        if (p / "registry.json").is_file():
            return p
    return candidates[0]


def _model_runtime_v1_dir(repo: Path) -> Path:
    candidates = (
        repo / "xlotyl" / "schemas" / "model-runtime" / "v1",
        repo / "schemas" / "model-runtime" / "v1",
    )
    for p in candidates:
        if (p / "registry.json").is_file():
            return p
    return candidates[0]


CP_DIR = _control_plane_v1_dir(REPO_ROOT)
MR_DIR = _model_runtime_v1_dir(REPO_ROOT)
CP_REGISTRY = CP_DIR / "registry.json"
MR_REGISTRY = MR_DIR / "registry.json"


def load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_registry() -> dict[str, dict]:
    """Load all schemas from both registries into id -> schema map."""
    out: dict[str, dict] = {}

    for reg_path, base_dir in (
        (CP_REGISTRY, CP_DIR),
        (MR_REGISTRY, MR_DIR),
    ):
        manifest = load_schema(reg_path)
        for entry in manifest.get("schemas", []):
            rel = entry["path"]
            spath = base_dir / rel
            if not spath.exists():
                print(f"Missing schema file: {spath}", file=sys.stderr)
                sys.exit(1)
            data = load_schema(spath)
            sid = data.get("$id")
            if sid != entry["id"]:
                print(
                    f"$id mismatch for {rel}: file {sid!r} registry {entry['id']!r}",
                    file=sys.stderr,
                )
                sys.exit(1)
            if sid in out:
                print(f"Duplicate $id: {sid}", file=sys.stderr)
                sys.exit(1)
            out[sid] = data

    return out


def main() -> int:
    registry = build_registry()

    try:
        from jsonschema import RefResolver
    except ImportError:
        print("jsonschema RefResolver missing", file=sys.stderr)
        return 2

    resolver = RefResolver(base_uri="", referrer=None, store=registry)

    for sid, schema in registry.items():
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as e:
            print(f"Schema compile failed {sid}: {e.message}", file=sys.stderr)
            return 1
        try:
            Draft202012Validator(schema, resolver=resolver)
        except Exception as e:  # noqa: BLE001
            print(f"Validator init failed {sid}: {e}", file=sys.stderr)
            return 1

    orch_id = "https://birtha.local/schemas/model-runtime/v1/orchestration_packet.schema.json"
    solve_id = "https://birtha.local/schemas/model-runtime/v1/solve_mechanics_request_v1.schema.json"

    orch_val = Draft202012Validator(registry[orch_id], resolver=resolver)
    solve_val = Draft202012Validator(registry[solve_id], resolver=resolver)

    # Valid root + valid child (schema allows null parent — runtime enforces branch rule)
    for name in ("valid-root.json", "valid-child.json"):
        p = MR_DIR / "fixtures" / "orchestration_packet" / name
        try:
            orch_val.validate(load_schema(p))
        except ValidationError as e:
            print(f"Expected valid {name}: {e.message}", file=sys.stderr)
            return 1

    # Solve minimal
    sp = MR_DIR / "fixtures" / "solve_mechanics_request_v1" / "valid-minimal.json"
    try:
        solve_val.validate(load_schema(sp))
    except ValidationError as e:
        print(f"Expected valid solve fixture: {e.message}", file=sys.stderr)
        return 1

    print("model-runtime schema gate: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
