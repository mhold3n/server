# birtha-bridge (OpenClaw extension)

Plugin-only integration with Birtha / Xlotyl HTTPS APIs.

| Tool | Route |
|------|--------|
| `birtha_query` | `POST /api/ai/query` |
| `birtha_query_stream` | `POST /api/ai/query/stream` |
| `birtha_tool_query` | `POST /api/ai/tool-query` (tool-model lane, class **B** tools only) |

OpenClaw core stays unchanged; tools are registered via `openclaw.plugin.json`.

## Configuration

- `birthaApiBaseUrl` — Birtha api-service base URL (same as `birtha_query`).

## Tool-model lane

`birtha_tool_query` sends a compact JSON body per `xlotyl/schemas/openclaw-bridge/v1/tool-model/tool-query-request.schema.json`. Responses are **non-authoritative** (`lane=tool_model`); see ADR [`docs/adr/0002-openclaw-tool-model-lane.md`](../../../docs/adr/0002-openclaw-tool-model-lane.md) in the **server** repository.

Implementation file: [`src/birtha-tool-query.ts`](src/birtha-tool-query.ts).
