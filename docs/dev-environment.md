# Development environment

## Single clone (recommended)

Work from one repository checkout: **[github.com/mhold3n/server](https://github.com/mhold3n/server)**. The monorepo holds the Birtha control plane, the WrkHrs AI stack under [`services/wrkhrs/`](../services/wrkhrs/), MCP servers, MBMH, and shared CI.

Cloning additional “legacy” projects **inside** this repository root increases confusion (two trees, two sets of commands, easy to edit the wrong copy). Prefer:

- **Same machine:** clone other projects under a sibling directory, e.g. `~/work/server` and `~/work/some-other-repo`, not `server/Birtha_bigger_n_badder/`.
- **This repo only:** run CI parity with [`scripts/run_ci_local.sh`](../scripts/run_ci_local.sh) from the repository root.

## Root `.gitignore` and sibling folders

Patterns such as `/Birtha_bigger_n_badder/`, `/Compute_Node_Birtha/`, `/structure/`, and similar entries are **safety rails**: they reduce the chance of accidentally `git add`-ing a large unrelated tree that happens to sit next to your clone. They are **not** required checkouts for developing this repo.

If you keep an old mirror inside the ignored path for personal reference, treat it as **read-only scratch space**; do not treat it as a second source of truth for platform code.

## WrkHrs location

The vendored WrkHrs stack lives only under **`services/wrkhrs/`**. Historical links to `WrkHrs/` at the repository root are obsolete; see [migration-wrkhrs-path.md](migration-wrkhrs-path.md).
