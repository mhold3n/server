"""
Prompt construction helpers for agents.
"""

import json
from typing import List, Dict, Any


def build_tool_schema_block(tools: Dict[str, Any]) -> str:
    """Format tool schemas into a text block for system prompt injection."""
    if not tools:
        return ""

    lines = ["You have access to the following tools:", ""]
    for name, tool in tools.items():
        lines.append(f"### {name}")
        if hasattr(tool, "description"):
            lines.append(f"Description: {tool.description}")
        if hasattr(tool, "input_schema"):
            lines.append(f"Input schema: {json.dumps(tool.input_schema)}")
        lines.append("")

    lines.append(
        "To use a tool, respond with a JSON block in this exact format:\n"
        '```tool_call\n{"tool": "<tool_name>", "arguments": {<args>}}\n```\n'
        "After the tool result is returned, continue reasoning."
    )
    return "\n".join(lines)


def build_system_prompt(agent_config, tool_schemas: Dict[str, Any] = None) -> str:
    """Assemble the full system prompt from agent config + tool block."""
    parts = [agent_config.system_prompt]

    if tool_schemas:
        parts.append(build_tool_schema_block(tool_schemas))

    return "\n\n".join(parts)


def format_tool_result(tool_name: str, result: Any) -> Dict[str, str]:
    """Wrap a tool execution result as an assistant-visible message."""
    return {
        "role": "tool",
        "name": tool_name,
        "content": json.dumps(result) if not isinstance(result, str) else result,
    }


def messages_to_prompt_text(messages: List[Dict[str, str]]) -> str:
    """Fallback plain-text formatter when the tokenizer lacks a chat template."""
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        parts.append(f"<|{role}|>\n{content}")
    parts.append("<|assistant|>\n")
    return "\n".join(parts)
