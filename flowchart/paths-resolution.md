# xlotyl — path resolution (`paths.py`)

In the **xlotyl** product repository, `_xlotyl_root()` walks up from `services/api-service/src/birtha_tool_model/paths.py` to the repo root that contains **`schemas/`** (**four** parents: `birtha_tool_model` → `src` → `api-service` → `services` → `xlotyl`). How this fits deployments: [`xlotyl-overview.md`](xlotyl-overview.md).

How schema and registry files are located relative to that tree.

```mermaid
flowchart TD
  F["Path(__file__).resolve().parents[4]"] --> X["_xlotyl_root()\n→ xlotyl/"]
  X --> S["schema_dir()\n→ xlotyl/schemas/openclaw-bridge/v1"]
  S --> TM["tool_model_schema_dir()\n→ .../v1/tool-model"]
  S --> DR["default_registry_path()"]
  DR --> E{"BIRTHA_TOOL_MODEL_REGISTRY_PATH set?"}
  E -->|yes| P1["Path(override)"]
  E -->|no| P2["schema_dir() / registry.v1.json"]
```
