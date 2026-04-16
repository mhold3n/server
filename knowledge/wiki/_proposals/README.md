# Wiki proposal queue

This directory stores unapproved wiki edit proposals produced by orchestration runs.

- File format: markdown with JSON front matter delimited by `---`.
- Front matter payload validates against `wiki-edit-proposal.schema.json`.
- Canonical wiki pages under `knowledge/wiki/orchestration/**` and `knowledge/wiki/projects/**`
  are not edited directly until a proposal is approved and promoted.

Lifecycle:

1. `PROPOSED` — created automatically, marked `unapproved_source: true`.
2. `APPROVED` — explicitly approved by the head editor.
3. `PROMOTED` — applied to canonical wiki and compiled catalogs in a promotion run/PR.
4. `REJECTED` — preserved for audit, excluded from promotion.
