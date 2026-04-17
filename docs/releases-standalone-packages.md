# Releases: standalone packages and pins

Standalone libraries (`response-control-framework`, `ai-shared-service`, each `domain-*`) are **git-tagged** in **their own repositories**. **[XLOTYL/xlotyl](https://github.com/XLOTYL/xlotyl)** pins those tags (or path deps) for the **product** workspace. The **mhold3n/server** root [`pyproject.toml`](../pyproject.toml) workspaces **MCP servers only**—it does **not** carry those pins; see [xlotyl-and-standalone-packages.md](xlotyl-and-standalone-packages.md) and [packages/README.md](../packages/README.md).

## Contract

- Tags on each standalone repo **match** the pins **consumed by xlotyl** (and any other workspace that depends on them) for the revision you build or deploy.
- After changing a tag in **xlotyl** (or a consuming project), run **`uv lock`** there (and **`make vendor-rcf-schemas`** in xlotyl when `response-control-framework` schema artifacts changed).

## Release sequence (per package)

1. Merge changes to **`main`** in the standalone repo with **green CI** (thin caller → [`reusable-python-package-ci.yml`](../.github/workflows/reusable-python-package-ci.yml)).
2. Tag with **semver** (e.g. `v0.2.0`) and push the tag (`git tag`, `git push origin v0.2.0`), or create a **GitHub Release** from the tag.
3. Optional: add release notes in that repo’s GitHub Release.
4. In **xlotyl** (or the consuming monorepo): bump the corresponding `tag = "..."` / workspace reference, run **`uv lock`**, open a PR, merge when CI passes.

## Pinning the reusable CI workflow

Small-repo workflows should use `uses: mhold3n/server/.github/workflows/reusable-python-package-ci.yml@<ref>` with `<ref>` = **tag or commit SHA** on `mhold3n/server`, not a floating `@main`, once the reusable workflow API is stable—see [`docs/dev-environment.md`](dev-environment.md) (“Standalone package repos (shared CI)”).

## Optional: tag-triggered CI

You may add a workflow in a standalone repo that runs tests on `push` of tags; this is secondary to tagging discipline and consumer lockfile updates.
