# WrkHrs path migration

The duplicate tree at repository root **`WrkHrs/`** has been removed. All WrkHrs assets, tests, Docker contexts, and the `wrkhrs` Python package now live exclusively under **`services/wrkhrs/`**.

**Update your bookmarks and scripts:**

- Editable install: `pip install -e "services/wrkhrs[dev]"` from the repo root (or `cd services/wrkhrs && pip install -e ".[dev]"`).
- CI and [`scripts/run_ci_local.sh`](../scripts/run_ci_local.sh) use `services/wrkhrs` for pytest and coverage.
- [`docker-compose.ai.yml`](../docker-compose.ai.yml) build contexts already pointed at `./services/wrkhrs`; no compose change was required for this migration.
