from __future__ import annotations

import os
import sys
import types
import unittest
from pathlib import Path


def _install_test_stubs() -> None:
    """Install lightweight stubs for optional runtime deps.

    The dev environment used by this repo may not have `httpx` / `structlog`
    installed in the host Python. These tests avoid those dependencies by
    stubbing them before importing the Connect client module.
    """

    # ---- httpx stub ----
    class FakeResponse:
        def __init__(self, *, status_code: int, payload: object | None = None, content: bytes = b"") -> None:
            self.status_code = status_code
            self._payload = payload
            self.content = content

        def json(self) -> object:
            if self._payload is None:
                return {}
            return self._payload

        def raise_for_status(self) -> None:
            if 400 <= self.status_code:
                raise RuntimeError(f"HTTP {self.status_code}")

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            self.timeout = timeout

        async def aclose(self) -> None:  # noqa: D401 - test stub
            return None

        async def get(self, url: str, *, headers: dict[str, str], params: dict[str, str] | None = None) -> FakeResponse:  # type: ignore[override]
            # ConnectClient uses:
            # - GET {base}/vaults?filter=name eq "<vaultName>"
            # - GET {base}/vaults/{vaultUUID}/items?filter=title eq "<itemTitle>"
            # - GET {base}/vaults/{vaultUUID}/items/{itemUUID} (fields included)
            if url.endswith("/heartbeat"):
                return FakeResponse(status_code=200, payload=None, content=b".")

            if url.endswith("/v1/vaults") and params and "filter" in params:
                return FakeResponse(
                    status_code=200,
                    payload=[{"name": "Personal", "id": "vault-uuid"}],
                )

            if url.endswith("/v1/vaults/vault-uuid/items") and params and "filter" in params:
                return FakeResponse(
                    status_code=200,
                    payload=[{"title": "notion", "id": "item-uuid"}],
                )

            if url.endswith("/v1/vaults/vault-uuid/items/item-uuid"):
                return FakeResponse(
                    status_code=200,
                    payload={
                        "fields": [
                            {"id": "field-uuid", "label": "apiKey", "value": "secret-value"}
                        ]
                    },
                )

            raise AssertionError(f"Unexpected GET {url} params={params}")

        async def patch(self, url: str, *, headers: dict[str, str], json: object) -> FakeResponse:  # type: ignore[override]
            raise AssertionError("set_secret is not exercised in this unit test")

        async def delete(self, url: str, *, headers: dict[str, str]) -> FakeResponse:  # type: ignore[override]
            raise AssertionError("delete_secret is not exercised in this unit test")

    httpx_stub = types.ModuleType("httpx")
    httpx_stub.AsyncClient = FakeAsyncClient  # type: ignore[attr-defined]
    sys.modules["httpx"] = httpx_stub

    # ---- structlog stub ----
    class FakeLogger:
        def exception(self, msg: str) -> None:
            # Keep tests quiet; failures surface via exceptions or assertions.
            return None

    structlog_stub = types.ModuleType("structlog")
    structlog_stub.get_logger = lambda: FakeLogger()  # type: ignore[attr-defined]
    sys.modules["structlog"] = structlog_stub


class TestConnectClientOpRefResolution(unittest.TestCase):
    def setUp(self) -> None:
        # Ensure stubs are present before importing.
        _install_test_stubs()

        os.environ["OP_CONNECT_HOST"] = "http://connect-api:8080"
        os.environ["OP_CONNECT_TOKEN"] = "connect-token"
        os.environ["OP_HTTP_TIMEOUT_SECONDS"] = "10"

        # Import after stubs.
        # The secrets-mcp package is published as the `src` package (see pyproject.toml
        # with `packages = ["src"]`), so we add the server root to sys.path.
        server_root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(server_root))

        from src.connect_client import ConnectClient  # type: ignore

        self.ConnectClient = ConnectClient

    def test_get_secret_op_ref(self) -> None:
        client = self.ConnectClient()
        resolved = self._run_async(client.get_secret("op://Personal/notion/apiKey"))
        self.assertEqual(resolved, "secret-value")

    def test_get_secret_vault_item_plus_key(self) -> None:
        client = self.ConnectClient()
        resolved = self._run_async(client.get_secret("Personal/notion", "apiKey"))
        self.assertEqual(resolved, "secret-value")

    def _run_async(self, coro):  # type: ignore[no-untyped-def]
        # Minimal async runner without external dependencies.
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)


if __name__ == "__main__":
    unittest.main()

