"""Unit tests for HF role dispatch (causal vs Qwen2.5-VL) without loading weights."""

from __future__ import annotations

import pytest

import model_runtime.hf_runtime as hr


def test_infer_backend_labels() -> None:
    assert hr.infer_backend_label("general") == "causal_lm"
    assert hr.infer_backend_label("coding") == "causal_lm"
    assert hr.infer_backend_label("multimodal") == "qwen2_5_vl"


def test_loaded_generator_roles_empty_until_instantiated() -> None:
    hr._GENERATORS.clear()
    assert hr.loaded_generator_roles() == []


def test_infer_with_hf_multimodal_uses_vl_generator(monkeypatch: pytest.MonkeyPatch) -> None:
    hr._GENERATORS.clear()

    class FakeVL:
        def __init__(self, role: str) -> None:
            self.role = role

        def generate(self, system_prompt: str, user_prompt: str) -> hr.HFInferenceResult:
            return hr.HFInferenceResult(
                text='{"extract_kind":"unit"}',
                prompt_tokens=2,
                completion_tokens=3,
                latency_ms=0.1,
                structured_output={"extract_kind": "unit"},
            )

    monkeypatch.setattr(hr, "HFVLGenerator", FakeVL)
    out = hr.infer_with_hf("multimodal", "sys", "user")
    assert out.text == '{"extract_kind":"unit"}'
    assert out.structured_output == {"extract_kind": "unit"}
    hr._GENERATORS.clear()


def test_infer_with_hf_general_uses_text_generator(monkeypatch: pytest.MonkeyPatch) -> None:
    hr._GENERATORS.clear()

    class FakeText:
        def __init__(self, role: str) -> None:
            self.role = role

        def generate(self, system_prompt: str, user_prompt: str) -> hr.HFInferenceResult:
            return hr.HFInferenceResult(
                text="ok",
                prompt_tokens=1,
                completion_tokens=1,
                latency_ms=0.1,
                structured_output=None,
            )

    monkeypatch.setattr(hr, "HFTextGenerator", FakeText)
    out = hr.infer_with_hf("general", "s", "u")
    assert out.text == "ok"
    hr._GENERATORS.clear()
