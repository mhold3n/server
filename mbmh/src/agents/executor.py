"""
Agent execution loop.

Implements the core agentic cycle:
  receive → prompt → generate → parse tool calls → execute tool → loop → return
"""

import json
import re
import uuid
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable

from .prompts import build_system_prompt, format_tool_result

logger = logging.getLogger(__name__)

# Regex to find ```tool_call ... ``` blocks in model output
TOOL_CALL_PATTERN = re.compile(
    r"```tool_call\s*\n(\{.*?\})\s*\n```", re.DOTALL
)


@dataclass
class AgentResult:
    """Returned from the executor loop."""
    session_id: str
    output: str
    status: str = "completed"
    iterations: int = 0
    trace: List[Dict[str, Any]] = field(default_factory=list)


def parse_tool_calls(text: str) -> Optional[Dict[str, Any]]:
    """Extract the first tool_call JSON block from model output text."""
    match = TOOL_CALL_PATTERN.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        logger.warning("Failed to parse tool call JSON: %s", match.group(1))
        return None


def agent_loop(
    agent,
    messages: List[Dict[str, str]],
    generate_fn: Callable,
    tools: Dict[str, Any] = None,
    safety_check: Callable = None,
    session_id: str = None,
    stream_callback: Callable[[str], None] = None,
) -> AgentResult:
    """
    Run the agent execution loop.

    Parameters
    ----------
    agent : BaseAgent
        The loaded agent instance.
    messages : list[dict]
        The incoming user messages (OpenAI chat format).
    generate_fn : callable
        ``(messages, *, temperature, max_tokens, stream) -> str | Iterable[str]``.
        When ``stream`` is True, may return either token/chunk strings from an iterator
        or a single complete string; if a string is returned, it is forwarded once via
        ``stream_callback`` so SSE clients still receive body text.
    tools : dict, optional
        Mapping of tool_name -> tool instance (must have .execute(args)).
    safety_check : callable, optional
        A function(agent_config, tool_name) -> bool that validates tool access.
    session_id : str, optional
        If not provided one is generated.
    stream_callback : callable, optional
        Called with (token: str) as they arrive from the generator if stream=True.

    Returns
    -------
    AgentResult
    """
    if tools is None:
        tools = {}
    if session_id is None:
        session_id = str(uuid.uuid4())

    cfg = agent.config
    trace: List[Dict[str, Any]] = []

    # ── 1. Inject system prompt (with tool descriptions) ──────────────
    system_prompt = build_system_prompt(cfg, tools if tools else None)
    working_messages = [{"role": "system", "content": system_prompt}]
    working_messages.extend(messages)

    for iteration in range(1, cfg.max_iterations + 1):
        # ── 2. Generate ───────────────────────────────────────────────
        gen_result = generate_fn(
            working_messages,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            stream=bool(stream_callback),
        )

        # Streaming clients (OpenAI-compatible SSE) only see output via stream_callback.
        # If the backend returns a full string while stream=True, still emit it once so
        # chunks are not empty (OpenClaw and similar UIs rely on delta content events).
        assistant_text = ""
        if hasattr(gen_result, "__iter__") and not isinstance(gen_result, str):
            for token in gen_result:
                assistant_text += token
                if stream_callback:
                    stream_callback(token)
        else:
            if gen_result is None:
                assistant_text = ""
            elif isinstance(gen_result, str):
                assistant_text = gen_result
            else:
                assistant_text = str(gen_result)
            if stream_callback and assistant_text:
                stream_callback(assistant_text)

        trace.append({
            "iteration": iteration,
            "type": "generation",
            "content": assistant_text,
        })

        # ── 3. Check for tool call ────────────────────────────────────
        tool_call = parse_tool_calls(assistant_text)

        if tool_call is None:
            # No tool call → final answer
            return AgentResult(
                session_id=session_id,
                output=assistant_text,
                iterations=iteration,
                trace=trace,
            )

        tool_name = tool_call.get("tool", "")
        tool_args = tool_call.get("arguments", {})

        # ── 4. Safety check ───────────────────────────────────────────
        if safety_check and not safety_check(cfg.__dict__, tool_name):
            error_msg = f"Tool '{tool_name}' is not allowed for this agent."
            logger.warning("[%s] %s", session_id, error_msg)
            trace.append({"iteration": iteration, "type": "tool_rejected", "tool": tool_name})
            working_messages.append({"role": "assistant", "content": assistant_text})
            working_messages.append(format_tool_result(tool_name, {"error": error_msg}))
            continue

        if tool_name not in tools:
            error_msg = f"Tool '{tool_name}' not found in registry."
            trace.append({"iteration": iteration, "type": "tool_missing", "tool": tool_name})
            working_messages.append({"role": "assistant", "content": assistant_text})
            working_messages.append(format_tool_result(tool_name, {"error": error_msg}))
            continue

        # ── 5. Execute tool ───────────────────────────────────────────
        try:
            tool_result = tools[tool_name].execute(tool_args)
        except Exception as exc:
            tool_result = {"error": str(exc)}
            logger.exception("[%s] Tool '%s' raised", session_id, tool_name)

        trace.append({
            "iteration": iteration,
            "type": "tool_execution",
            "tool": tool_name,
            "arguments": tool_args,
            "result": tool_result,
        })

        # ── 6. Append to messages and continue loop ───────────────────
        working_messages.append({"role": "assistant", "content": assistant_text})
        working_messages.append(format_tool_result(tool_name, tool_result))

    # Hit max iterations
    return AgentResult(
        session_id=session_id,
        output=working_messages[-1].get("content", ""),
        status="max_iterations",
        iterations=cfg.max_iterations,
        trace=trace,
    )
