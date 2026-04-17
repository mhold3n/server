# xlotyl — repository layout

Derived from the **xlotyl** product `README.md` and tree layout. Major directories and how selected services connect.

```mermaid
flowchart TB
  subgraph root["xlotyl/"]
    SM["Submodules: openclaw/, claw-code-main/, void/"]
    MCP["mcp-servers/"]
    SVC["services/"]
    SCH["schemas/"]
    KNOW["knowledge/"]
    DOCK["docker/compose-profiles/"]
  end

  subgraph services["services/ (selected)"]
    API["api-service\n(control plane)"]
    RTR["router-service"]
    WRK["worker-service"]
    GW["ai-gateway-service"]
    AP["agent-platform-service"]
    MR["model-runtime"]
    DOM["domain-*, engineering-core,\nresponse-control-framework, …"]
  end

  SVC --> services
  root --> SM
  root --> MCP

  API -->|"AGENT_PLATFORM_URL"| AP
  API -->|"router_url"| RTR
  AP -->|"may call"| MR
```

**Downstream:** [mhold3n/server](https://github.com/mhold3n/server) runs published images; see [`xlotyl-overview.md`](xlotyl-overview.md).
