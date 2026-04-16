from domain_research import default_research_pool_keys


def test_default_research_pool_keys() -> None:
    assert "source_corroboration" in default_research_pool_keys()
