# model-runtime — FastAPI surface

From `services/model-runtime/src/model_runtime/app.py`: bounded inference / solve entry (high level).

```mermaid
flowchart TD
  APP["FastAPI app"] --> MOCK{"MOCK_INFER?"}
  MOCK -->|enabled| MOCKPATH["Deterministic / stub paths\n(no torch)"]
  MOCK -->|disabled| INF["infer_with_hf, engineering_core solve\nas configured"]
  APP --> VAL["validate_* helpers\norchestration_packet, solve_request,\ntask_packet variants"]
  VAL --> ROUTE["Route handlers under\n/infer/* and /solve/mechanics etc."]
```

See `app.py` and `validate.py` for exact routes and validation order.
