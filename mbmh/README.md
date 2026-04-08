# Cross-Platform LLM Training + Local Runtime Monorepo

This tree lives inside the Birtha monorepo as `mbmh/`. See [`docs/mbmh.md`](../docs/mbmh.md) for how MBMH relates to the platform (API, worker, Docker, observability).

## Purpose
A single monorepo bridging local model training (SFT, PEFT, continued pretraining) and local runtime serving with isolated layers. Training internals are kept strictly separate from the runtime environment.

## Layer Separation
- **Training**: Defines datasets, trainers, adapters, PEFT logic, and metric collection.
- **Runtime**: Defined as packaged runtime bundles containing manifests. Responsible for local model serving, OpenAI compatibilities, generation routines.
- **Agents**: Config-driven runtime entities representing tools and system prompts.
- **Tools**: Enabled by explicit configuration, bounded to capabilities.
- **Integration**: Adapters for consumer clients (like OpenClaw). See `deploy/openclaw/README.md` and `scripts/emit_openclaw_provider_config.py` to generate OpenClaw `models.providers` from this repo.

## Supported Hardware
- **Apple Silicon** (via MPS Backend)
- **NVIDIA** (via CUDA, FSDP support)
- **CPU** (fallback/smoke test validation)

## Quickstart
Review `docs/runbooks.md` for specific steps. To begin:
1. Bootstrap the focused MBMH env from the repo root: `scripts/bootstrap_tool_env.sh mbmh`
2. Activate it: `source .cache/envs/mbmh/bin/activate`
3. Run the runtime: `python scripts/serve_local.py ...`

## Training Workflow
Executed via `scripts/train_sft.py` or `scripts/train_clm.py`. Reads configs from `configs/` and writes bundled artifacts into `outputs/`.

## Runtime Workflow
Operates out of `outputs/packaged/runtime-bundles`. Executed via `scripts/serve_local.py`. Completely ignorant to deep trainer abstractions.

## Bunldes & Deployment Configs
- Bundles are deposited in `outputs/packaged/runtime-bundles`
- Local Docker and OpenClaw adaptions deploy via `deploy/` directory configurations.
