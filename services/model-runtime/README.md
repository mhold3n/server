# model-runtime

Single Python process: **strict** `POST /infer/general`, `/infer/coding`, `/infer/multimodal`, and **`POST /solve/mechanics`** (delegates to `engineering-core`). Default bind **`127.0.0.1`**.

## Agent-platform integration (v1)

- **`wrkhrs-agent-platform`** uses **`MODEL_RUNTIME_URL`** and calls **`POST /infer/multimodal`** for executor **`multimodal_model`** only.
- **`/infer/general`** and **`/infer/coding`** are **not** wired into the TS orchestration graph today; they remain for **schema-validated HTTP**, tests, and **future** routing (e.g. local Qwen for general/coding).

## HF backends

- **`general`** / **`coding`**: causal LMs (`AutoModelForCausalLM` + tokenizer chat template).
- **`multimodal`**: **Qwen2.5-VL** (`Qwen2_5_VLForConditionalGeneration` + `AutoProcessor`). v1 uses **text-only** chat blocks; artifact-resolved images are a follow-up (control-plane `task_packet` is `additionalProperties: false`).

## Config

- `MODEL_RUNTIME_CONFIG_PATH` — YAML path (default: `config/models.yaml` next to this package).
- Set `local_model_path` per role after download for offline `local_files_only=True` loading.

## Download weights (operator)

```bash
scripts/bootstrap_tool_env.sh qwen-runtime
source .cache/envs/qwen-runtime/bin/activate
hf auth login
hf download Qwen/Qwen3-4B --local-dir ./.cache/models/Qwen3-4B
# ... set local_model_path in YAML
```

## Run

```bash
uv sync --python 3.11
cd services/model-runtime
MODEL_RUNTIME_HOST=127.0.0.1 MODEL_RUNTIME_PORT=8765 uv run --package model-runtime python -m model_runtime.main
```

## v1 behavior

- **`/infer/general`**: validates `orchestration_packet` JSON Schema + `workflow_root` query (see below).
- **`MOCK_INFER=1`**: returns deterministic stub text (CI) without loading torch.

### `workflow_root` query parameter

`parent_packet_id` may be `null` **only** when `workflow_root=true`. Descendant packets must send `workflow_root=false` and non-null `parent_packet_id` or receive **422**.

## Smoke (HTTP)

From repo root (with `model-runtime` listening on the host-mapped port, default **8765**):

```bash
make smoke-model-runtime-hf
# or: bash dev/scripts/smoke_model_runtime_hf.sh
```

See [local-hf-models.md](../../docs/local-hf-models.md) §4 and §4c for real HF (`MOCK_INFER=0`) and CI behaviour.

## Tests

```bash
pytest tests/ -q
```

**`RUN_MODEL_SMOKE=1`**: opt-in local transformer smoke in [`tests/test_smoke_placeholder.py`](tests/test_smoke_placeholder.py). Set **`MODEL_RUNTIME_GENERAL_LOCAL_PATH`** to a directory with a **general-role** causal model snapshot (same role as `models.yaml` key `general`), or **`MODEL_RUNTIME_LOCAL_PATH_GENERAL`** as an accepted alias. This does not start the HTTP server; it only validates an offline load + tiny `generate` call.

**CI:** Root [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) does not install `model-runtime[hf]` today (torch size). Repo-wide Python gates can be extended later with a **`RUN_MODEL_SMOKE`** or Docker-based job on a self-hosted runner with HF cache.
