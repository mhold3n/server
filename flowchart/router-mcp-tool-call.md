# api-service — MCP tool execution via router-service

From `routes/ai.py`: `_call_router_mcp_tool` and `_run_required_tools` when `req.tools` is set (orchestration pre-step before LangGraph).

```mermaid
flowchart TD
  LOOP["_run_required_tools(prompt, tools, tool_args)"] --> EACH["For each tool_spec in tools"]
  EACH --> FMT{"':' in spec?"}
  FMT -->|no| ERR["ValueError: expect server:tool"]
  FMT -->|yes| SPLIT["server, tool = split"]
  SPLIT --> ARGS["args = query; merge tool_args[server:tool]"]
  ARGS --> HTTP["httpx POST\n{settings.router_url}/mcp/servers/{server}/call\njson: tool_name, arguments"]
  HTTP --> OK["append result dict to list"]
  OK --> EACH
```

This keeps the **router** as a tool adapter while LangGraph retains orchestration in agent-platform.
