"""
API key authentication for the local runtime server.

Keys are loaded from a YAML file (default: configs/auth/api_keys.yaml).
A single key grants access to all agents — the caller selects the agent
via the ``model`` field in the request body, just like the OpenAI API.

An optional ``scopes`` list can restrict a key to specific agent names.
An empty scopes list (the default) means "all agents allowed".
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from fastapi import Request, HTTPException


@dataclass
class AuthEntry:
    key: str
    bundle: str = "latest"
    scopes: List[str] = field(default_factory=list)  # empty = all agents

    def is_agent_allowed(self, agent_name: str) -> bool:
        """Return True if this key is allowed to use the given agent."""
        if not self.scopes:
            return True  # no restrictions
        return agent_name in self.scopes


class APIKeyStore:
    """Loads and validates API keys from a local YAML file."""

    def __init__(self, keys_path: str = "configs/auth/api_keys.yaml"):
        self._entries: Dict[str, AuthEntry] = {}
        self._load(keys_path)

    def _load(self, path: str):
        if not os.path.exists(path):
            raise FileNotFoundError(f"API keys file not found: {path}")

        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}

        for entry in data.get("keys", []):
            key = entry["key"]
            self._entries[key] = AuthEntry(
                key=key,
                bundle=entry.get("bundle", "latest"),
                scopes=entry.get("scopes", []),
            )

    def validate(self, key: str) -> AuthEntry:
        """Validate a key and return the associated auth entry.

        Raises HTTPException 401 for unknown keys.
        """
        entry = self._entries.get(key)
        if entry is None:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return entry

    def list_keys(self) -> List[str]:
        return list(self._entries.keys())


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

_store: Optional[APIKeyStore] = None


def init_auth(keys_path: str = "configs/auth/api_keys.yaml"):
    """Initialise the global key store. Call once at server startup."""
    global _store
    _store = APIKeyStore(keys_path)
    return _store


def get_store() -> APIKeyStore:
    if _store is None:
        raise RuntimeError("APIKeyStore not initialised – call init_auth() first")
    return _store


async def require_api_key(request: Request) -> AuthEntry:
    """FastAPI dependency that extracts and validates a Bearer token."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = auth_header[len("Bearer "):]
    return get_store().validate(token)
