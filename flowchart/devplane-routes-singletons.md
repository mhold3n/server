# api-service — DevPlane route module singletons

From `services/api-service/src/routes/devplane.py`: how HTTP handlers obtain `DevPlaneService` and execution backend.

```mermaid
flowchart TD
  GS(["get_service()"]) --> SIG{"_service is None or\nsignature changed?"}
  SIG -->|yes| NEW["DevPlaneService(\n db_path,\n devplane_root,\n control_plane_root,\n default_remote)"]
  SIG -->|no| RET1["return _service"]
  NEW --> RET1

  GEC(["get_execution_client()"]) --> EC{"_execution_client?"}
  EC -->|None| DEV["DevPlaneExecutionClient(\n base_url = settings.agent_platform_url)"]
  EC -->|set| RET2["return client"]
  DEV --> RET2
```

`control_plane_root` resolves from `Path(__file__).resolve().parents[4]` when depth allows, else `parents[2]` (container-safe).
