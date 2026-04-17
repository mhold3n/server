# xlotyl — `POST /api/ai/tool-query` HTTP flow

[`routes.ai`](https://github.com/XLOTYL/xlotyl/blob/main/services/api-service/src/routes/ai.py) `ai_tool_query` → `asyncio.to_thread(process_tool_query, body)`. Contrasts with **`POST /api/ai/query`**: [`ai-query-pipeline.md`](ai-query-pipeline.md), [`xlotyl-overview.md`](xlotyl-overview.md).

```mermaid
flowchart TD
  A["Client POST /api/ai/tool-query"] --> B["routes.ai.ai_tool_query"]
  B --> C["await request.json()"]
  C --> D{"body is dict?"}
  D -->|no| F["Return tool_result_rejected\nschema_validation_failed"]
  D -->|yes| G["asyncio.to_thread\nprocess_tool_query"]
  G --> H["See process-tool-query.md"]
```
