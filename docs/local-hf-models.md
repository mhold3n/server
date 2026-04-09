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

### 4. GPU \"no-compromises\" path (Qwen3.5-9B via vLLM)

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

### 5. Toggle mock mode

To run the stack with mock backends instead of real HF models:

```bash
export USE_MOCK_MODELS=true
docker compose -f docker-compose.yml -f compose/docker-compose.local-ai.yml up -d --force-recreate
```

Then:

- `wrkhrs-asr /health` will show `use_mock: true` and `status: "degraded"` with a synthetic transcript from `/transcribe`.
- `wrkhrs-rag /health` will show `use_mock: true` and still allow search using deterministic hash-based embeddings.
