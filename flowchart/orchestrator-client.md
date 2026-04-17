# api-service — `OrchestratorClient` → agent-platform

From `services/api-service/src/orchestrator_client.py`: single HTTP surface for LangGraph workflows.

```mermaid
flowchart LR
  subgraph api["api-service"]
    OC["OrchestratorClient\n(context manager)"]
    OC --> POST["POST {base_url}/v1/workflows/execute"]
  end

  subgraph payload["JSON body"]
    WN["workflow_name"]
    IN["input_data"]
    WC["workflow_config\n(merged defaults:\nallow_api_brain=False,\nescalation_budget=0)"]
  end

  POST --> AP["agent-platform-service/server\nFastify"]
```

**Config:** `settings.agent_platform_url` (env `AGENT_PLATFORM_URL` or `ORCHESTRATOR_AGENT_PLATFORM_URL`).
