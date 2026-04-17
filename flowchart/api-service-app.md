# api-service — `src/app.py` control plane assembly

FastAPI app construction: which route modules mount and policy/observability hooks (abbreviated). The **`POST /api/ai/tool-query`** handler lives in **`routes.ai`** and delegates to **`birtha_tool_model.process_tool_query`** (xlotyl `services/api-service/src/`).

```mermaid
flowchart LR
  subgraph routers["Included routers (prefixes from modules)"]
    AI["routes.ai\n/api/ai"]
    CP["routes.control_plane"]
    DP["routes.devplane\n/api/dev"]
    SRCH["routes.search"]
    AUTO["routes.automation"]
    APPS["routes.apps"]
    VM["routes.vms"]
    TOR["routes.torrents"]
  end

  APP["FastAPI app"] --> policy["policies.middleware\npolicy_enforcer"]
  APP --> ctx["observability\nRequestContextMiddleware"]
  APP --> routers
```

Startup (`_startup`) also wires OpenTelemetry, MLflow, provenance, Redis, static files, and metrics — see `app.py` for the full sequence.

**See also:** [`xlotyl-overview.md`](xlotyl-overview.md)
