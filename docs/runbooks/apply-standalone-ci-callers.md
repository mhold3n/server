# Apply thin CI callers to standalone repos

Use this after [`reusable-python-package-ci.yml`](../../.github/workflows/reusable-python-package-ci.yml) is on **`mhold3n/server`** `main` (or a release tag).

## 1. Choose `SERVER_REF`

Replace the placeholder `SERVER_REF` in the template YAML with either:

- A **commit SHA** on `mhold3n/server` that contains the reusable workflow (stable for months), or
- A **tag** on `mhold3n/server` you maintain for workflow API stability (e.g. `v2026.04.15`).

Avoid bare `@main` for production callers if you want server `main` refactors not to break small repos unexpectedly.

## 2. Copy per-repo templates

Templates live in [`docs/templates/standalone-repos/`](../templates/standalone-repos/):

| Repo | Template file |
|------|-----------------|
| `mhold3n/response-control-framework` | `response-control-framework-ci.yml` |
| `mhold3n/ai-shared-service` | `ai-shared-service-ci.yml` |
| `mhold3n/domain-engineering` | `domain-engineering-ci.yml` |
| `mhold3n/domain-research` | `domain-research-ci.yml` |
| `mhold3n/domain-content` | `domain-content-ci.yml` |

Copy the chosen file to **`<repo>/.github/workflows/ci.yml`**.

## 3. Dev extras

Ensure each package’s `pyproject.toml` has `[project.optional-dependencies]` **`dev`** (or adjust `extras-name` in the caller) including at least `pytest`, `ruff`, and `mypy`, plus anything tests import.

## 4. Open PRs and fix failures

Merge when **ruff**, **mypy --strict**, and **pytest** pass. Tune `pytest-args`, `ruff-paths`, `mypy-target`, or `job-timeout-minutes` only in the caller `with:` block.

## 5. Branch protection

After CI appears on a PR, configure rules using [standalone-branch-protection.md](standalone-branch-protection.md).

## Optional: GHCR (`ai-shared-service` only)

See [`docs/templates/ai-shared-service-ghcr-publish.yml`](../templates/ai-shared-service-ghcr-publish.yml) and the commented `image:` block in [`docker/compose-profiles/docker-compose.addons.yml`](../../docker/compose-profiles/docker-compose.addons.yml).
