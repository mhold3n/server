from pydantic import BaseModel
from typing import Optional


class RuntimeConfig(BaseModel):
    server_mode: str = "direct"
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    batch_size: int = 1
    api_keys_path: str = "configs/auth/api_keys.yaml"
    agents_dir: str = "configs/agents"
    bundle_id: str = "latest"
    base_model: Optional[str] = None
    # Hugging Face Hub HTTP timeouts (seconds). Default hub is 10s; slow networks need more.
    hf_hub_timeout_seconds: int = 300
