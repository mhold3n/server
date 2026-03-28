"""Secure secrets management MCP server."""

import os
from typing import Any

import structlog
from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .vault_client import VaultClient

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

app = FastAPI(title="Secrets MCP Server", version="0.1.0")

# Global vault client
vault_client = VaultClient()


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
    try:
        vault_status = await vault_client.health_check()
        return {
            "status": "healthy" if vault_status else "degraded",
            "service": "secrets-mcp",
            "vault_connected": vault_status,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "secrets-mcp",
            "error": str(e),
        }


@app.get("/tools")
async def list_tools():
    """List available tools."""
    return {
        "tools": [
            {
                "name": "get_secret",
                "description": "Retrieve a secret from the vault",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Secret path"},
                        "key": {"type": "string", "description": "Secret key (optional)"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "set_secret",
                "description": "Store a secret in the vault",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Secret path"},
                        "data": {"type": "object", "description": "Secret data"},
                    },
                    "required": ["path", "data"],
                },
            },
            {
                "name": "list_secrets",
                "description": "List secrets in a path",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Secret path"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "delete_secret",
                "description": "Delete a secret from the vault",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Secret path"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "encrypt_data",
                "description": "Encrypt data using local encryption",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "data": {"type": "string", "description": "Data to encrypt"},
                    },
                    "required": ["data"],
                },
            },
            {
                "name": "decrypt_data",
                "description": "Decrypt data using local encryption",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "encrypted_data": {"type": "string", "description": "Encrypted data"},
                    },
                    "required": ["encrypted_data"],
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

        if request.tool == "get_secret":
            result = await vault_client.get_secret(
                request.arguments["path"],
                request.arguments.get("key"),
            )
        elif request.tool == "set_secret":
            result = await vault_client.set_secret(
                request.arguments["path"],
                request.arguments["data"],
            )
        elif request.tool == "list_secrets":
            result = await vault_client.list_secrets(request.arguments["path"])
        elif request.tool == "delete_secret":
            result = await vault_client.delete_secret(request.arguments["path"])
        elif request.tool == "encrypt_data":
            result = await encrypt_data_locally(request.arguments["data"])
        elif request.tool == "decrypt_data":
            result = await decrypt_data_locally(request.arguments["encrypted_data"])
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


async def encrypt_data_locally(data: str) -> str:
    """Encrypt data using local encryption key."""
    try:
        # Get encryption key from environment
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            raise ValueError("ENCRYPTION_KEY environment variable not set")

        # Ensure key is 32 bytes
        if len(key) != 32:
            key = key[:32].ljust(32, "0")

        # Create Fernet instance
        fernet = Fernet(Fernet.generate_key())

        # Encrypt data
        encrypted_data = fernet.encrypt(data.encode())

        return encrypted_data.decode()

    except Exception as e:
        logger.error("Failed to encrypt data", error=str(e))
        raise


async def decrypt_data_locally(encrypted_data: str) -> str:
    """Decrypt data using local encryption key."""
    try:
        # Get encryption key from environment
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            raise ValueError("ENCRYPTION_KEY environment variable not set")

        # Ensure key is 32 bytes
        if len(key) != 32:
            key = key[:32].ljust(32, "0")

        # Create Fernet instance
        fernet = Fernet(Fernet.generate_key())

        # Decrypt data
        decrypted_data = fernet.decrypt(encrypted_data.encode())

        return decrypted_data.decode()

    except Exception as e:
        logger.error("Failed to decrypt data", error=str(e))
        raise


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7002)
