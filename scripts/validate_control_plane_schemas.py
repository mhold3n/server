#!/usr/bin/env python3
"""
Validate control-plane JSON Schemas (Draft 2020-12) and golden fixtures.

For agents: run from repo root — `python scripts/validate_control_plane_schemas.py`.
Exits non-zero on compile errors, unresolved refs, or fixture mismatches.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError, ValidationError
except ImportError:
    print("Install jsonschema: pip install jsonschema", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "schemas" / "control-plane" / "v1"
REGISTRY_PATH = SCHEMA_DIR / "registry.json"


def load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    manifest = load_schema(REGISTRY_PATH)
    schemas = manifest.get("schemas", [])
    if not schemas:
        print("registry.json missing schemas[]", file=sys.stderr)
        return 1

    registry: dict[str, dict] = {}
    for entry in schemas:
        rel = entry["path"]
        spath = SCHEMA_DIR / rel
        if not spath.exists():
            print(f"Missing schema file: {spath}", file=sys.stderr)
            return 1
        data = load_schema(spath)
        sid = data.get("$id")
        if sid != entry["id"]:
            print(
                f"$id mismatch for {rel}: file has {sid!r}, registry expects {entry['id']!r}",
                file=sys.stderr,
            )
            return 1
        registry[sid] = data

    # Compile each schema with resolver
    resolver = jsonschema.RefResolver(base_uri="", referrer=None, store=registry)

    for sid, schema in registry.items():
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as e:
            print(f"Schema compile failed {sid}: {e.message}", file=sys.stderr)
            return 1
        try:
            Draft202012Validator(schema, resolver=resolver)
        except Exception as e:  # noqa: BLE001 — surface resolver/ref errors
            print(f"Validator init failed {sid}: {e}", file=sys.stderr)
            return 1

    # Fixtures: task-packet
    tp_schema = registry[
        "https://birtha.local/schemas/control-plane/v1/task-packet.schema.json"
    ]
    tp_val = Draft202012Validator(tp_schema, resolver=resolver)

    valid_fix = SCHEMA_DIR / "fixtures" / "task-packet" / "valid-minimal.json"
    invalid_fix = SCHEMA_DIR / "fixtures" / "task-packet" / "invalid-missing-required.json"

    try:
        tp_val.validate(load_schema(valid_fix))
    except ValidationError as e:
        print(f"Expected valid fixture to pass: {e.message}", file=sys.stderr)
        return 1

    try:
        tp_val.validate(load_schema(invalid_fix))
    except ValidationError:
        pass
    else:
        print("Expected invalid fixture to fail validation", file=sys.stderr)
        return 1

    # Additional contracts: validate golden fixtures compile against registry
    extra_fixtures: list[tuple[str, Path]] = [
        (
            "https://birtha.local/schemas/control-plane/v1/knowledge-pack.schema.json",
            SCHEMA_DIR / "fixtures" / "knowledge-pack" / "valid-minimal.json",
        ),
        (
            "https://birtha.local/schemas/control-plane/v1/knowledge-pool-assessment.schema.json",
            SCHEMA_DIR / "fixtures" / "knowledge-pool-assessment" / "valid-minimal.json",
        ),
        (
            "https://birtha.local/schemas/control-plane/v1/recipe-object.schema.json",
            SCHEMA_DIR / "fixtures" / "recipe-object" / "valid-minimal.json",
        ),
        (
            "https://birtha.local/schemas/control-plane/v1/execution-adapter-spec.schema.json",
            SCHEMA_DIR / "fixtures" / "execution-adapter-spec" / "valid-minimal.json",
        ),
        (
            "https://birtha.local/schemas/control-plane/v1/evidence-bundle.schema.json",
            SCHEMA_DIR / "fixtures" / "evidence-bundle" / "valid-minimal.json",
        ),
        (
            "https://birtha.local/schemas/control-plane/v1/role-context-bundle.schema.json",
            SCHEMA_DIR / "fixtures" / "role-context-bundle" / "valid-minimal.json",
        ),
        (
            "https://birtha.local/schemas/control-plane/v1/environment-spec.schema.json",
            SCHEMA_DIR / "fixtures" / "environment-spec" / "valid-minimal.json",
        ),
        (
            "https://birtha.local/schemas/control-plane/v1/gui-session-spec.schema.json",
            SCHEMA_DIR / "fixtures" / "gui-session-spec" / "valid-minimal.json",
        ),
        (
            "https://birtha.local/schemas/control-plane/v1/decision-log.schema.json",
            SCHEMA_DIR / "fixtures" / "decision-log" / "valid-minimal.json",
        ),
        (
            "https://birtha.local/schemas/control-plane/v1/verification-report.schema.json",
            SCHEMA_DIR / "fixtures" / "verification-report" / "valid-minimal.json",
        ),
        (
            "https://birtha.local/schemas/control-plane/v1/problem-brief.schema.json",
            SCHEMA_DIR / "fixtures" / "problem-brief" / "valid-minimal.json",
        ),
        (
            "https://birtha.local/schemas/control-plane/v1/task-queue.schema.json",
            SCHEMA_DIR / "fixtures" / "task-queue" / "valid-minimal.json",
        ),
        (
            "https://birtha.local/schemas/control-plane/v1/engineering-state.schema.json",
            SCHEMA_DIR / "fixtures" / "engineering-state" / "valid-minimal.json",
        ),
        (
            "https://birtha.local/schemas/control-plane/v1/routing-policy.schema.json",
            SCHEMA_DIR / "fixtures" / "routing-policy" / "valid-minimal.json",
        ),
    ]
    for sid, fpath in extra_fixtures:
        if not fpath.exists():
            print(f"Missing fixture: {fpath}", file=sys.stderr)
            return 1
        sub = Draft202012Validator(registry[sid], resolver=resolver)
        try:
            sub.validate(load_schema(fpath))
        except ValidationError as e:
            print(f"Expected valid fixture {fpath}: {e.message}", file=sys.stderr)
            return 1

    print("control-plane schema gate: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
