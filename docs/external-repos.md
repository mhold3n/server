# External GitHub repos

This **infrastructure** repository does **not** vendor the AI product or OpenClaw as submodules.

- **AI stack (api-service, router, WrkHrs, domains, model-runtime, schemas):** [XLOTYL/xlotyl](https://github.com/XLOTYL/xlotyl) — developed and released independently; consumed here as **OCI images** whose registry prefix and tag are pinned in [`config/xlotyl-images.env`](../config/xlotyl-images.env) (`XLOTYL_IMAGE_PREFIX`, `XLOTYL_VERSION`; today often `ghcr.io/mhold3n` until the product repo is transferred to the **XLOTYL** org).
- **OpenClaw, claw-code, void:** tracked as **submodules inside the xlotyl repo**, not in server. After cloning [XLOTYL/xlotyl](https://github.com/XLOTYL/xlotyl), run `git submodule update --init --recursive`.

Hugging Face and Ollama are not tracked as source submodules in this repo. See [`ai-runtime-dependencies.md`](ai-runtime-dependencies.md) for pinned Ollama/vLLM image digests.

## Local development

Clone the xlotyl product repo beside this repository (sibling `../xlotyl`) when you need Python/Node sources, OpenClaw, or orchestration wiki tooling. Compose and Makefile targets that delegate to xlotyl use `XLOTYL_ROOT` (default `../xlotyl`).

## Interaction model

See [`external-orchestration-interfaces.md`](external-orchestration-interfaces.md) for the control-plane and DevPlane interaction model (URLs and contracts only; no AI source paths in this repo).
