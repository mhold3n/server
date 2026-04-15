## LLM Profiles: GPU vs Apple Silicon

Birtha's orchestration stack can talk to different LLM backends behind the **same OpenAI-compatible API**. Profiles let you switch backends without touching router logic, task cards, or RAG:

- **`gpu` (no compromises)**: Qwen3.5-9B served via vLLM on an NVIDIA GPU Linux host.
- **`apple` (local dev)**: Apple Silicon–friendly worker running on the laptop, used to develop and debug orchestration + RAG flows.

The active profile is controlled by:

```bash
ORCH_PROFILE=gpu   # or apple
```

and resolved in `services/api-service/src/config.py:get_worker_settings()`. The router always calls the API's `/v1/chat/completions`; only the worker URL + default model change.

### GPU profile (`gpu`)

- **Worker**: vLLM (`qwen-vllm` service) exposing `http://qwen-vllm:8000/v1`.
- **Default model**: `Qwen/Qwen3.5-9B`.
- **How to run**:

```bash
cd /path/to/server
docker compose --project-directory "$(pwd)" -f worker/vllm/docker-compose.vllm.yml up -d
```

In `.env`:

```bash
ORCH_PROFILE=gpu
OPENAI_BASE_URL=http://qwen-vllm:8000/v1    # or http://gpu-host:8000/v1
```

### WrkHrs agent-platform + host Ollama (recommended on Apple Silicon)

The default full dev stack runs **wrkhrs-agent-platform** (LangGraph / open-multi-agent), not only the Python API worker. For accelerated inference on Apple Silicon, run **[Ollama](https://ollama.com)** on the host and wire the platform to its **native** HTTP API (containers reach the Mac via `host.docker.internal`; see `wrkhrs-agent-platform` `extra_hosts` in [`docker/compose-profiles/docker-compose.ai.yml`](../docker/compose-profiles/docker-compose.ai.yml)). **Use the Qwen lane**, not ad-hoc Llama defaults: pull **`qwen3:4b-instruct`** (Ollama) as the counterpart to **`Qwen/Qwen3-4B`** in [`docker-compose.local-ai.yml`](../docker/compose-profiles/docker-compose.local-ai.yml).

```bash
LLM_BACKEND=ollama
LLM_RUNNER_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen3:4b-instruct
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
```

[`dev/scripts/fullstack_e2e_bootstrap.sh`](../dev/scripts/fullstack_e2e_bootstrap.sh) and [`dev/scripts/e2e_stack_up.sh`](../dev/scripts/e2e_stack_up.sh) set these automatically on Darwin arm64 (preflight: `ollama` + `/api/tags`); see [dev-environment.md — fullstack e2e](dev-environment.md#one-shot-fullstack-e2e-docker--openclaw--checks). This is separate from `ORCH_PROFILE=apple` below, which configures `get_worker_settings()` for the Python API’s worker URL and default model.

### Apple Silicon profile (`apple`)

For Apple, we lean on an existing OpenAI-compatible server (for example **Ollama**’s `/v1` shim, or **llama.cpp** with `--server` and OpenAI API enabled) and point the Python API worker profile at it.

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
cd /path/to/server
docker compose --project-directory "$(pwd)" -f docker-compose.yml --env-file .env up -d api router
```

4. Hit:

```bash
curl -s http://localhost:8080/api/ai/status | jq
```

You should see:

- `qwen.reachable: true`
- `worker.status: "healthy"`
- `profile` and `worker_base_url` (once added in the status payload).
