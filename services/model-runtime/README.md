# model-runtime

Single Python process: **strict** `POST /infer/general`, `/infer/coding`, `/infer/multimodal`, and **`POST /solve/mechanics`** (delegates to `engineering-core`). Default bind **`127.0.0.1`**.

## Config

- `MODEL_RUNTIME_CONFIG_PATH` — YAML path (default: `config/models.yaml` next to this package).
- Set `local_model_path` per role after download for offline `local_files_only=True` loading.

## Download weights (operator)

```bash
python -m venv .venv-models
source .venv-models/bin/activate
pip install torch transformers accelerate huggingface_hub qwen-vl-utils fastapi uvicorn pydantic pyyaml jsonschema
hf auth login
hf download Qwen/Qwen3-4B --local-dir ./models/Qwen3-4B
# ... set local_model_path in YAML
```

## Run

```bash
cd services/model-runtime
pip install -e ".[dev]"
MODEL_RUNTIME_HOST=127.0.0.1 MODEL_RUNTIME_PORT=8765 python -m model_runtime.main
```

## v1 behavior

- **`/infer/general`**: validates `orchestration_packet` JSON Schema + `workflow_root` query (see below).
- **`MOCK_INFER=1`**: returns deterministic stub text (CI) without loading torch.

### `workflow_root` query parameter

`parent_packet_id` may be `null` **only** when `workflow_root=true`. Descendant packets must send `workflow_root=false` and non-null `parent_packet_id` or receive **422**.

## Tests

```bash
pytest tests/ -q
```

`RUN_MODEL_SMOKE=1` reserved for future GPU smokes (optional).
