"""Golden test sets for evaluation."""

import os
from typing import Any

import structlog

logger = structlog.get_logger()


def load_golden_sets() -> dict[str, list[dict[str, Any]]]:
    """Load golden test sets.

    Returns:
        Dictionary of golden test sets
    """
    golden_sets = {}

    # Load from files
    golden_sets_dir = os.path.dirname(__file__)

    # Chemistry tests
    golden_sets["chemistry"] = [
        {
            "id": "chem-1",
            "prompt": "Explain the mechanism of SN2 nucleophilic substitution in organic chemistry",
            "expected_citations_min": 3,
            "expected_sources": ["textbook", "paper"],
            "SI_required": True,
            "hedging_allowed": False,
            "reference_uris": ["https://example.com/sn2-mechanism"],
        },
        {
            "id": "chem-2",
            "prompt": "Calculate the pH of a 0.1 M solution of acetic acid (Ka = 1.8 × 10^-5)",
            "expected_citations_min": 2,
            "expected_sources": ["textbook"],
            "SI_required": True,
            "hedging_allowed": False,
            "reference_uris": ["https://example.com/ph-calculation"],
        },
        {
            "id": "chem-3",
            "prompt": "Describe the bonding in benzene and explain why it's aromatic",
            "expected_citations_min": 3,
            "expected_sources": ["textbook", "paper"],
            "SI_required": False,
            "hedging_allowed": False,
            "reference_uris": ["https://example.com/benzene-bonding"],
        },
    ]

    # Mechanical engineering tests
    golden_sets["mechanical"] = [
        {
            "id": "mech-1",
            "prompt": "Calculate the stress in a steel beam with a cross-sectional area of 100 mm² under a load of 5000 N",
            "expected_citations_min": 2,
            "expected_sources": ["textbook", "standard"],
            "SI_required": True,
            "hedging_allowed": False,
            "reference_uris": ["https://example.com/stress-calculation"],
        },
        {
            "id": "mech-2",
            "prompt": "Explain the difference between ductile and brittle failure modes",
            "expected_citations_min": 3,
            "expected_sources": ["textbook", "paper"],
            "SI_required": False,
            "hedging_allowed": False,
            "reference_uris": ["https://example.com/failure-modes"],
        },
        {
            "id": "mech-3",
            "prompt": "Design a simple gear train with a speed reduction ratio of 4:1",
            "expected_citations_min": 2,
            "expected_sources": ["textbook", "standard"],
            "SI_required": True,
            "hedging_allowed": False,
            "reference_uris": ["https://example.com/gear-design"],
        },
    ]

    # Materials science tests
    golden_sets["materials"] = [
        {
            "id": "mat-1",
            "prompt": "Compare the mechanical properties of steel and aluminum alloys",
            "expected_citations_min": 3,
            "expected_sources": ["textbook", "paper", "standard"],
            "SI_required": True,
            "hedging_allowed": False,
            "reference_uris": ["https://example.com/steel-aluminum-comparison"],
        },
        {
            "id": "mat-2",
            "prompt": "Explain the heat treatment process for hardening steel",
            "expected_citations_min": 2,
            "expected_sources": ["textbook", "standard"],
            "SI_required": True,
            "hedging_allowed": False,
            "reference_uris": ["https://example.com/steel-hardening"],
        },
        {
            "id": "mat-3",
            "prompt": "Describe the crystal structure of titanium and its effect on properties",
            "expected_citations_min": 3,
            "expected_sources": ["textbook", "paper"],
            "SI_required": False,
            "hedging_allowed": False,
            "reference_uris": ["https://example.com/titanium-crystal-structure"],
        },
    ]

    # General engineering tests
    golden_sets["general"] = [
        {
            "id": "gen-1",
            "prompt": "Explain the principles of heat transfer by conduction, convection, and radiation",
            "expected_citations_min": 3,
            "expected_sources": ["textbook", "paper"],
            "SI_required": True,
            "hedging_allowed": False,
            "reference_uris": ["https://example.com/heat-transfer"],
        },
        {
            "id": "gen-2",
            "prompt": "Calculate the Reynolds number for water flowing through a pipe with diameter 50 mm at velocity 2 m/s",
            "expected_citations_min": 2,
            "expected_sources": ["textbook"],
            "SI_required": True,
            "hedging_allowed": False,
            "reference_uris": ["https://example.com/reynolds-number"],
        },
        {
            "id": "gen-3",
            "prompt": "Describe the working principle of a heat exchanger",
            "expected_citations_min": 2,
            "expected_sources": ["textbook", "standard"],
            "SI_required": False,
            "hedging_allowed": False,
            "reference_uris": ["https://example.com/heat-exchanger"],
        },
    ]

    # Code-related tests
    golden_sets["code"] = [
        {
            "id": "code-1",
            "prompt": "Write a Python function to calculate the factorial of a number",
            "expected_citations_min": 1,
            "expected_sources": ["textbook", "documentation"],
            "SI_required": False,
            "hedging_allowed": True,
            "reference_uris": ["https://example.com/python-factorial"],
        },
        {
            "id": "code-2",
            "prompt": "Explain the difference between a list and a tuple in Python",
            "expected_citations_min": 2,
            "expected_sources": ["documentation", "textbook"],
            "SI_required": False,
            "hedging_allowed": True,
            "reference_uris": ["https://example.com/python-lists-tuples"],
        },
        {
            "id": "code-3",
            "prompt": "Design a REST API endpoint for user authentication",
            "expected_citations_min": 2,
            "expected_sources": ["documentation", "standard"],
            "SI_required": False,
            "hedging_allowed": True,
            "reference_uris": ["https://example.com/rest-api-auth"],
        },
    ]

    # Policy enforcement tests
    golden_sets["policy"] = [
        {
            "id": "policy-1",
            "prompt": "What is the melting point of steel?",
            "expected_citations_min": 2,
            "expected_sources": ["textbook", "standard"],
            "SI_required": True,
            "hedging_allowed": False,
            "reference_uris": ["https://example.com/steel-melting-point"],
        },
        {
            "id": "policy-2",
            "prompt": "Explain the concept of entropy in thermodynamics",
            "expected_citations_min": 3,
            "expected_sources": ["textbook", "paper"],
            "SI_required": True,
            "hedging_allowed": False,
            "reference_uris": ["https://example.com/entropy-thermodynamics"],
        },
        {
            "id": "policy-3",
            "prompt": "Calculate the moment of inertia for a rectangular beam",
            "expected_citations_min": 2,
            "expected_sources": ["textbook", "standard"],
            "SI_required": True,
            "hedging_allowed": False,
            "reference_uris": ["https://example.com/moment-of-inertia"],
        },
    ]

    # Load from files if they exist
    for set_name in golden_sets.keys():
        file_path = os.path.join(golden_sets_dir, f"{set_name}.json")
        if os.path.exists(file_path):
            try:
                import json
                with open(file_path) as f:
                    file_tests = json.load(f)
                    golden_sets[set_name].extend(file_tests)
                logger.info(f"Loaded additional tests from {file_path}")
            except Exception as e:
                logger.warning(f"Failed to load tests from {file_path}: {e}")

    return golden_sets


def get_test_by_id(test_id: str) -> dict[str, Any]:
    """Get a specific test by ID.

    Args:
        test_id: Test ID

    Returns:
        Test configuration

    Raises:
        ValueError: If test not found
    """
    golden_sets = load_golden_sets()

    for _set_name, tests in golden_sets.items():
        for test in tests:
            if test["id"] == test_id:
                return test

    raise ValueError(f"Test with ID '{test_id}' not found")


def get_tests_by_category(category: str) -> list[dict[str, Any]]:
    """Get tests by category.

    Args:
        category: Test category

    Returns:
        List of test configurations
    """
    golden_sets = load_golden_sets()

    if category in golden_sets:
        return golden_sets[category]

    return []


def get_all_test_ids() -> list[str]:
    """Get all test IDs.

    Returns:
        List of test IDs
    """
    golden_sets = load_golden_sets()

    test_ids = []
    for tests in golden_sets.values():
        for test in tests:
            test_ids.append(test["id"])

    return test_ids











