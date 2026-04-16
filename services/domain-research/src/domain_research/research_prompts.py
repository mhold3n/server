"""Prompt and pool defaults for research-mode orchestration."""


def default_research_pool_keys() -> list[str]:
    """Return default knowledge pool keys for research workflows.

    Returns
    -------
    list[str]
        Pool keys aligned with orchestration wiki (``source_corroboration``).
    """
    return ["source_corroboration"]
