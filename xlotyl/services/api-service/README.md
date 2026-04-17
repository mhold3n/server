# api-service — tool-model lane (reference)

This package is a **reference implementation** of `POST /api/ai/tool-query` for the OpenClaw **tool-model lane**. Integrate into the production **`xlotyl` product repository** by copying `birtha_tool_model/` and wiring `get_tool_query_router()` into the FastAPI app.

- **Schemas:** [`../../schemas/openclaw-bridge/v1/tool-model/`](../../schemas/openclaw-bridge/v1/tool-model/)
- **Registry:** [`../../schemas/openclaw-bridge/v1/registry.v1.json`](../../schemas/openclaw-bridge/v1/registry.v1.json)
- **ADR:** [`../../../../docs/adr/0002-openclaw-tool-model-lane.md`](../../../../docs/adr/0002-openclaw-tool-model-lane.md)

## Environment

| Variable | Purpose |
|----------|---------|
| `BIRTHA_TOOL_MODEL_REGISTRY_PATH` | Override path to `registry.v1.json` |
| `BIRTHA_TOOL_MODEL_MOCK` | If `1`, return a deterministic structured result for class B (tests / dev only) |
| `BIRTHA_TOOL_MODEL_LANE` | Log label (default `tool_model`) |

## Tests

From `xlotyl/services/api-service`:

```bash
uv sync --extra dev  # or pip install -e ".[dev]"
pytest -q
```
