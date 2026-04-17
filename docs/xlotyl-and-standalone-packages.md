# Xlotyl vs standalone domain packages (source of truth)

## Summary

- **[XLOTYL/xlotyl](https://github.com/XLOTYL/xlotyl)** is the **canonical product repo** for the AI stack: `services/*` (including `services/domain-*`, `services/response-control-framework`, `services/ai-shared-service` as checked out there), wiki, orchestration sources, and **dependency pins** in that repo’s workspace.
- **Standalone GitHub repos** (`mhold3n/response-control-framework`, `mhold3n/domain-*`, `mhold3n/ai-shared-service`) exist so each library can be **versioned**, **tagged**, and **CI-tested** independently, with workflows **calling** [`reusable-python-package-ci.yml`](../.github/workflows/reusable-python-package-ci.yml) from **this** infra repo.

## Dependency direction

- **mhold3n/server** provides **reusable CI** and **infrastructure**; it does **not** need to embed all domain package sources to be the system of record for “how the server runs.”
- **xlotyl** consumes tagged releases of those libraries (or path/workspace deps during development) per its own `pyproject.toml` / layout.
- Avoid maintaining **two divergent copies** of the same package: prefer **one editing workflow** (either develop in the standalone repo and bump pins in xlotyl, or develop in xlotyl’s tree if your team uses subtree/submodule—pick one policy and document it in xlotyl).

## Related

- [repository-content-model.md](repository-content-model.md)
- [releases-standalone-packages.md](releases-standalone-packages.md)
- Migration context: [migration/server-xlotyl-boundary-manifest.md](migration/server-xlotyl-boundary-manifest.md)
