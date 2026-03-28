# MBMH (training and local runtime)

This repository’s **MBMH** tree lives at [`mbmh/`](../mbmh/). It is the authoritative, cross-platform **LLM training** environment (SFT, PEFT, continued pretraining) and **local OpenAI-compatible runtime** (`serve_local.py`), including OpenClaw-oriented wiring under `mbmh/deploy/openclaw/`.

The rest of this repo (services, worker, Docker, observability) is the **platform scaffolding** that runs in production; MBMH is where you train, package runtime bundles, and run the local inference surface used by adapters like OpenClaw.

Quick start:

1. `cd mbmh`
2. Follow [`mbmh/README.md`](../mbmh/README.md) and [`mbmh/docs/runbooks.md`](../mbmh/docs/runbooks.md) as needed.

The historical GitHub repo **MBMH-Training** was a stub; development now happens here under `mbmh/`.
