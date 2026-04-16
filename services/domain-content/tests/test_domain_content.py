from domain_content import default_content_pool_keys


def test_default_content_pool_keys() -> None:
    assert "video_editing" in default_content_pool_keys()
