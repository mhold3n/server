# AI Runtime Dependency Inventory

This inventory records how Hugging Face, Ollama, vLLM, and related AI runtime
dependencies are tracked in this workspace.

## Dependency Policy

- Package managers and lockfiles are canonical for library dependencies.
- OCI image references are pinned by digest for runtime containers that execute
  model servers.
- Git submodules are used only when this repo imports, patches, or vendors
  upstream source directly.
- Hugging Face and Ollama upstream source repositories are not submodules in
  this phase because the active stack consumes their packages, APIs, and images
  rather than importing or patching their source trees.

## Runtime Images

| Runtime | Default image reference | Tracking mechanism | Override |
| --- | --- | --- | --- |
| Ollama | `ollama/ollama@sha256:1375516e575632dd84ad23b2c1cbd5e36ef34ebe8e41f9857545ab9aa72aeec2` | OCI digest in compose and env examples | `OLLAMA_IMAGE` |
| vLLM OpenAI server | `vllm/vllm-openai@sha256:7a0f0fdd2771464b6976625c2b2d5dd46f566aa00fbc53eceab86ef50883da90` | OCI digest in compose and env examples | `VLLM_IMAGE` |

These digests pin the Linux amd64 runtime images used by the worker compose
profiles. If a different platform image is required, resolve the digest for
that platform and update this inventory, `.env.example`, and the relevant
compose files in the same change.

## Python Packages

| Area | Packages | Tracking mechanism |
| --- | --- | --- |
| RAG local embeddings | `sentence-transformers`, `torch`, `transformers` transitive stack | root `pyproject.toml` and `uv.lock` |
| Model runtime HF mode | `transformers`, `torch`, `accelerate` via `services/model-runtime[hf]` | `services/model-runtime/pyproject.toml` and `uv.lock` |
| HF Hub downloads | `huggingface-hub` transitive package | `uv.lock` |
| Reranking integration | HTTP client only in this phase | existing package lock for `httpx` |

`MODEL_RUNTIME_CONFIG_PATH` points at `services/model-runtime/config/models.yaml`.
Each role may use `local_model_path` for offline loading; when that path is set,
the runtime loads with `local_files_only=True`.

## Node Packages

| Area | Packages | Tracking mechanism |
| --- | --- | --- |
| OpenMultiAgent provider adapters | TypeScript source in `merged claude leak/packages/open-multi-agent` | root `package-lock.json` workspace lock |
| Agent-platform orchestration | TypeScript source in `services/agent-platform/server` | root `package-lock.json` workspace lock |

The hosted Hugging Face route uses the existing OpenAI-compatible adapter with
`baseURL=https://router.huggingface.co/v1` and auth from `HF_TOKEN` or
`HUGGINGFACE_HUB_TOKEN`. Native Ollama chat uses Ollama `/api/chat` in the local
OpenMultiAgent adapter; OpenAI-compatible `/v1` remains only a fallback shape for
non-tool chat paths that explicitly select an OpenAI-compatible base URL.

## Existing Source Submodules

| Submodule | Upstream | Why tracked as source |
| --- | --- | --- |
| `claw-code-main/` | `https://github.com/ultraworkers/claw-code.git` | External coding operator/client surface |
| `openclaw/` | `https://github.com/openclaw/openclaw.git` | External orchestration/operator surface |

Use `git submodule status` to inspect the pinned commits.

## Adding A Source Dependency

Do not add Hugging Face or Ollama upstream repos as submodules unless active
server code directly imports, patches, or vendors their source. If that changes,
record all of the following in this file and `docs/external-repos.md`:

- GitHub repository URL.
- Branch or tag.
- Pinned commit.
- License note.
- Update command.
- Reason package, API, or OCI tracking is insufficient.
