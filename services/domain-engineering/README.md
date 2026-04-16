# Domain Engineering

Python package isolating **engineering** control-plane logic and the `coding-tools` knowledge substrate for the Birtha server.

## Dependencies

- [`response-control-framework`](../response-control-framework): contracts, `evaluate_response_control`, knowledge pool loader.
- [`ai-shared-service`](../ai-shared-service): shared classifiers and gateway helpers.

Install from the **repository root** with the uv workspace (recommended):

```bash
uv sync --python 3.11
```

Or editable installs in dependency order:

```bash
pip install -e services/response-control-framework
pip install -e services/ai-shared-service
pip install -e services/domain-engineering
```

## Knowledge layout

- **Engineering substrate (JSON, adapters, runtimes):** `src/domain_engineering/data/coding-tools/`
- **Orchestration wiki (modes, pools, modules, …):** lives under `knowledge/wiki/orchestration/` in the super-project; research/content shards are maintained in [`domain-research`](../domain-research) and [`domain-content`](../domain-content) and merged via `scripts/sync_domain_orchestration_wiki.py` before `wiki_compile`.

`resolve_engineering_knowledge_pool_root()` in `response-control-framework` selects the same roots as `KnowledgePoolCatalog.load` (packaged `data/coding-tools`, then legacy `knowledge/coding-tools`).

## Tests

```bash
cd services/domain-engineering
pytest -q
```

## Splitting to its own GitHub repository

1. Copy or submodule this tree as the new repo; keep the same package name `domain-engineering` or rename in one commit.
2. Pin **`response-control-framework`** via git tag or published wheel (same for `ai-shared-service`).
3. In the **super-project**, replace the workspace path with `tool.uv.sources` pointing at the git URL and revision tag.
4. CI in the domain repo should run `pytest` and optionally `wiki_compile --check` if that repo vendors orchestration sources.

No `domain_engineering` code may import the API service or other feature apps (acyclic graph).
