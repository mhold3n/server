"""
Base agent abstraction.  Config-driven, loadable from YAML.
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class AgentConfig:
    """Validated agent configuration loaded from YAML."""
    agent_type: str = "base"
    system_prompt: str = "You are a helpful assistant."
    temperature: float = 0.7
    max_tokens: int = 1024
    max_iterations: int = 10
    tools_allowed: List[str] = field(default_factory=list)
    bundle: str = "latest"


class BaseAgent:
    """A config-driven agent that can be loaded from a YAML file."""

    def __init__(self, config: AgentConfig):
        self.config = config

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config_file(cls, path: str) -> "BaseAgent":
        """Load an agent from a YAML config file on disk."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Agent config not found: {path}")

        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}

        cfg = AgentConfig(**{
            k: v for k, v in data.items()
            if k in AgentConfig.__dataclass_fields__
        })
        return cls(cfg)

    @classmethod
    def from_dict(cls, data: dict) -> "BaseAgent":
        cfg = AgentConfig(**{
            k: v for k, v in data.items()
            if k in AgentConfig.__dataclass_fields__
        })
        return cls(cfg)

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------

    def build_system_message(self) -> Dict[str, str]:
        return {"role": "system", "content": self.config.system_prompt}

    def __repr__(self):
        return f"<BaseAgent type={self.config.agent_type} tools={self.config.tools_allowed}>"
