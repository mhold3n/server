#!/usr/bin/env python3
"""
Additional classifier coverage tests.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))

from prompt_middleware.classifier import INTENT_KEYWORDS, score_intents


def test_score_intents_returns_keyword_ratios():
    scores = score_intents("cache expiration burst precompute")

    assert len(scores) == len(INTENT_KEYWORDS)
    assert scores["revisit_cache_boundary_and_policy"] > 0
    assert scores["frontend_perf_render_thrash"] == 0
