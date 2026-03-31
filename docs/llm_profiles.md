## LLM Profiles: GPU vs Apple Silicon

Birtha's orchestration stack can talk to different LLM backends behind the **same OpenAI-compatible API**. Profiles let you switch backends without touching router logic, task cards, or RAG:

- **`gpu` (no compromises)**: Qwen3.5-9B served via vLLM on an NVIDIA GPU Linux host.
- **`apple` (local dev)**: Apple Silicon–friendly worker running on the laptop, used to develop and debug orchestration + RAG flows.

The active profile is controlled by:

```bash
ORCH_PROFILE=gpu   # or apple
```

and resolved in `services/api/src/config.py:get_worker_settings()`. The router always calls the API’s `/v1/chat/completions`; only the worker URL + default model change.

### GPU profile (`gpu`)

- **Worker**: vLLM (`qwen-vllm` service) exposing `http://qwen-vllm:8000/v1`.
- **Default model**: `Qwen/Qwen3.5-9B`.
- **How to run**:

```bash
cd Birtha_bigger_n_badder/worker/vllm
docker compose -f docker-compose.vllm.yml up -d
```

In `.env`:

```bash
ORCH_PROFILE=gpu
OPENAI_BASE_URL=http://qwen-vllm:8000/v1    # or http://gpu-host:8000/v1
```

### Apple Silicon profile (`apple`)

For Apple, we lean on an existing OpenAI-compatible server (for example **llama.cpp** with `--server` and OpenAI API enabled) and simply point the orchestrator at it.

- **Worker**: any Apple-capable model server exposing:

```text
POST /v1/chat/completions
GET  /v1/models
```

on `http://localhost:8000`.

- **How to run (example with llama.cpp)**:

```bash
# Build llama.cpp with server + OpenAI API support (see llama.cpp docs),
# then run a quantized model that fits your M1
./server --model /path/to/model.gguf \
  --host 0.0.0.0 \
  --port 8000 \
  --api-openai
```

Then in the orchestrator `.env`:

```bash
ORCH_PROFILE=apple
OPENAI_BASE_URL=http://host.docker.internal:8000/v1
```

With this configuration:

- `get_worker_settings()` resolves:
  - `base_url` → `http://host.docker.internal:8000/v1`
  - `default_model` → `"local-llm-apple"` (you can override per-request).
- Router + task cards still call `/v1/chat/completions` via the API; only the backing model/host changes.

### Verifying profile wiring

1. Start the appropriate worker (GPU vLLM or Apple local server).
2. Set `ORCH_PROFILE` and `OPENAI_BASE_URL` in `.env`.
3. Restart API + router:

```bash
cd Birtha_bigger_n_badder
docker compose -p agent-orchestrator --env-file .env up -d api router
```

4. Hit:

```bash
curl -s http://localhost:8080/api/ai/status | jq
```

You should see:

- `qwen.reachable: true`
- `worker.status: "healthy"`
- `profile` and `worker_base_url` (once added in the status payload).

