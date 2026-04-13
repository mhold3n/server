"""Configuration management for router service."""

from enum import StrEnum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerProfile(StrEnum):
    """LLM worker profile from the router's perspective."""

    GPU = "gpu"
    APPLE = "apple"


class Settings(BaseSettings):
    """Router service settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API configuration
    api_url: str = Field(
        default="http://api:8080",
        description="URL of the API service",
    )

    # Redis configuration
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL",
    )

    # MCP configuration
    mcp_servers_config: str = Field(
        default="/app/config/mcp_servers.yaml",
        description="Path to MCP servers configuration file",
    )

    # Application settings
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    host: str = Field(default="0.0.0.0", description="Host to bind to")
    port: int = Field(default=8000, description="Port to bind to")

    # Router settings
    max_concurrent_requests: int = Field(
        default=10,
        description="Maximum concurrent requests to handle",
    )
    request_timeout: int = Field(
        default=600,
        description="Request timeout in seconds",
    )

    # LLM defaults (kept in sync with API)
    orch_profile: WorkerProfile = Field(
        default=WorkerProfile.GPU,
        description="LLM worker profile (gpu or apple)",
    )
    default_llm_model: str = Field(
        default="Qwen/Qwen3.5-9B",
        description="Default model to assume when none is specified",
    )

    # MCP client settings
    mcp_connect_timeout: int = Field(
        default=10,
        description="MCP connection timeout in seconds",
    )
    mcp_request_timeout: int = Field(
        default=30,
        description="MCP request timeout in seconds",
    )


# Global settings instance
settings = Settings()
