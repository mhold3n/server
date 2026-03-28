"""Configuration management using Pydantic Settings."""

from enum import StrEnum

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerProfile(StrEnum):
    """LLM worker profile."""

    GPU = "gpu"
    APPLE = "apple"


class WorkerSettings(BaseModel):
    """Resolved worker connection + model settings for a profile."""

    base_url: str
    default_model: str


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # OpenAI/Worker configuration
    openai_base_url: str = Field(
        default="http://worker.local:8000/v1",
        description="Base URL for OpenAI-compatible API (vLLM/TGI)",
    )
    openai_api_key: str = Field(
        default="local-dev-token",
        description="API key for worker authentication",
    )

    orch_profile: WorkerProfile = Field(
        default=WorkerProfile.GPU,
        description="LLM worker profile (gpu or apple)",
    )

    # Redis configuration
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL",
    )

    # Application settings
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    host: str = Field(default="0.0.0.0", description="Host to bind to")
    port: int = Field(default=8080, description="Port to bind to")

    # Security
    jwt_secret: str | None = Field(default=None, description="JWT secret key")
    encryption_key: str | None = Field(default=None, description="Encryption key")

    # Metrics
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")

    # Proxmox (VM management)
    proxmox_base_url: str = Field(
        default="https://192.168.50.180:8006",
        description="Proxmox API base URL (e.g., https://host:8006)",
    )
    proxmox_token_id: str | None = Field(
        default=None,
        description="Proxmox API token ID (user@realm!token)",
    )
    proxmox_token_secret: str | None = Field(
        default=None,
        description="Proxmox API token secret",
    )
    proxmox_verify_ssl: bool = Field(
        default=False,
        description="Verify SSL cert when calling Proxmox (often self-signed)",
    )

    # qBittorrent (torrent management)
    qb_base_url: str = Field(
        default="http://gluetun:8080",
        description="qBittorrent base URL (gluetun exposes qb at 8080 in-cluster)",
    )
    qb_username: str = Field(default="admin", description="qBittorrent username")
    qb_password: str | None = Field(
        default=None, description="qBittorrent password (set via UI/env)"
    )

    # Search backends
    meili_url: str = Field(
        default="http://meilisearch:7700",
        description="Meilisearch base URL",
    )
    meili_api_key: str | None = Field(
        default=None, description="Meilisearch API key (master/search key)"
    )
    meili_index: str = Field(default="files", description="Meilisearch index name")
    searx_url: str = Field(
        default="http://searxng:8080",
        description="SearXNG base URL",
    )

    # Router/AI stack URLs
    router_url: str = Field(default="http://router:8000", description="Agent router base URL")
    ai_stack_url: str = Field(default="http://ai-stack:8090", description="AI stack base URL")

    # Wrkhrs RAG/ASR health (optional; for status endpoint; set to empty to skip)
    rag_health_url: str | None = Field(
        default=None,
        description="Base URL for RAG worker health (e.g. http://wrkhrs-rag:8000)",
    )
    asr_health_url: str | None = Field(
        default=None,
        description="Base URL for ASR worker health (e.g. http://wrkhrs-asr:8000)",
    )

    # AI workflow configuration
    ai_repos: str = Field(
        default=(
            "https://github.com/mhold3n/server,"
            "https://github.com/datalab-to/marker"
        ),
        description="Comma-separated list of repositories for code-RAG workflows",
    )
    marker_docs_dir: str = Field(
        default="/mnt/appdata/addons/documents",
        description="Host path for marker input documents (if mounted)",
    )
    marker_processed_dir: str = Field(
        default="/mnt/appdata/addons/documents_processed",
        description="Host path for marker processed documents (if mounted)",
    )

    def model_post_init(self, __context) -> None:
        """Validate configuration after initialization."""
        if self.debug and not self.jwt_secret:
            self.jwt_secret = "dev-secret-key"
        if self.debug and not self.encryption_key:
            self.encryption_key = "dev-encryption-key-32-chars"


def get_worker_settings(cfg: "Settings") -> WorkerSettings:
    """
    Resolve worker connection + default model based on the active profile.

    - gpu: assumes a remote vLLM/TGI-style worker serving Qwen3.5-9B.
    - apple: assumes a local Apple Silicon worker exposed on host.docker.internal.
    """
    profile = cfg.orch_profile or WorkerProfile.GPU
    if isinstance(profile, str):
        try:
            profile = WorkerProfile(profile.lower())
        except ValueError:
            profile = WorkerProfile.GPU

    if profile is WorkerProfile.APPLE:
        base_url = cfg.openai_base_url or "http://host.docker.internal:8000/v1"
        default_model = "local-llm-apple"
    else:
        base_url = cfg.openai_base_url
        default_model = "Qwen/Qwen3.5-9B"

    return WorkerSettings(base_url=base_url, default_model=default_model)


# Global settings instance
settings = Settings()
