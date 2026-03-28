"""File system operations and code analysis MCP server."""

from typing import Any

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .code_analyzer import CodeAnalyzer
from .file_operations import FileOperations

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

app = FastAPI(title="Filesystem MCP Server", version="0.1.0")

# Global instances
file_ops = FileOperations()
code_analyzer = CodeAnalyzer()


class ToolRequest(BaseModel):
    """Tool request model."""

    tool: str = Field(..., description="Tool name")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class ToolResponse(BaseModel):
    """Tool response model."""

    content: list[dict[str, str]] = Field(..., description="Response content")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "filesystem-mcp"}


@app.get("/tools")
async def list_tools():
    """List available tools."""
    return {
        "tools": [
            {
                "name": "read_file",
                "description": "Read the contents of a file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"},
                        "encoding": {"type": "string", "default": "utf-8"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "write_file",
                "description": "Write content to a file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"},
                        "content": {"type": "string", "description": "File content"},
                        "encoding": {"type": "string", "default": "utf-8"},
                    },
                    "required": ["path", "content"],
                },
            },
            {
                "name": "list_directory",
                "description": "List contents of a directory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path"},
                        "recursive": {"type": "boolean", "default": False},
                        "include_hidden": {"type": "boolean", "default": False},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "search_files",
                "description": "Search for files matching a pattern",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "File pattern (glob)"},
                        "root_path": {"type": "string", "description": "Root directory to search"},
                        "include_hidden": {"type": "boolean", "default": False},
                    },
                    "required": ["pattern"],
                },
            },
            {
                "name": "search_content",
                "description": "Search for content within files",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query (regex)"},
                        "root_path": {"type": "string", "description": "Root directory to search"},
                        "file_pattern": {"type": "string", "description": "File pattern to include"},
                        "exclude_pattern": {"type": "string", "description": "File pattern to exclude"},
                        "case_sensitive": {"type": "boolean", "default": False},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "analyze_code",
                "description": "Analyze code structure and dependencies",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File or directory path"},
                        "language": {"type": "string", "description": "Programming language"},
                        "include_ast": {"type": "boolean", "default": False},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "get_dependencies",
                "description": "Get dependencies for a project",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Project root path"},
                        "language": {"type": "string", "description": "Programming language"},
                    },
                    "required": ["path"],
                },
            },
        ]
    }


@app.post("/call", response_model=ToolResponse)
async def call_tool(request: ToolRequest):
    """Call a tool with the given arguments."""
    try:
        logger.info(
            "Calling tool",
            tool=request.tool,
            arguments=request.arguments,
        )

        if request.tool == "read_file":
            result = await file_ops.read_file(
                request.arguments["path"],
                request.arguments.get("encoding", "utf-8"),
            )
        elif request.tool == "write_file":
            result = await file_ops.write_file(
                request.arguments["path"],
                request.arguments["content"],
                request.arguments.get("encoding", "utf-8"),
            )
        elif request.tool == "list_directory":
            result = await file_ops.list_directory(
                request.arguments["path"],
                request.arguments.get("recursive", False),
                request.arguments.get("include_hidden", False),
            )
        elif request.tool == "search_files":
            result = await file_ops.search_files(
                request.arguments["pattern"],
                request.arguments.get("root_path", "."),
                request.arguments.get("include_hidden", False),
            )
        elif request.tool == "search_content":
            result = await file_ops.search_content(
                request.arguments["query"],
                request.arguments.get("root_path", "."),
                request.arguments.get("file_pattern"),
                request.arguments.get("exclude_pattern"),
                request.arguments.get("case_sensitive", False),
            )
        elif request.tool == "analyze_code":
            result = await code_analyzer.analyze_code(
                request.arguments["path"],
                request.arguments.get("language"),
                request.arguments.get("include_ast", False),
            )
        elif request.tool == "get_dependencies":
            result = await code_analyzer.get_dependencies(
                request.arguments["path"],
                request.arguments.get("language"),
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {request.tool}")

        return ToolResponse(content=[{"type": "text", "text": result}])

    except Exception as e:
        logger.error(
            "Tool call failed",
            tool=request.tool,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7001)
