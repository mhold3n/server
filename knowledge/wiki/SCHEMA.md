# Birtha unified wiki — authoring contract

This tree is the **single** long-lived knowledge surface for humans and tooling. Only one subtree feeds orchestration JSON generation.

## Zones (path = authority)

| Path | Role |
|------|------|
| `knowledge/wiki/orchestration/{modes,pools,modules,techniques,theory}/` | **Routing cards.** Each `*.md` file’s JSON front matter is compiled into [`knowledge/response-control/`](../response-control/) JSON arrays consumed by `evaluate_response_control` in the API service. |
| `knowledge/wiki/projects/` | **Non-routing** project narrative (clients, delivery, specs). The compiler **never** reads this directory. |
| `knowledge/wiki/index.md` | Human-oriented map of the wiki (optional machine lint later). |
| `knowledge/wiki/log.md` | Chronological notes and decisions about wiki structure (optional). |

## Orchestration page format

1. File **must** live under `knowledge/wiki/orchestration/<shard>/` where `<shard>` is one of: `modes`, `pools`, `modules`, `techniques`, `theory`.
2. Begin the file with **JSON** front matter delimited by `---` lines (stdlib-only compile; no YAML dependency).
3. The JSON block **must** include the full machine record for that shard (same fields as the JSON objects in `knowledge/response-control/*.json`), validated by Pydantic models in `services/api-service/src/control_plane/contracts.py`:
   - `modes` → `ResponseModePayload`
   - `pools` → `KnowledgePoolPayload`
   - `modules` → `ModuleCardPayload`
   - `techniques` → `TechniqueCardPayload`
   - `theory` → `TheoryCardPayload`
4. Optional metadata keys (stripped before validation; must not collide with card fields):
   - `wiki_zone`: must be `orchestration` when present.
   - `wiki_shard`: must match the parent directory name (`modes`, `pools`, etc.).
5. Markdown **after** the closing `---` is free-form (rationale, diagrams, links). It is **not** parsed into JSON and does not affect routing.

## Workflow

1. Edit markdown under `knowledge/wiki/orchestration/`.
2. From the repo root: `make wiki-compile` (or `python scripts/wiki_compile_response_control.py`).
3. Commit **both** the wiki sources and the regenerated `knowledge/response-control/*.json`.
4. CI runs `make wiki-check` to forbid drift between sources and JSON.

Do **not** hand-edit `knowledge/response-control/*.json` on an ongoing basis; treat those files as **build artifacts** of this wiki.
