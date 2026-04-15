# External GitHub repos

This workspace keeps two codebases as **Git submodules** pinned to our **forks’** `main` branches (see `.gitmodules`), so Birtha can carry local patches without pointing submodule remotes at third-party default repos:

- `claw-code-main/` → `https://github.com/mhold3n/claw-code.git` (fork of [`ultraworkers/claw-code`](https://github.com/ultraworkers/claw-code))
- `openclaw/` → `https://github.com/mhold3n/openclaw.git` (fork of [`openclaw/openclaw`](https://github.com/openclaw/openclaw))

The `branch = main` entries in `.gitmodules` refer to **`main` on each fork**, not the upstream organizations’ remotes.

Hugging Face and Ollama are intentionally not tracked as source submodules in
this phase. The active stack uses their package dependencies, hosted/local APIs,
and OCI images rather than importing or patching their GitHub source. See
[`ai-runtime-dependencies.md`](ai-runtime-dependencies.md) for the AI runtime
dependency inventory, including pinned Ollama/vLLM image digests and lockfile
tracking.

## Fork and sync (maintainers)

**`openclaw`:** Fork [`openclaw/openclaw`](https://github.com/openclaw/openclaw) → **`mhold3n/openclaw`** (or change `.gitmodules` if your fork URL differs). In the fork, add **`upstream`** → `https://github.com/openclaw/openclaw.git` to pull official releases.

**`claw-code-main`:** Fork [`ultraworkers/claw-code`](https://github.com/ultraworkers/claw-code) → **`mhold3n/claw-code`**. In the fork, add **`upstream`** → `https://github.com/ultraworkers/claw-code.git`.

**Contributors:** After cloning this repo, run `npm run deps:external` (or `git submodule sync --recursive && git submodule update --init --recursive claw-code-main openclaw`) so submodule `origin` URLs match `.gitmodules`.

## Refresh

From the repo root:

```bash
npm run deps:external
```

That wrapper calls [`scripts/sync_external_repos.sh`](../scripts/sync_external_repos.sh), which syncs the submodule remotes and updates both checkouts from the **branches named in `.gitmodules`** on **each submodule’s `origin`** (your forks).

## Why submodules instead of raw package-manager GitHub deps?

`openclaw` is consumed in this workspace as a live checkout, but the repo's `main` branch is source-first and does not ship the built package artifacts that downstream plugin installs expect. Tracking the repo as a Git submodule keeps the checkout current without forcing the rest of the workspace onto an unbuilt npm GitHub dependency.

New source submodules should be added only when this workspace directly imports,
patches, or vendors upstream code. If a Hugging Face or Ollama upstream checkout
ever becomes necessary, record the repo URL, branch or tag, pinned commit,
license note, and update command before relying on it in runtime code.

## Inspect the pinned revisions

Use:

```bash
git submodule status
```

That shows the exact commit currently pinned for each external repo in this workspace.

## Interaction model

See [`external-orchestration-interfaces.md`](external-orchestration-interfaces.md) for the control-plane and DevPlane interaction model.
