"""Configuration management for worker client."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Worker client settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Worker configuration
    worker_base_url: str = Field(
        default="http://worker.local:8000/v1",
        description="Base URL for worker API (vLLM/TGI)",
    )
    worker_api_key: str = Field(
        default="local-dev-token",
        description="API key for worker authentication",
    )

    # Client settings
    timeout: int = Field(
        default=120,
        description="Request timeout in seconds",
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retry attempts",
    )
    retry_delay: float = Field(
        default=1.0,
        description="Initial delay between retries in seconds",
    )
    retry_backoff: float = Field(
        default=2.0,
        description="Backoff multiplier for retry delays",
    )

    # Streaming settings
    stream_chunk_size: int = Field(
        default=1024,
        description="Chunk size for streaming responses",
    )
    stream_timeout: int = Field(
        default=30,
        description="Timeout for streaming connections",
    )

    # Model settings
    default_model: str = Field(
        default="mistralai/Mistral-7B-Instruct-v0.3",
        description="Default model to use",
    )
    default_temperature: float = Field(
        default=0.7,
        description="Default temperature for generation",
    )
    default_max_tokens: int = Field(
        default=2048,
        description="Default maximum tokens to generate",
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    debug: bool = Field(default=False, description="Enable debug mode")


# Global settings instance
settings = Settings()
