"""Task card schema and registry for orchestration workflows.

Task cards define the workflow type, system prompt, required tools, and
guardrails. The router uses them to drive the orchestration loop; the user
never sees ai_gateway_client directly—the router controls what data Qwen receives.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TaskCard(BaseModel):
    """First-class workflow definition (task card)."""

    id: str = Field(..., description="Unique workflow id (e.g. code-rag, media-fixups)")
    display_name: str = Field(..., description="Human-readable name for UI/CLI")
    description: str = Field(
        ..., description="Short description of what this workflow does"
    )
    system_prompt: str = Field(
        ...,
        description="System prompt template for the LLM (task card instructions)",
    )
    required_tools: list[str] = Field(
        default_factory=list,
        description="MCP/ai_gateway_client tools this workflow should use (e.g. vector-db-mcp:embedding_search)",
    )
    max_tokens: int | None = Field(
        default=None, gt=0, description="Max tokens for completion"
    )
    temperature: float = Field(
        default=0.2, ge=0.0, le=2.0, description="Sampling temperature"
    )


# Registry of task cards. Build tool_args per request in the route using card id + input + settings.
TASK_CARDS: list[TaskCard] = [
    TaskCard(
        id="code-rag",
        display_name="Code RAG",
        description="Retrieve repository and vector-db context and answer with citations.",
        system_prompt=(
            "You are a code assistant. Use the provided tools to retrieve context from repositories and the vector store. "
            "Always cite sources. Prefer tool results over guessing; if a tool fails, say so and do not hallucinate."
        ),
        required_tools=[
            "github-mcp:search",
            "filesystem-mcp:code_analysis",
            "vector-db-mcp:embedding_search",
        ],
        max_tokens=4096,
        temperature=0.2,
    ),
    TaskCard(
        id="media-fixups",
        display_name="Media / Document Fix-ups",
        description="Analyze documents in the processed docs directory and propose fixes.",
        system_prompt=(
            "You assist with media and document fix-ups. Use the filesystem tools to read and traverse the processed documents directory. "
            "Propose concrete fixes based on the retrieved content. Cite file paths when referencing content."
        ),
        required_tools=[
            "filesystem-mcp:directory_traversal",
            "filesystem-mcp:file_read",
        ],
        max_tokens=4096,
        temperature=0.2,
    ),
    TaskCard(
        id="sysadmin-ops",
        display_name="Sysadmin Ops",
        description="General sysadmin and operations assistance (tools optional).",
        system_prompt="You are a sysadmin assistant. Answer concisely. If the user asks for something that requires tools, say so.",
        required_tools=[],
        max_tokens=2048,
        temperature=0.3,
    ),
]


def get_task_card(card_id: str) -> TaskCard | None:
    """Return the task card for the given id, or None."""
    for card in TASK_CARDS:
        if card.id == card_id:
            return card
    return None


def list_task_cards() -> list[TaskCard]:
    """Return all registered task cards."""
    return list(TASK_CARDS)


def build_tool_args_for_card(
    card_id: str,
    input_: dict[str, Any],
    *,
    ai_repos: str = "",
    marker_processed_dir: str = "",
) -> dict[str, dict[str, Any]]:
    """Build tool_args for the router from task card id and user input."""
    repos = [r.strip() for r in ai_repos.split(",") if r.strip()] if ai_repos else []
    tool_args: dict[str, dict[str, Any]] = {}

    if card_id == "code-rag":
        tool_args = {
            "github-mcp:search": {"repos": repos, "query": input_.get("query", "")},
            "filesystem-mcp:code_analysis": {"path": input_.get("path", "/workspace")},
            "vector-db-mcp:embedding_search": {
                "text": input_.get("query", ""),
                "top_k": 5,
            },
        }
    elif card_id == "media-fixups":
        tool_args = {
            "filesystem-mcp:directory_traversal": {"path": marker_processed_dir},
            "filesystem-mcp:file_read": {"path": input_.get("file", "")},
        }
    elif card_id == "sysadmin-ops":
        tool_args = {}

    return tool_args
