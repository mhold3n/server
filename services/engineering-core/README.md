# engineering-core

Deterministic **reference mechanics** (no LLM): sliding block on flat surface, friction, quasi-static work/energy ledger. Loads packaged `engineering_core/fixtures/*.json` for density and interface friction.

- **`solve_mechanics`**: public entry — JSON dict matching `solve_mechanics_request_v1.schema.json` → `engineering_report_v1`.
- **`verify_engineering_report`**: returns `verification_outcome` dict (bounded check names).

```bash
cd services/engineering-core && pip install -e ".[dev]" && pytest -q
```
