# Archived WrkHrs components

## `python-orchestrator/`

The LangGraph/Python FastAPI orchestrator was retired in favor of
[`services/agent-platform`](../../agent-platform) (TypeScript: Open Multi-Agent + LangGraph JS).

To run the legacy service for rollback or comparison:

```bash
docker compose -f docker-compose.yml -f docker-compose.ai.yml --profile legacy-python-orchestrator up -d wrkhrs-orchestrator
```

Ensure `ORCHESTRATOR_URL` on the gateway points at the Python container if you use it.
