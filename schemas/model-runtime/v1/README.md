# Model runtime JSON Schemas (v1)

Draft 2020-12 contracts merged with control-plane `common.schema.json` for `$ref` resolution. Canonical `$id` prefix: `https://birtha.local/schemas/model-runtime/v1/`.

| File | Purpose |
|------|---------|
| `registry.json` | Manifest for CI / `schema_store` |
| `mr-common.schema.json` | Shared `$defs` (delegates uuid/artifactRef to control-plane common) |
| `orchestration_packet.schema.json` | `POST /infer/general` body (`packet_class` = `ORCHESTRATION`) |
| `solve_mechanics_request_v1.schema.json` | `POST /solve/mechanics` body (engineering-core rigid block v1) |
| `fixtures/orchestration_packet/*.json` | Golden orchestration packets |
| `fixtures/solve_mechanics_request_v1/*.json` | Golden solve requests |

Run gate from repo root:

```bash
python scripts/validate_model_runtime_schemas.py
```
