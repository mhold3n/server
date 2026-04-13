"""Default system prompts and Qwen sampling presets for the agent router.

Used when the API does not send a task-card-specific system prompt. Instructs
the LLM to treat wrkhrs/MCP tool results as ground truth and prefer tools over guessing.
"""

from typing import Any

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant with access to tools (RAG, filesystem, MCP). "
    "Treat tool results as authoritative. When unsure, request or use tools rather than guessing. "
    "Cite sources when you use retrieved content."
)

# Qwen3.5 recommended sampling (thinking mode general tasks)
QWEN_DEFAULT_PARAMS: dict[str, Any] = {
    "temperature": 1.0,
    "top_p": 0.95,
    "top_k": 20,
    "presence_penalty": 1.5,
    "repetition_penalty": 1.0,
}

# Presets by task type for router/API to use
TASK_TYPE_PRESETS: dict[str, dict[str, Any]] = {
    "general": QWEN_DEFAULT_PARAMS,
    "coding": {
        "temperature": 0.6,
        "top_p": 0.95,
        "top_k": 20,
        "presence_penalty": 0.0,
        "repetition_penalty": 1.0,
    },
    "retrieval_heavy": {
        "temperature": 0.7,
        "top_p": 0.95,
        "top_k": 20,
        "presence_penalty": 1.5,
        "repetition_penalty": 1.0,
    },
}


def qwen_default_params(task_type: str = "general") -> dict[str, Any]:
    """Return sampling params for Qwen for the given task type."""
    return dict(TASK_TYPE_PRESETS.get(task_type, QWEN_DEFAULT_PARAMS))
