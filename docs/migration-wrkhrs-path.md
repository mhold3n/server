# WrkHrs path migration

The duplicate tree at repository root **`WrkHrs/`** has been removed. The active WrkHrs-derived AI gateway assets, tests, Docker contexts, and Python package now live under **`services/ai-gateway-service/`**.

**Update your bookmarks and scripts:**

- Editable install: `pip install -e "services/ai-gateway-service[dev]"` from the repo root, or `cd services/ai-gateway-service && pip install -e ".[dev]"`.
- CI and [`scripts/run_ci_local.sh`](../scripts/run_ci_local.sh) use `services/ai-gateway-service` for pytest and coverage.
- [`docker/compose-profiles/docker-compose.ai.yml`](../docker/compose-profiles/docker-compose.ai.yml) uses `./services/ai-gateway-service` as the active build context.
