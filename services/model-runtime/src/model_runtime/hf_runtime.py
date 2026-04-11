"""Lazy Hugging Face Transformers runtime for model-runtime infer endpoints."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any

from model_runtime.config import resolved_model_config, resolved_model_id


@dataclass
class HFInferenceResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    structured_output: dict[str, Any] | None = None


_GENERATORS: dict[str, "HFTextGenerator"] = {}


def _truthy(value: str | None) -> bool:
    return (value or "").lower() in {"1", "true", "yes", "on"}


def _max_output_tokens(role: str) -> int:
    cfg = resolved_model_config(role)
    env_key = f"MODEL_RUNTIME_{role.upper()}_MAX_NEW_TOKENS"
    return int(os.environ.get(env_key, cfg.get("max_output_tokens", 512)))


def _extract_json_object(text: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


class HFTextGenerator:
    def __init__(self, role: str):
        self.role = role
        cfg = resolved_model_config(role)
        self.model_id = resolved_model_id(role)
        self.model_ref = str(cfg.get("local_model_path") or self.model_id)
        self.local_files_only = bool(cfg.get("local_model_path")) or _truthy(
            os.environ.get("HF_LOCAL_FILES_ONLY"),
        )
        self.max_new_tokens = _max_output_tokens(role)

        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "Transformers runtime is not installed. Install model-runtime[hf].",
            ) from exc

        trust_remote_code = _truthy(os.environ.get("MODEL_RUNTIME_TRUST_REMOTE_CODE"))
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_ref,
            local_files_only=self.local_files_only,
            trust_remote_code=trust_remote_code,
        )
        kwargs: dict[str, Any] = {
            "local_files_only": self.local_files_only,
            "trust_remote_code": trust_remote_code,
            "torch_dtype": "auto",
        }
        device_map = os.environ.get("MODEL_RUNTIME_DEVICE_MAP", "").strip()
        if device_map:
            kwargs["device_map"] = device_map
        self.model = AutoModelForCausalLM.from_pretrained(self.model_ref, **kwargs)
        if not device_map and hasattr(self.model, "eval"):
            self.model.eval()

    def generate(self, system_prompt: str, user_prompt: str) -> HFInferenceResult:
        t0 = time.perf_counter()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if hasattr(self.tokenizer, "apply_chat_template"):
            try:
                encoded = self.tokenizer.apply_chat_template(
                    messages,
                    add_generation_prompt=True,
                    return_tensors="pt",
                    return_dict=True,
                )
            except TypeError:
                input_ids = self.tokenizer.apply_chat_template(
                    messages,
                    add_generation_prompt=True,
                    return_tensors="pt",
                )
                encoded = {"input_ids": input_ids}
        else:
            encoded = self.tokenizer(
                f"{system_prompt}\n\n{user_prompt}",
                return_tensors="pt",
            )

        try:
            device = next(self.model.parameters()).device
            encoded = {key: value.to(device) for key, value in encoded.items()}
        except Exception:
            pass

        prompt_tokens = int(encoded["input_ids"].shape[-1])
        generation_kwargs: dict[str, Any] = {
            **encoded,
            "max_new_tokens": self.max_new_tokens,
            "do_sample": False,
        }
        eos_token_id = getattr(self.tokenizer, "eos_token_id", None)
        if eos_token_id is not None:
            generation_kwargs["eos_token_id"] = eos_token_id
        output = self.model.generate(**generation_kwargs)
        generated = output[0][prompt_tokens:]
        text = self.tokenizer.decode(generated, skip_special_tokens=True).strip()
        completion_tokens = int(generated.shape[-1])
        latency_ms = (time.perf_counter() - t0) * 1000
        return HFInferenceResult(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            structured_output=_extract_json_object(text),
        )


def infer_with_hf(role: str, system_prompt: str, user_prompt: str) -> HFInferenceResult:
    if role not in _GENERATORS:
        _GENERATORS[role] = HFTextGenerator(role)
    return _GENERATORS[role].generate(system_prompt, user_prompt)
