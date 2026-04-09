# Development environment

## Single clone (recommended)

Work from one repository checkout: **[github.com/mhold3n/server](https://github.com/mhold3n/server)**. The active repo holds the Birtha control plane, the WrkHrs AI stack under [`services/wrkhrs/`](../services/wrkhrs/), MCP servers, and shared CI. Legacy MBMH training/runtime materials now live in the sibling local archive at `../server-local-archive/2026-04-08/server/`.

Cloning additional “legacy” projects **inside** this repository root increases confusion (two trees, two sets of commands, easy to edit the wrong copy). Prefer:

- **Same machine:** clone other projects under a sibling directory, e.g. `~/work/server` and `~/work/some-other-repo`, not inside `server/`.
- **This repo only:** run CI parity with [`scripts/run_ci_local.sh`](../scripts/run_ci_local.sh) from the repository root.

## Workspace bootstrap

- Main Python workspace: `uv sync --python 3.11`
- Main Node workspace: `npm install`
- Focused tool envs: `scripts/bootstrap_tool_env.sh marker-pdf|whisper-asr|qwen-runtime|larrak-audio`
- Shared local caches and model state live under `./.cache/`

## Root `.gitignore` and sibling folders

Patterns for ignored sibling scratch trees are **safety rails**: they reduce the chance of accidentally `git add`-ing a large unrelated tree that happens to sit next to your clone. They are **not** required checkouts for developing this repo.

If you keep an old mirror inside the ignored path for personal reference, treat it as **read-only scratch space**; do not treat it as a second source of truth for platform code.

## WrkHrs location

The vendored WrkHrs stack lives only under **`services/wrkhrs/`**. Historical links to `WrkHrs/` at the repository root are obsolete; see [migration-wrkhrs-path.md](migration-wrkhrs-path.md).
