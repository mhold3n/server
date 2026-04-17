# Tool-model lane (v1)

HTTPS **`POST /api/ai/tool-query`** contracts for OpenClaw **class B** (AI-assisted shell) tools.

- `tool-query-request.schema.json` — request body.
- `tool-query-response.schema.json` — discriminated union of result types.
- `provenance.schema.json` — required metadata on non-rejected success paths.

Registry of tool classes: `../birtha_bridge_tools.v1.json` (sibling to this directory).
