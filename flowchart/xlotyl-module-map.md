# xlotyl — module dependency map

`birtha_tool_model` package under **`services/api-service/src/`** in the [xlotyl](https://github.com/XLOTYL/xlotyl) repo. HTTP route: **`POST /api/ai/tool-query`** on [`routes/ai.py`](https://github.com/XLOTYL/xlotyl/blob/main/services/api-service/src/routes/ai.py). Stack context: [`xlotyl-overview.md`](xlotyl-overview.md).

Mermaid diagram of how `birtha_tool_model` modules relate. Arrows follow **import direction** (consumer → dependency).

```mermaid
flowchart LR
  subgraph public["Public API"]
    INIT["birtha_tool_model.__init__\nprocess_tool_query"]
  end

  subgraph http["HTTP"]
    AI["routes/ai.py\nai_tool_query"]
    AI -->|"POST /api/ai/tool-query"| PQ["handler.py\nprocess_tool_query()"]
  end

  subgraph core["Core"]
    H["handler.py\n_validate_request\n_provenance"]
    REG["registry.py\nload_registry\ntool_class\nassert_class_b"]
    PATHS["paths.py\n_xlotyl_root\nschema_dir\ntool_model_schema_dir\ndefault_registry_path"]
    OBS["observability.py\nmetrics\nlog_lane_event"]
  end

  INIT --> PQ
  PQ --> H
  H --> REG
  H --> PATHS
  H --> OBS
  AI --> PQ
  REG --> PATHS

  subgraph disk["On disk (xlotyl tree)"]
    TM["schemas/.../tool-model/\n*.schema.json"]
    RV["schemas/.../registry.v1.json\n(or BIRTHA_TOOL_MODEL_REGISTRY_PATH)"]
    BR["schemas/.../birtha_bridge_tools.v1.json"]
  end

  PATHS --> TM
  PATHS --> RV
  PATHS --> BR
```

**Server repo:** integration pin only — [`xlotyl/INTEGRATION.json`](../xlotyl/INTEGRATION.json).
