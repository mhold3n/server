"""
engineering_core: deterministic mechanics solver and report verification.

For agents: numbers come from reference_mechanics only — not from LLMs.
"""

from engineering_core.solve import solve_mechanics
from engineering_core.verify import verify_engineering_report

__all__ = ["solve_mechanics", "verify_engineering_report"]
