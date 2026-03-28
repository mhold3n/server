"""Vault client for secrets management."""

import json
import os
from typing import Any

import hvac
import structlog

logger = structlog.get_logger()


class VaultClient:
    """HashiCorp Vault client wrapper."""

    def __init__(self):
        """Initialize Vault client."""
        self.vault_url = os.getenv("VAULT_ADDR", "http://vault:8200")
        self.vault_token = os.getenv("VAULT_TOKEN", "root")
        self.client = None
        self._connect()

    def _connect(self):
        """Connect to Vault."""
        try:
            self.client = hvac.Client(url=self.vault_url, token=self.vault_token)

            # Test connection
            if self.client.is_authenticated():
                logger.info("Connected to Vault", url=self.vault_url)
            else:
                logger.warning("Vault authentication failed", url=self.vault_url)
                self.client = None

        except Exception as e:
            logger.error("Failed to connect to Vault", url=self.vault_url, error=str(e))
            self.client = None

    async def health_check(self) -> bool:
        """Check if Vault is healthy."""
        if not self.client:
            return False

        try:
            health = self.client.sys.read_health_status()
            return health.get("initialized", False)
        except Exception as e:
            logger.error("Vault health check failed", error=str(e))
            return False

    async def get_secret(self, path: str, key: str | None = None) -> str:
        """Get a secret from Vault."""
        if not self.client:
            raise RuntimeError("Vault client not connected")

        try:
            # Read secret
            response = self.client.secrets.kv.v2.read_secret_version(path=path)

            if not response or "data" not in response:
                raise ValueError(f"Secret not found: {path}")

            secret_data = response["data"]["data"]

            if key:
                if key not in secret_data:
                    raise ValueError(f"Key '{key}' not found in secret: {path}")
                return str(secret_data[key])
            else:
                return json.dumps(secret_data, indent=2)

        except Exception as e:
            logger.error("Failed to get secret", path=path, key=key, error=str(e))
            raise

    async def set_secret(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        """Set a secret in Vault."""
        if not self.client:
            raise RuntimeError("Vault client not connected")

        try:
            # Write secret
            response = self.client.secrets.kv.v2.create_or_update_secret(
                path=path, secret=data
            )

            logger.info("Secret stored", path=path, keys=list(data.keys()))

            return {
                "path": path,
                "created": True,
                "version": response.get("version"),
            }

        except Exception as e:
            logger.error("Failed to set secret", path=path, error=str(e))
            raise

    async def list_secrets(self, path: str) -> dict[str, Any]:
        """List secrets in a path."""
        if not self.client:
            raise RuntimeError("Vault client not connected")

        try:
            # List secrets
            response = self.client.secrets.kv.v2.list_secrets(path=path)

            if not response or "data" not in response:
                return {"path": path, "secrets": []}

            secrets = response["data"]["keys"]

            return {
                "path": path,
                "secrets": secrets,
                "count": len(secrets),
            }

        except Exception as e:
            logger.error("Failed to list secrets", path=path, error=str(e))
            raise

    async def delete_secret(self, path: str) -> dict[str, Any]:
        """Delete a secret from Vault."""
        if not self.client:
            raise RuntimeError("Vault client not connected")

        try:
            # Delete secret
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(path=path)

            logger.info("Secret deleted", path=path)

            return {
                "path": path,
                "deleted": True,
            }

        except Exception as e:
            logger.error("Failed to delete secret", path=path, error=str(e))
            raise
