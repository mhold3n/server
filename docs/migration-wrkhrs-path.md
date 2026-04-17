# WrkHrs path migration

The duplicate tree at repository root **`WrkHrs/`** has been removed. The active WrkHrs-derived AI gateway assets, tests, Docker contexts, and Python package live under the **`xlotyl`** product repo:

- **When you keep a sibling xlotyl clone:** `../xlotyl/services/ai-gateway-service/` (or set `XLOTYL_ROOT`).
- **Standalone xlotyl clone:** `services/ai-gateway-service/` at the root of [`mhold3n/xlotyl`](https://github.com/mhold3n/xlotyl)

**Update your bookmarks and scripts:**

- **Editable install from server repo root:**  
  `pip install -e "xlotyl/services/ai-gateway-service[dev]"`  
  or `cd xlotyl/services/ai-gateway-service && pip install -e ".[dev]"`.
- **Editable install from a standalone xlotyl clone:**  
  `pip install -e "services/ai-gateway-service[dev]"` from that repo’s root.
- **CI and local parity:** [`scripts/run_ci_local.sh`](../scripts/run_ci_local.sh) runs pytest and ruff against **`xlotyl/services/ai-gateway-service`** when executed from the server repository root.
- **Compose (server):** [`docker/compose-profiles/docker-compose.ai.yml`](../docker/compose-profiles/docker-compose.ai.yml) pulls **published** WrkHrs-related images (`${XLOTYL_IMAGE_PREFIX}/…:${XLOTYL_VERSION}`) with pins from [`config/xlotyl-images.env`](../config/xlotyl-images.env). For **source** builds of the gateway, use compose from a **xlotyl** checkout (see that repo’s `services/ai-gateway-service/`).

For the broader split between infrastructure (`server`) and the AI product (`xlotyl`), see [`docs/migration/server-xlotyl-boundary-manifest.md`](migration/server-xlotyl-boundary-manifest.md).
