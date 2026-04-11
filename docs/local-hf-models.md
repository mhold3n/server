## Local Hugging Face Models – RAG & ASR

This document describes how to verify that the local `server` stack is using offline Hugging Face models via the shared cache.

### Prerequisites

- `.env` in the project root has:
  - `HF_HOME=./.cache/models/hf`
  - `MODEL_CACHE_DIR=./.cache/models/hf`
  - `EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2`
  - `ASR_MODEL=Systran/faster-whisper-small`
- Models are pre-cached into `./.cache/models/hf` using a focused tool env such as `scripts/bootstrap_tool_env.sh whisper-asr` or `scripts/bootstrap_tool_env.sh qwen-runtime`.

### 1. Start the local AI stack (Apple / dev profile)

```bash
cd /path/to/server
docker compose -f docker-compose.yml -f compose/docker-compose.local-ai.yml up -d
```

Key services:

- RAG worker: `wrkhrs-rag` on `http://localhost:8082`
- ASR worker: `wrkhrs-asr` on `http://localhost:8084`
- Model runtime: `model-runtime` on `http://localhost:${MODEL_RUNTIME_PORT:-8765}`

### 2. Verify ASR uses the local Systran model

Health check:

```bash
curl -s http://localhost:8084/health | jq
```

Expected fields:

- `status`: `"healthy"` once the model is loaded.
- `model_loaded`: `true`
- `model_size`: `"Systran/faster-whisper-small"`
- `use_mock`: `false`

Test transcription with a small audio file:

```bash
curl -s -X POST "http://localhost:8084/transcribe/file" \
  -F "file=@/path/to/sample.wav" \
  -F "language=auto" \
  -F "extract_technical=true" | jq
```

Expected:

- HTTP 200.
- Non-empty `transcript`.
- Reasonable `segments` and `technical_segments`.

### 3. Verify RAG uses local MiniLM embeddings

Health check:

```bash
curl -s http://localhost:8082/health | jq
```

Expected fields:

- `status`: `"healthy"`
- `embedding_model_loaded`: `true` (when using local embeddings)
- `embedding_model_name`: `"sentence-transformers/all-MiniLM-L6-v2"`
- `embedding_backend`: `"local"` for SentenceTransformer, `"ollama"` for Ollama
  `/api/embed`, `"openai"` for OpenAI-compatible remote embeddings, or `"mock"`
  for deterministic test embeddings.
- `reranker_configured`: `true` when `RERANKER_URL` is set.
- `use_mock`: `false`

Ingest a simple document:

```bash
curl -s -X POST "http://localhost:8082/documents" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Graphene is a two-dimensional form of carbon with remarkable electrical properties.",
    "metadata": {"source": "local-doc"},
    "domain": "materials"
  }' | jq
```

Expected:

- HTTP 200.
- `chunks_created` > 0.

Run a RAG query:

```bash
curl -s -X POST "http://localhost:8082/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is special about graphene?",
    "domain_weights": {"materials": 1.0},
    "k": 3
  }' | jq
```

Expected:

- HTTP 200.
- `results` list with at least one entry mentioning graphene.

### Remote embedding variants

Use a local OpenAI-compatible embedding endpoint:

```bash
EMBEDDING_BACKEND=openai
EMBEDDING_ENDPOINT_URL=http://embedding-worker:8000/v1/embeddings
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

Use Ollama native embeddings:

```bash
EMBEDDING_BACKEND=ollama
EMBEDDING_ENDPOINT_URL=http://llm-runner:11434
EMBEDDING_MODEL=nomic-embed-text
```

When `EMBEDDING_BACKEND=auto`, the RAG service treats endpoints ending in
`/api/embed` or containing port `11434` as Ollama and otherwise assumes an
OpenAI-compatible embeddings API.

### Optional reranking

Set `RERANKER_URL` to a service exposing `POST /rerank` with
`{"query": "...", "documents": [...], "top_k": N}`. Search responses expose
`reranking_method`; if the reranker fails, the service logs a warning and falls
back to the current BM25 plus embedding score.

### 4. Model-runtime HF mode

Dev compose defaults `MOCK_INFER=1`, so `/infer/*` endpoints return deterministic
mock envelopes without loading large models. To smoke test real local HF
generation:

```bash
export MOCK_INFER=0
export MODEL_RUNTIME_CONFIG_PATH=/app/services/model-runtime/config/models.yaml
export HF_HOME=./.cache/models/hf
export TRANSFORMERS_CACHE=./.cache/models/hf
export MODEL_CACHE_DIR=./.cache/models/hf
docker compose -f docker-compose.yml -f compose/docker-compose.ai.yml up -d model-runtime
curl -s http://localhost:${MODEL_RUNTIME_PORT:-8765}/health | jq
```

For offline loading, set `local_model_path` in
`services/model-runtime/config/models.yaml`; model-runtime then calls
Transformers with `local_files_only=True`.

### 5. Hosted Hugging Face route

Hosted HF chat uses the OpenAI-compatible router:

```bash
LLM_BACKEND=huggingface
HF_INFERENCE_BASE_URL=https://router.huggingface.co/v1
HF_INFERENCE_MODEL=Qwen/Qwen3-8B
HF_TOKEN=...
```

The public API accepts `provider: "huggingface"` as a routing hint, but raw
provider API keys are not accepted in request bodies.

### 6. GPU \"no-compromises\" path (Qwen3.5-9B via vLLM)

When you have access to an NVIDIA GPU Linux host and want the full Qwen3.5-9B model, run the vLLM worker and point the orchestrator at it:

```bash
cd /path/to/server/worker/vllm
docker compose -f docker-compose.vllm.yml up -d
```

Then set, in the orchestrator `.env`:

```bash
ORCH_PROFILE=gpu
OPENAI_BASE_URL=http://qwen-vllm:8000/v1  # if API is on same Docker network
```

or, for a remote GPU box:

```bash
ORCH_PROFILE=gpu
OPENAI_BASE_URL=http://gpu-hostname-or-ip:8000/v1
```

The router and task cards will continue to hit `/v1/chat/completions` via the API; only the worker URL and default model change per profile.

### 7. Toggle mock mode

To run the stack with mock backends instead of real HF models:

```bash
export USE_MOCK_MODELS=true
docker compose -f docker-compose.yml -f compose/docker-compose.local-ai.yml up -d --force-recreate
```

Then:

- `wrkhrs-asr /health` will show `use_mock: true` and `status: "degraded"` with a synthetic transcript from `/transcribe`.
- `wrkhrs-rag /health` will show `use_mock: true` and still allow search using deterministic hash-based embeddings.
