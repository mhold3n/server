"""
Agent registry.

Loads all agent configs from a directory of YAML files and provides
lookup-by-name.
"""

import os
import glob
import logging
from typing import Dict

from .base import BaseAgent

logger = logging.getLogger(__name__)

AGENT_REGISTRY: Dict[str, BaseAgent] = {}


def load_agents(agents_dir: str = "configs/agents") -> Dict[str, BaseAgent]:
    """Scan the agents config directory and load every YAML file as an agent.

    The agent name is the YAML filename without extension
    (e.g. ``base-agent.yaml`` → ``base-agent``).
    """
    global AGENT_REGISTRY
    AGENT_REGISTRY.clear()

    if not os.path.isdir(agents_dir):
        logger.warning("Agents directory not found: %s", agents_dir)
        return AGENT_REGISTRY

    for path in sorted(glob.glob(os.path.join(agents_dir, "*.yaml"))):
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            agent = BaseAgent.from_config_file(path)
            AGENT_REGISTRY[name] = agent
            logger.info("Loaded agent: %s", name)
        except Exception:
            logger.exception("Failed to load agent config: %s", path)

    return AGENT_REGISTRY


def get_agent(name: str) -> BaseAgent:
    """Return a loaded agent by name. Raises ValueError for unknown names."""
    if name not in AGENT_REGISTRY:
        raise ValueError(
            f"Unknown agent '{name}'. Available: {list(AGENT_REGISTRY.keys())}"
        )
    return AGENT_REGISTRY[name]


def list_agent_names():
    return list(AGENT_REGISTRY.keys())
