# agent-platform — `POST /v1/workflows/execute` dispatch

From `services/agent-platform-service/server/src/server.ts`: how `workflow_name` selects graph invocations (simplified).

```mermaid
flowchart TD
  REQ(["POST /v1/workflows/execute"]) --> PARSE["workflow_name default wrkhrs_chat\ninput_data, workflow_config"]
  PARSE --> ARCH{"workflow_name ==\nengineering_physics_v1?"}
  ARCH -->|yes| GONE["410 archived workflow"]
  ARCH -->|no| RUN["createWorkflowRun(uuid, name)"]

  RUN --> BR{"workflow_name"}
  BR -->|wrkhrs_chat or default| CW["createChatWorkflow.invoke\nwithModelRouting(...)\nrequired_tool_results from input"]
  BR -->|engineering_workflow| EW["createEngineeringWorkflow.invoke\nintake, task_packet, devplane context"]
  BR -->|other names| OTHER["rag_retrieval, tool_execution,\ngithub_integration, policy_validation,\ndevplane_code_task — see server.ts"]

  CW --> OUT["completeWorkflowRun → JSON result"]
  EW --> OUT
  OTHER --> OUT
```

Registered names (non-exhaustive for branches): `WORKFLOW_NAMES` includes `wrkhrs_chat`, `engineering_workflow`, `rag_retrieval`, `tool_execution`, `github_integration`, `policy_validation`, `devplane_code_task`.
