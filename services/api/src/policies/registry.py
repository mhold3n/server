"""Policy registry for dynamic policy discovery and management."""

from typing import Any

import structlog
from pydantic import BaseModel

from .citations import CitationPolicy
from .evidence import EvidencePolicy
from .hedging import HedgingPolicy
from .units import SIUnitPolicy

logger = structlog.get_logger()


class PolicyConfig(BaseModel):
    """Configuration for a policy."""

    name: str
    description: str
    enabled: bool = True
    config: dict[str, Any] = {}
    priority: int = 0


class PolicyRegistry:
    """Registry for managing and discovering policies."""

    def __init__(self):
        """Initialize policy registry."""
        self.policies = {}
        self.policy_configs = {}
        self._register_default_policies()

    def _register_default_policies(self) -> None:
        """Register default policies."""
        # Evidence policy
        self.register_policy(
            "evidence",
            EvidencePolicy,
            PolicyConfig(
                name="evidence",
                description="Enforces evidence requirements and citation standards",
                config={
                    "min_citations": 3,
                    "evidence_required": True,
                    "source_quotas": {
                        "textbook": 0.4,
                        "paper": 0.3,
                        "standard": 0.3,
                    },
                    "min_source_diversity": 0.3,
                },
                priority=1,
            ),
        )

        # Citation policy
        self.register_policy(
            "citations",
            CitationPolicy,
            PolicyConfig(
                name="citations",
                description="Enforces proper citation formats and source attribution",
                config={
                    "min_citations": 3,
                    "require_inline_citations": True,
                    "citation_formats": ["numeric", "author-year", "author-title"],
                    "ban_unsupported_claims": True,
                },
                priority=2,
            ),
        )

        # Hedging policy
        self.register_policy(
            "hedging",
            HedgingPolicy,
            PolicyConfig(
                name="hedging",
                description="Detects and manages uncertain language",
                config={
                    "ban_hedging": False,
                    "max_hedging_ratio": 0.1,
                    "allow_justified_hedging": True,
                },
                priority=3,
            ),
        )

        # SI units policy
        self.register_policy(
            "si_units",
            SIUnitPolicy,
            PolicyConfig(
                name="si_units",
                description="Enforces SI units and unit consistency",
                config={
                    "enforce_si_units": True,
                    "allow_common_units": True,
                    "require_unit_consistency": True,
                    "unit_conversion_threshold": 0.01,
                },
                priority=4,
            ),
        )

    def register_policy(
        self,
        name: str,
        policy_class: type,
        config: PolicyConfig,
    ) -> None:
        """Register a policy.

        Args:
            name: Policy name
            policy_class: Policy class
            config: Policy configuration
        """
        self.policies[name] = policy_class
        self.policy_configs[name] = config

        logger.info("Registered policy", policy_name=name, config=config.dict())

    def get_policy(self, name: str) -> Any | None:
        """Get a policy instance.

        Args:
            name: Policy name

        Returns:
            Policy instance or None
        """
        if name not in self.policies:
            return None

        policy_class = self.policies[name]
        config = self.policy_configs[name]

        return policy_class(**config.config)

    def get_available_policies(self) -> list[dict[str, Any]]:
        """Get list of available policies.

        Returns:
            List of policy information
        """
        policies = []

        for name, config in self.policy_configs.items():
            if config.enabled:
                policies.append({
                    "name": name,
                    "description": config.description,
                    "config": config.config,
                    "priority": config.priority,
                })

        # Sort by priority
        policies.sort(key=lambda x: x["priority"])

        return policies

    def get_policy_schema(self, name: str) -> dict[str, Any] | None:
        """Get JSON schema for a policy.

        Args:
            name: Policy name

        Returns:
            JSON schema or None
        """
        if name not in self.policy_configs:
            return None

        config = self.policy_configs[name]

        # Generate schema from config
        schema = {
            "type": "object",
            "properties": {},
            "required": [],
        }

        for key, value in config.config.items():
            if isinstance(value, bool):
                schema["properties"][key] = {"type": "boolean"}
            elif isinstance(value, int):
                schema["properties"][key] = {"type": "integer"}
            elif isinstance(value, float):
                schema["properties"][key] = {"type": "number"}
            elif isinstance(value, str):
                schema["properties"][key] = {"type": "string"}
            elif isinstance(value, list):
                schema["properties"][key] = {"type": "array"}
            elif isinstance(value, dict):
                schema["properties"][key] = {"type": "object"}
            else:
                schema["properties"][key] = {"type": "string"}

        return schema

    def update_policy_config(
        self,
        name: str,
        config: dict[str, Any],
    ) -> bool:
        """Update policy configuration.

        Args:
            name: Policy name
            config: New configuration

        Returns:
            True if successful, False otherwise
        """
        if name not in self.policy_configs:
            return False

        # Update config
        self.policy_configs[name].config.update(config)

        logger.info("Updated policy config", policy_name=name, config=config)
        return True

    def enable_policy(self, name: str) -> bool:
        """Enable a policy.

        Args:
            name: Policy name

        Returns:
            True if successful, False otherwise
        """
        if name not in self.policy_configs:
            return False

        self.policy_configs[name].enabled = True
        logger.info("Enabled policy", policy_name=name)
        return True

    def disable_policy(self, name: str) -> bool:
        """Disable a policy.

        Args:
            name: Policy name

        Returns:
            True if successful, False otherwise
        """
        if name not in self.policy_configs:
            return False

        self.policy_configs[name].enabled = False
        logger.info("Disabled policy", policy_name=name)
        return True

    def get_enabled_policies(self) -> list[str]:
        """Get list of enabled policy names.

        Returns:
            List of enabled policy names
        """
        return [
            name for name, config in self.policy_configs.items()
            if config.enabled
        ]

    def get_policy_summary(self) -> dict[str, Any]:
        """Get summary of all policies.

        Returns:
            Policy summary
        """
        total_policies = len(self.policies)
        enabled_policies = len(self.get_enabled_policies())

        policy_types = {}
        for _name, policy_class in self.policies.items():
            policy_type = policy_class.__name__
            if policy_type not in policy_types:
                policy_types[policy_type] = 0
            policy_types[policy_type] += 1

        return {
            "total_policies": total_policies,
            "enabled_policies": enabled_policies,
            "disabled_policies": total_policies - enabled_policies,
            "policy_types": policy_types,
            "policies": self.get_available_policies(),
        }


# Global policy registry instance
policy_registry = PolicyRegistry()











