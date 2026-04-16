# WrkHrs path migration

The duplicate tree at repository root **`WrkHrs/`** has been removed. The active WrkHrs-derived AI gateway assets, tests, Docker contexts, and Python package live under the **`xlotyl`** product repo:

- **In this monorepo (server checkout):** [`xlotyl/services/ai-gateway-service/`](../xlotyl/services/ai-gateway-service/)
- **Standalone xlotyl clone:** `services/ai-gateway-service/` at the root of [`mhold3n/xlotyl`](https://github.com/mhold3n/xlotyl)

**Update your bookmarks and scripts:**

- **Editable install from server repo root:**  
  `pip install -e "xlotyl/services/ai-gateway-service[dev]"`  
  or `cd xlotyl/services/ai-gateway-service && pip install -e ".[dev]"`.
- **Editable install from a standalone xlotyl clone:**  
  `pip install -e "services/ai-gateway-service[dev]"` from that repo’s root.
- **CI and local parity:** [`scripts/run_ci_local.sh`](../scripts/run_ci_local.sh) runs pytest and ruff against **`xlotyl/services/ai-gateway-service`** when executed from the server repository root.
- **Compose:** [`docker/compose-profiles/docker-compose.ai.yml`](../docker/compose-profiles/docker-compose.ai.yml) uses **`./xlotyl/services/ai-gateway-service`** as the build context (paths relative to the **server** repo root).

For the broader split between infrastructure (`server`) and the AI product (`xlotyl`), see [`docs/migration/server-xlotyl-boundary-manifest.md`](migration/server-xlotyl-boundary-manifest.md).
