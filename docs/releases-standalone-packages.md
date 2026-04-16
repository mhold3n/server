# Releases: standalone packages and server pins

Standalone libraries are **git-tagged** in their own repos. This monorepo pins those tags in the root [`pyproject.toml`](../pyproject.toml) under `[tool.uv.sources]`.

## Contract

- Tags on `response-control-framework`, `ai-shared-service`, and each `domain-*` repo **match** the `tag = "..."` entries in `pyproject.toml` for the server revision you are building or deploying.
- After changing a pin, run **`uv lock`** (and **`make vendor-rcf-schemas`** when `response-control-framework` schema artifacts changed).

## Release sequence (per package)

1. Merge changes to **`main`** in the standalone repo with **green CI** (thin caller → [`reusable-python-package-ci.yml`](../.github/workflows/reusable-python-package-ci.yml)).
2. Tag with **semver** (e.g. `v0.2.0`) and push the tag (`git tag`, `git push origin v0.2.0`), or create a **GitHub Release** from the tag.
3. Optional: add release notes in that repo’s GitHub Release.
4. In **this** repo: update the corresponding `[tool.uv.sources].<package>.tag`, run `uv lock`, open a PR, merge when CI passes.

## Pinning the reusable CI workflow

Small-repo workflows should use `uses: mhold3n/server/.github/workflows/reusable-python-package-ci.yml@<ref>` with `<ref>` = **tag or commit SHA** on `mhold3n/server`, not a floating `@main`, once the reusable workflow API is stable—see [`docs/dev-environment.md`](dev-environment.md) (“Standalone package repos (shared CI)”).

## Optional: tag-triggered CI

You may add a workflow in a standalone repo that runs tests on `push` of tags; this is secondary to tagging discipline and server lockfile updates.
