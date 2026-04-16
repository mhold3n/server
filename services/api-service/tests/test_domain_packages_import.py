"""Ensure optional domain packages resolve for control-plane integration."""

from __future__ import annotations

import domain_content
import domain_research


def test_domain_research_exports() -> None:
    assert "source_corroboration" in domain_research.default_research_pool_keys()


def test_domain_content_exports() -> None:
    assert "video_editing" in domain_content.default_content_pool_keys()
