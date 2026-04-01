#!/usr/bin/env python3
"""
Tests for shadow prompts dataset integration and classification sanity.
"""

import os
import json
import pytest

try:
    import torch  # noqa: F401
except Exception:
    pytest.skip("WrkHrs shadow prompt integration requires torch (install wrkhrs[ml])", allow_module_level=True)

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "services"))
from prompt_middleware.classifier import classify_intent  # noqa: E402


def test_shadow_prompts_file_exists():
    assert os.path.exists("data/prompts/ambiguous_coding.jsonl"), "Shadow prompts JSONL missing"


def test_shadow_prompts_lengths_and_parse():
    n = 0
    with open("data/prompts/ambiguous_coding.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            assert "prompt" in obj and isinstance(obj["prompt"], str)
            assert 100 <= len(obj["prompt"]) <= 800
            n += 1
    assert n >= 10, "Expected at least 10 shadow prompts"


def test_classifier_has_signal_on_some_prompts():
    hits = 0
    with open("data/prompts/ambiguous_coding.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            intent = classify_intent(obj["prompt"])
            if intent != "unknown":
                hits += 1
    assert hits >= 3, "Classifier should recognize some intents in the dataset"


