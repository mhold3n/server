# api-service — `execute_ai_query_pipeline` (`routes/ai.py`)

Governed **`POST /api/ai/query`** orchestration: normalize messages, optional MCP “required tools”, engagement mode, DevPlane session hooks, then the LangGraph orchestrator. Distinct from the **`POST /api/ai/tool-query`** tool-model lane — see [`process-tool-query.md`](process-tool-query.md) and [`xlotyl-overview.md`](xlotyl-overview.md).

```mermaid
flowchart TD
  START(["execute_ai_query_pipeline(req)"]) --> MSG{"req.messages?"}
  MSG -->|yes| M1["messages = list(req.messages)"]
  MSG -->|no| M2["messages = user from req.prompt"]
  M1 --> SYS{"req.system?"}
  M2 --> SYS
  SYS -->|yes| MP["prepend system message"]
  SYS -->|no| RT
  MP --> RT

  RT["required_tool_results = []"] --> TOOLS{"req.tools?"}
  TOOLS -->|yes| RT2["_run_required_tools →\nPOST router /mcp/servers/.../call"]
  TOOLS -->|no| ID
  RT2 -->|fail| E502["HTTP 502 Required tool execution failed"]
  RT2 --> ID

  ID["input_data = messages, model, tools, context,\nrequired_tool_results, …"] --> SVC["get_service() DevPlane"]
  ID --> SNAP{"context.engineering_session_id?"}
  SNAP -->|yes| LOAD["load_engineering_session_snapshot"]
  SNAP -->|no| CFG
  LOAD --> CFG

  CFG["workflow_config, workflow_name = wrkhrs_chat"] --> EVAL["evaluate_engagement_mode(...)"]
  EVAL --> MODE{"selected_mode in\nengineering_task,\nstrict_engineering?"}
  MODE -->|yes| ENG["workflow_name = engineering_workflow\nensure_engineering_chat_session …"]
  MODE -->|no| NAP{"selected_mode == napkin_math?"}
  NAP -->|yes| NAPCFG["analytical_mode, non_mutating_only"]
  NAP -->|no| ORC
  ENG --> ORC

  ORC["async with OrchestratorClient()"] --> EX["client.execute_workflow(\nworkflow_name, input_data, workflow_config)"]
  EX --> POST["Merge / sync engineering session if applicable"]
  POST --> RET["return result dict"]
```
