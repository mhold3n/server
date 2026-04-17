# Portable custom packages (not vendored here by default)

First-party **domain libraries** (`response-control-framework`, `ai-shared-service`, `domain-*`) are developed and released from **their own GitHub repositories**, with **CI** invoking the reusable workflow in this repo:

`mhold3n/server/.github/workflows/reusable-python-package-ci.yml`

## Repositories

| Package | GitHub |
|---------|--------|
| response-control-framework | [mhold3n/response-control-framework](https://github.com/mhold3n/response-control-framework) |
| ai-shared-service | [mhold3n/ai-shared-service](https://github.com/mhold3n/ai-shared-service) |
| domain-engineering | [mhold3n/domain-engineering](https://github.com/mhold3n/domain-engineering) |
| domain-research | [mhold3n/domain-research](https://github.com/mhold3n/domain-research) |
| domain-content | [mhold3n/domain-content](https://github.com/mhold3n/domain-content) |

Clone them **beside** this repo when you need to edit package code (same pattern as sibling `../xlotyl`). Template CI callers: [`docs/templates/standalone-repos/`](../docs/templates/standalone-repos/).

## Relationship to this repo

The **root** [`pyproject.toml`](../pyproject.toml) workspaces **host MCP servers** only. Domain package **pins** for the AI product live in **[XLOTYL/xlotyl](https://github.com/XLOTYL/xlotyl)** (see [xlotyl-and-standalone-packages.md](../docs/xlotyl-and-standalone-packages.md)), not in a giant monolith inside **mhold3n/server**—consistent with the [pointer-first content model](../docs/repository-content-model.md).

This directory exists as a **stable anchor** in the tree for documentation and optional future workspace layout; it does not duplicate package sources by default.
