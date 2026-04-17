# xlotyl — registry load and class-B assertion

`registry.py`; registry JSON lives under **`xlotyl/schemas/openclaw-bridge/v1/`** unless overridden by env. See [`xlotyl-repo-layout.md`](xlotyl-repo-layout.md).

Flow for `load_registry`, `tool_class`, and `assert_class_b` (tool-model lane may only serve **class B** tools).

```mermaid
flowchart TD
  subgraph load["load_registry() @ lru_cache"]
    L1["default_registry_path()\nenv BIRTHA_TOOL_MODEL_REGISTRY_PATH or\nschemas/.../registry.v1.json"]
    L1 --> L2["json.load"]
    L2 --> L3["_registry_format_validator()\nbirtha_bridge_tools.v1.json schema"]
    L3 --> L4["validate(data)"]
    L4 --> L5["Return registry dict"]
  end

  subgraph toolclass["tool_class(tool_name)"]
    T1["load_registry()"]
    T1 --> T2["Iterate tools[]"]
    T2 --> T3{"name match?"}
    T3 -->|yes| T4["Return class A|B|C"]
    T3 -->|no| T5["Return None"]
  end

  subgraph assertb["assert_class_b(tool_name)"]
    A1["cls = tool_class(tool_name)"]
    A1 --> A2{"cls is None?"}
    A2 -->|yes| A3["False, unknown_tool"]
    A2 -->|no| A4{"cls == B?"}
    A4 -->|yes| A5["True, None"]
    A4 -->|no| A6{"cls == A or C?"}
    A6 -->|yes| A7["False, tool_class_forbidden"]
    A6 -->|no| A8["False, unknown_tool"]
  end
```



