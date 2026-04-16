# Domain Research

Orchestration sources for **research** mode and the **source_corroboration** knowledge pool. Depends on [`response-control-framework`](../response-control-framework) and [`ai-shared-service`](../ai-shared-service).

## Wiki ownership

Authoritative markdown lives under `wiki/orchestration/{modes,pools,modules,techniques,theory}/`. The super-project merges these into `knowledge/wiki/orchestration/` via `scripts/sync_domain_orchestration_wiki.py` before `wiki_compile`.

## Public API

- `default_research_pool_keys()` — default pools for research workflows.

## Tests

```bash
cd services/domain-research
pytest -q
```

## Mirror repo checklist

Same pattern as [`domain-engineering`](../domain-engineering/README.md): tag releases, pin `response-control-framework`, no imports from `api-service`.
