"""
Centralized generation logic for the runtime layer.

Accepts chat-format messages, applies the tokenizer chat template,
and runs model.generate() on the correct device.
"""

import torch
from typing import List, Dict, Optional, Any


def generate_from_messages(
    model,
    tokenizer,
    messages: List[Dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 256,
    device: Optional[str] = None,
    stream: bool = False,
):
    """Generate a completion from a list of chat messages.

    Uses the tokenizer's built-in chat template when available,
    otherwise falls back to a simple concatenation.
    """
    if device is None:
        device = str(model.device) if hasattr(model, "device") else "cpu"

    from .chat_content import normalize_chat_messages

    messages = normalize_chat_messages(messages)

    # Try the HF chat template path first
    try:
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    except Exception:
        # Fallback: plain text assembly
        parts = []
        for msg in messages:
            parts.append(f"<|{msg['role']}|>\n{msg['content']}")
        parts.append("<|assistant|>\n")
        prompt = "\n".join(parts)

    inputs = tokenizer(prompt, return_tensors="pt").to(device)

    gen_kwargs = {
        "max_new_tokens": max_tokens,
        "do_sample": temperature > 0,
    }
    if temperature > 0:
        gen_kwargs["temperature"] = temperature
        gen_kwargs["top_p"] = 0.95

    if stream:
        from transformers import TextIteratorStreamer
        import threading
        streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
        gen_kwargs["streamer"] = streamer

        thread = threading.Thread(target=model.generate, kwargs={**inputs, **gen_kwargs})
        thread.start()
        return streamer
    else:
        with torch.no_grad():
            output_ids = model.generate(**inputs, **gen_kwargs)

        # Decode only the newly generated tokens
        new_tokens = output_ids[0][inputs["input_ids"].shape[-1]:]
        return tokenizer.decode(new_tokens, skip_special_tokens=True)


# Legacy single-prompt helper (kept for backward compatibility)
def generate_text(model, tokenizer, prompt: str, max_tokens: int = 128) -> str:
    messages = [{"role": "user", "content": prompt}]
    return generate_from_messages(model, tokenizer, messages, max_tokens=max_tokens)
