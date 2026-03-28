from src.integrations.openclaw.mapping import map_runtime_to_openclaw


def test_openclaw_adapter_mapping_preserves_text():
    payload = {"text": "hello from runtime"}
    out = map_runtime_to_openclaw(payload)
    assert out["choices"][0]["message"]["content"] == "hello from runtime"


def test_openclaw_adapter_mapping_empty_string():
    out = map_runtime_to_openclaw({"text": ""})
    assert out["choices"][0]["message"]["content"] == ""
