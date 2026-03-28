"""Lightweight async Proxmox API client for VM management.

Scaffolded to support listing VMs and starting/stopping them. Uses
token-based authentication and targets the JSON API.
"""

from __future__ import annotations

from typing import Any

import httpx


class ProxmoxClient:
    def __init__(
        self,
        base_url: str,
        token_id: str | None,
        token_secret: str | None,
        *,
        verify_ssl: bool = True,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token_id = token_id
        self.token_secret = token_secret
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> ProxmoxClient:
        self._client = httpx.AsyncClient(verify=self.verify_ssl, timeout=self.timeout)
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> dict[str, str]:
        # Proxmox API token header format
        # Authorization: PVEAPIToken=<token-id>=<token-secret>
        if self.token_id and self.token_secret:
            return {"Authorization": f"PVEAPIToken={self.token_id}={self.token_secret}"}
        return {}

    async def list_vms(self) -> list[dict[str, Any]]:
        """Return a simplified list of VMs/LXCs from cluster resources."""
        assert self._client is not None, "Client not started"
        url = f"{self.base_url}/api2/json/cluster/resources"
        resp = await self._client.get(url, params={"type": "vm"}, headers=self._headers())
        resp.raise_for_status()
        payload = resp.json()
        items: list[dict[str, Any]] = payload.get("data", [])

        result: list[dict[str, Any]] = []
        for it in items:
            result.append(
                {
                    "id": it.get("vmid"),
                    "name": it.get("name"),
                    "node": it.get("node"),
                    "status": it.get("status"),
                    "type": it.get("type", "qemu"),
                    "uptime": it.get("uptime"),
                    "mem": it.get("maxmem"),
                    "cpu": it.get("maxcpu"),
                }
            )
        return result

    async def _find_vm(self, vmid: int) -> tuple[str, str]:
        """Find the node and type for a given VMID.

        Returns (node, type), where type is usually 'qemu' or 'lxc'.
        """
        vms = await self.list_vms()
        for vm in vms:
            if int(vm.get("id")) == int(vmid):
                node = str(vm.get("node"))
                vm_type = str(vm.get("type", "qemu"))
                return node, vm_type
        raise ValueError(f"VMID {vmid} not found")

    async def start_vm(self, vmid: int) -> dict[str, Any]:
        """Start a VM or LXC by VMID."""
        assert self._client is not None, "Client not started"
        node, vm_type = await self._find_vm(vmid)
        url = f"{self.base_url}/api2/json/nodes/{node}/{vm_type}/{vmid}/status/start"
        resp = await self._client.post(url, headers=self._headers())
        resp.raise_for_status()
        return {"status": "started", "vmid": vmid, "node": node, "type": vm_type}

    async def stop_vm(self, vmid: int) -> dict[str, Any]:
        """Stop a VM or LXC by VMID."""
        assert self._client is not None, "Client not started"
        node, vm_type = await self._find_vm(vmid)
        url = f"{self.base_url}/api2/json/nodes/{node}/{vm_type}/{vmid}/status/stop"
        resp = await self._client.post(url, headers=self._headers())
        resp.raise_for_status()
        return {"status": "stopped", "vmid": vmid, "node": node, "type": vm_type}

