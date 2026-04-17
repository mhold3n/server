# xlotyl — overview

How the major pieces fit together. Diagrams elsewhere in `flowchart/` drill into specific modules.

```mermaid
flowchart TB
  subgraph repo["xlotyl repository"]
    API["api-service"]
    API --> Q["POST /api/ai/query\nroutes/ai — execute_ai_query_pipeline"]
    API --> TQ["POST /api/ai/tool-query\nbirtha_tool_model"]
    API --> DP["routes/devplane, control_plane, …"]
    Q --> OC["OrchestratorClient"]
    OC --> AP["agent-platform-service\n/v1/workflows/execute"]
    Q --> RTR["router-service\nMCP tool calls"]
    AP --> MR["model-runtime\ninfer / solve"]
    SCH["schemas/\nopenclaw-bridge, …"]
    TQ --> SCH
    Q --> SCH
  end

  DEP["Deployments that pin OCI tags\n(e.g. mhold3n/server)"] -.->|"run images built from xlotyl CI"| repo
```

**Two AI entry points on api-service (different contracts):**

| Route | Flowchart |
|-------|-----------|
| `POST /api/ai/query` | [`ai-query-pipeline.md`](ai-query-pipeline.md) |
| `POST /api/ai/tool-query` | [`tool-query-http-flow.md`](tool-query-http-flow.md), [`process-tool-query.md`](process-tool-query.md) |
