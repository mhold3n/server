# External GitHub repos

This workspace keeps two upstream codebases as Git submodules so they stay tied to their GitHub `main` branches instead of drifting as ad hoc local snapshots:

- `claw-code-main/` → `https://github.com/ultraworkers/claw-code.git`
- `openclaw/` → `https://github.com/openclaw/openclaw.git`

## Refresh

From the repo root:

```bash
npm run deps:external
```

That wrapper calls [`scripts/sync_external_repos.sh`](../scripts/sync_external_repos.sh), which syncs the submodule remotes and updates both checkouts from their configured upstream branches.

## Why submodules instead of raw package-manager GitHub deps?

`openclaw` is consumed in this workspace as a live upstream checkout, but the repo's `main` branch is source-first and does not ship the built package artifacts that downstream plugin installs expect. Tracking the repo as a Git submodule keeps the checkout current without forcing the rest of the workspace onto an unbuilt npm GitHub dependency.

## Inspect the pinned revisions

Use:

```bash
git submodule status
```

That shows the exact commit currently pinned for each external repo in this workspace.

## Interaction model

See [`external-orchestration-interfaces.md`](external-orchestration-interfaces.md) for the control-plane and DevPlane interaction model.
