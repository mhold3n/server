"""1Password Connect client for resolving secrets via `op://`-style refs.

This MCP server keeps the existing tool surface:
  - get_secret(path, key?)
  - set_secret(path, data)
  - list_secrets(path)
  - delete_secret(path)

For the Connect backend, `get_secret` and friends accept either:
  - An `op://<vault>/<item>/<field>` reference (path starts with `op://`)
  - Or `path=<vault>/<item>` with `key=<field>`
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from .op_ref import OpRef, parse_op_ref

logger = structlog.get_logger()


@dataclass(frozen=True)
class ConnectConfig:
    base_url: str
    token: str


def _env_str(name: str, default: str) -> str:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    return val


class ConnectClient:
    def __init__(self) -> None:
        base_url = os.getenv("OP_CONNECT_HOST", "http://connect-api:8080").strip()
        base_url = base_url.rstrip("/")
        token = os.getenv("OP_CONNECT_TOKEN", "").strip()

        self._cfg = ConnectConfig(base_url=base_url, token=token)
        self._client = httpx.AsyncClient(
            timeout=float(os.getenv("OP_HTTP_TIMEOUT_SECONDS", "10"))
        )

        self._vault_cache: dict[str, str] = {}  # vault name -> vault UUID
        self._item_cache: dict[tuple[str, str], str] = (
            {}
        )  # (vault UUID, item title) -> item UUID

        # Field label -> field UUID for a specific item UUID.
        self._field_cache: dict[tuple[str, str], dict[str, str]] = {}

    async def close(self) -> None:
        await self._client.aclose()

    def _auth_headers(self) -> dict[str, str]:
        if not self._cfg.token:
            raise RuntimeError(
                "OP_CONNECT_TOKEN is required for 1Password Connect access"
            )
        return {
            "Authorization": f"Bearer {self._cfg.token}",
            "Content-Type": "application/json",
        }

    async def _get_json(
        self, path: str, *, params: dict[str, str] | None = None
    ) -> Any:
        url = f"{self._cfg.base_url}{path}"
        res = await self._client.get(url, headers=self._auth_headers(), params=params)
        if res.status_code == 401:
            raise RuntimeError("Connect authorization failed (401)")
        res.raise_for_status()
        return res.json()

    async def _patch_json(self, path: str, body: dict[str, Any]) -> Any:
        url = f"{self._cfg.base_url}{path}"
        res = await self._client.patch(url, headers=self._auth_headers(), json=body)
        if res.status_code == 401:
            raise RuntimeError("Connect authorization failed (401)")
        res.raise_for_status()
        return res.json() if res.content else {}

    async def _delete(self, path: str) -> None:
        url = f"{self._cfg.base_url}{path}"
        res = await self._client.delete(url, headers=self._auth_headers())
        if res.status_code == 401:
            raise RuntimeError("Connect authorization failed (401)")
        res.raise_for_status()

    async def health_check(self) -> bool:
        if not self._cfg.token:
            return False
        try:
            url = f"{self._cfg.base_url}/heartbeat"
            res = await self._client.get(url, headers=self._auth_headers())
            return res.status_code == 200
        except Exception:
            logger.exception("Connect health check failed")
            return False

    async def list_vaults(self, *, name: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, str] | None = None
        if name is not None:
            params = {"filter": f'name eq "{name}"'}
        data = await self._get_json("/v1/vaults", params=params)
        if not isinstance(data, list):
            return []
        return data

    async def _get_vault_uuid(self, vault_name: str) -> str:
        cached = self._vault_cache.get(vault_name)
        if cached:
            return cached

        vaults = await self.list_vaults(name=vault_name)
        for v in vaults:
            if v.get("name") == vault_name:
                vault_uuid = (
                    v.get("id")
                    or v.get("uuid")
                    or v.get("vaultUUID")
                    or v.get("vaultUuid")
                )
                if isinstance(vault_uuid, str) and vault_uuid:
                    self._vault_cache[vault_name] = vault_uuid
                    return vault_uuid

        raise KeyError(f"Connect vault not found: {vault_name}")

    async def _get_item_uuid(self, vault_uuid: str, item_title: str) -> str:
        key = (vault_uuid, item_title)
        cached = self._item_cache.get(key)
        if cached:
            return cached

        params = {"filter": f'title eq "{item_title}"'}
        items = await self._get_json(f"/v1/vaults/{vault_uuid}/items", params=params)
        if not isinstance(items, list):
            raise KeyError(f"Unexpected Connect list-items response for {item_title}")

        for item in items:
            if item.get("title") == item_title:
                item_uuid = item.get("id") or item.get("uuid") or item.get("itemUUID")
                if isinstance(item_uuid, str) and item_uuid:
                    self._item_cache[key] = item_uuid
                    return item_uuid

        raise KeyError(f"Connect item not found: vault={vault_uuid} item={item_title}")

    async def _get_item_fields_index(
        self, vault_uuid: str, item_uuid: str
    ) -> dict[str, str]:
        cache_key = (vault_uuid, item_uuid)
        existing = self._field_cache.get(cache_key)
        if existing is not None:
            return existing

        item = await self._get_json(f"/v1/vaults/{vault_uuid}/items/{item_uuid}")
        fields = item.get("fields", [])
        if not isinstance(fields, list):
            raise RuntimeError(
                "Unexpected Connect item details: fields missing/not a list"
            )

        idx: dict[str, str] = {}
        for f in fields:
            if not isinstance(f, dict):
                continue
            fid = f.get("id")
            if not (isinstance(fid, str) and fid):
                continue

            # Connect field metadata uses either `label` (common for custom fields)
            # or `purpose` (USERNAME/PASSWORD/NOTES) depending on field type.
            label = f.get("label")
            if isinstance(label, str) and label:
                idx[label] = fid
                continue

            purpose = f.get("purpose")
            if isinstance(purpose, str) and purpose:
                idx[purpose] = fid
                continue

            field_type = f.get("type")
            if isinstance(field_type, str) and field_type:
                idx[field_type] = fid

        self._field_cache[cache_key] = idx
        return idx

    async def _get_field_value(
        self, vault_uuid: str, item_uuid: str, field_label: str
    ) -> str:
        item = await self._get_json(f"/v1/vaults/{vault_uuid}/items/{item_uuid}")
        fields = item.get("fields", [])
        if not isinstance(fields, list):
            raise RuntimeError(
                "Unexpected Connect item details: fields missing/not a list"
            )

        for f in fields:
            if not isinstance(f, dict):
                continue
            label = f.get("label") or f.get("purpose") or f.get("type")
            if str(label) == field_label:
                value = f.get("value")
                if value is None:
                    return ""
                return str(value)

        raise KeyError(f"Connect field not found: field={field_label}")

    async def get_secret(self, path: str, key: str | None = None) -> str:
        op_ref: OpRef
        if path.startswith("op://"):
            op_ref = parse_op_ref(path)
            field = op_ref.field or key
            if not field:
                raise ValueError("op:// reference requires a field (or pass key=field)")
        else:
            if key is None:
                raise ValueError(
                    "key must be provided when path is not an op:// reference"
                )
            # Interpret `path` as `<vault>/<item>`
            parts = [p for p in path.split("/") if p]
            if len(parts) < 2:
                raise ValueError(
                    "path must be <vault>/<item> when not using op:// refs"
                )
            op_ref = OpRef(vault=parts[0], item="/".join(parts[1:]), field=key)

        vault_uuid = await self._get_vault_uuid(op_ref.vault)
        item_uuid = await self._get_item_uuid(vault_uuid, op_ref.item)
        field_label = op_ref.field or key
        assert field_label is not None
        return await self._get_field_value(vault_uuid, item_uuid, field_label)

    async def set_secret(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        # For Connect, we support set_secret only when `path` is a full op:// ref.
        if not path.startswith("op://"):
            raise ValueError(
                "set_secret requires an op:// path in this Connect backend"
            )

        op_ref = parse_op_ref(path)
        if op_ref.field is None:
            raise ValueError("op:// reference must include a field to set")
        # secrets-mcp set_secret expects a JSON object; callers may pass:
        # - {"value": "..."} or {"secret": "..."}
        # - {"apiKey": "..."} (matching op_ref.field)
        # - {"any-single-key": "..."} (single key)
        if "value" in data:
            secret_value = data["value"]
        elif op_ref.field in data:
            secret_value = data[op_ref.field]
        elif len(data) == 1:
            secret_value = next(iter(data.values()))
        else:
            raise ValueError(
                "Connect set_secret expects data to be either {'value': ...}, "
                "{'<fieldLabel>': ...}, or a single-key object"
            )
        vault_uuid = await self._get_vault_uuid(op_ref.vault)
        item_uuid = await self._get_item_uuid(vault_uuid, op_ref.item)

        fields_index = await self._get_item_fields_index(vault_uuid, item_uuid)
        field_uuid = fields_index.get(op_ref.field)
        if not field_uuid:
            raise KeyError(
                f"Connect field UUID not found for field label={op_ref.field}"
            )

        updated = await self._patch_json(
            f"/v1/vaults/{vault_uuid}/items/{item_uuid}",
            {
                "op": "replace",
                "path": f"/fields/{field_uuid}/value",
                "value": secret_value,
            },
        )

        return {
            "updated": True,
            "item": op_ref.item,
            "vault": op_ref.vault,
            "raw": updated,
        }

    async def list_secrets(self, path: str) -> dict[str, Any]:
        # For Connect, interpret `path` as either:
        # - op://<vault>/<item>[/<field>] (list the vault items)
        # - or <vault> (list the vault items)
        vault_name: str
        if path.startswith("op://"):
            op_ref = parse_op_ref(path)
            vault_name = op_ref.vault
        else:
            vault_name = path

        vault_uuid = await self._get_vault_uuid(vault_name)
        items = await self._get_json(f"/v1/vaults/{vault_uuid}/items")
        if not isinstance(items, list):
            return {"vault": vault_name, "items": []}
        titles: list[str] = []
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("title"), str):
                titles.append(item["title"])
        return {"vault": vault_name, "items": titles, "count": len(titles)}

    async def delete_secret(self, path: str) -> dict[str, Any]:
        if not path.startswith("op://"):
            raise ValueError(
                "delete_secret requires an op:// path in this Connect backend"
            )

        op_ref = parse_op_ref(path)
        vault_uuid = await self._get_vault_uuid(op_ref.vault)
        # delete_secret deletes the entire item, since Connect delete is item-scoped.
        item_uuid = await self._get_item_uuid(vault_uuid, op_ref.item)
        await self._delete(f"/v1/vaults/{vault_uuid}/items/{item_uuid}")
        return {"deleted": True, "vault": op_ref.vault, "item": op_ref.item}
