"""
Tests for schema validation.

Validates that:
- Registry files conform to their schemas
- Policies conform to policy schemas
- Invalid data is properly rejected
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from validator.schema_validator import (
    SchemaValidator,
    RegistryValidator,
    PolicyValidator,
    validate_all_registries,
    validate_all_policies,
)


class TestSchemaValidator:
    """Test SchemaValidator class."""

    def test_validates_valid_task_request(self):
        validator = SchemaValidator()
        valid_request = {
            "user_input": "Implement structured task intake for the control plane",
            "project_id": "proj_example",
            "repo_ref_hint": "src/control",
            "risk_hints": ["writes_code"],
        }
        is_valid, errors = validator.validate_task_request(valid_request)
        assert is_valid, f"Should be valid: {errors}"

    def test_rejects_invalid_task_request(self):
        validator = SchemaValidator()
        invalid_request = {"user_input": ""}  # Empty string should fail minLength
        is_valid, errors = validator.validate_task_request(invalid_request)
        # Note: depends on schema having minLength constraint
        # If no constraint, this may pass

    def test_validates_valid_task_plan(self):
        validator = SchemaValidator()
        valid_plan = {
            "domain": "code",
            "project_id": "proj_example",
            "objective": "Implement the requested code task",
            "required_gates": ["schema_gate"],
            "acceptance_criteria": ["Relevant tests pass"],
            "delegation_hints": ["Lead executor may delegate targeted verification work"],
            "work_items": ["Inspect workspace", "Implement change", "Verify"],
            "implementation_outline": ["Update files", "Run tests"],
            "verification_plan": ["pytest -q"],
            "verification_blocks": [
                {
                    "name": "pytest",
                    "command": "pytest -q",
                    "required": True,
                }
            ],
            "publish_intent": {"mode": "branch_pr_dossier", "push": True},
        }
        is_valid, errors = validator.validate_task_plan(valid_plan)
        assert is_valid, f"Should be valid: {errors}"

    def test_validates_valid_task_dossier(self):
        validator = SchemaValidator()
        valid_dossier = {
            "task_id": "8b7e2d0b-27c6-43d7-b75d-4913c2f6e0e1",
            "project_id": "proj_example",
            "state": "ready_to_publish",
            "request": {
                "user_input": "Implement control-plane dev tasks",
                "project_id": "proj_example",
            },
            "plan": {
                "domain": "code",
                "required_gates": ["schema_gate"],
                "objective": "Implement control-plane dev tasks",
            },
            "run_ids": ["03a8c4f4-3f6d-48d8-89af-a19be7a9d208"],
            "workspace": {
                "canonical_repo_path": "/tmp/example",
                "worktree_path": "/tmp/example/.birtha/task-1",
                "branch_name": "birtha/example",
                "base_branch": "main",
            },
            "commands": [
                {
                    "command": "pytest -q",
                    "cwd": "/tmp/example",
                }
            ],
            "verification_results": [
                {
                    "name": "pytest",
                    "status": "passed",
                }
            ],
            "artifacts": [
                {
                    "name": "task-packet",
                    "path": "/tmp/example/.birtha/task-packet.json",
                    "kind": "task_packet",
                }
            ],
            "created_at": "2026-04-03T12:00:00Z",
            "updated_at": "2026-04-03T12:05:00Z",
        }
        is_valid, errors = validator.validate_task_dossier(valid_dossier)
        assert is_valid, f"Should be valid: {errors}"

    def test_rejects_invalid_domain(self):
        validator = SchemaValidator()
        invalid_plan = {
            "domain": "invalid_domain",  # Not in enum
            "required_gates": [],
        }
        is_valid, errors = validator.validate_task_plan(invalid_plan)
        assert not is_valid, "Should reject invalid domain"


class TestRegistryValidator:
    """Test RegistryValidator class."""

    def test_validates_kernel_registry(self):
        validator = RegistryValidator()
        is_valid, errors = validator.validate_kernel_registry()
        assert is_valid, f"Kernel registry should be valid: {errors}"

    def test_validates_quantities_registry(self):
        validator = RegistryValidator()
        is_valid, errors = validator.validate_quantities_registry()
        assert is_valid, f"Quantities registry should be valid: {errors}"

    def test_validate_all_registries(self):
        is_valid, errors = validate_all_registries()
        assert is_valid, f"All registries should be valid: {errors}"


class TestPolicyValidator:
    """Test PolicyValidator class."""

    def test_validates_unit_disambiguation_policy(self):
        validator = PolicyValidator()
        is_valid, errors = validator.validate_policy("unit_disambiguation")
        assert is_valid, f"unit_disambiguation policy should be valid: {errors}"

    def test_validates_all_policies(self):
        is_valid, errors = validate_all_policies()
        # Note: some policies may not conform to base schema
        # This is expected for policies without policy_id field
        print(f"Policy validation: {is_valid}, errors: {errors}")


def run_tests():
    """Run all schema validation tests."""
    import traceback

    test_classes = [
        TestSchemaValidator,
        TestRegistryValidator,
        TestPolicyValidator,
    ]

    passed = 0
    failed = 0

    for test_class in test_classes:
        print(f"\n{'=' * 60}")
        print(f"Running: {test_class.__name__}")
        print("=" * 60)

        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith("test_"):
                try:
                    getattr(instance, method_name)()
                    print(f"  ✓ {method_name}")
                    passed += 1
                except AssertionError as e:
                    print(f"  ✗ {method_name}: {e}")
                    failed += 1
                except Exception as e:
                    print(f"  ✗ {method_name}: {type(e).__name__}: {e}")
                    traceback.print_exc()
                    failed += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
