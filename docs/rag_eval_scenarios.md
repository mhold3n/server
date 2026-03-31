# RAG workflow evaluation scenarios

This document describes the RAG evaluation loop used to tune prompts, RAG parameters (`k`, threshold, domain weights), and tool selection for task cards. The scenarios are defined in **`rag_eval_scenarios.yaml`** in this directory.

## Purpose

- Run the full path: **API → Router → (RAG / MCP tools) → Qwen** for each scenario.
- Log **precision-like signals**: whether the answer cited the expected document/source, and whether domain weighting was respected where applicable.
- Use results to iteratively adjust system prompts, RAG `k`/threshold/domain weights, and task card `required_tools`.

## Scenario format (YAML)

Each scenario in `rag_eval_scenarios.yaml` has:

| Field | Description |
|-------|-------------|
| `id` | Unique identifier (e.g. `rag-1`) |
| `task_card_id` | Workflow to run (`code-rag`, `media-fixups`, `sysadmin-ops`) |
| `query` | User input (query / instruction / task) |
| `expected_source_substrings` | (Optional) List of substrings that should appear in the model response or in retrieved evidence (citation signal). |
| `expected_tools_used` | (Optional) List of tool specs (e.g. `vector-db-mcp:embedding_search`) that should be used. |
| `notes` | (Optional) Human note for tuning. |

## Running the evaluation

From the API service directory:

```bash
# With stack running (router, Qwen, RAG/MCP available)
pytest tests/test_rag_workflow_eval.py -v

# Or run the helper script to print signals only (no pytest)
python tests/run_rag_eval.py --api-url http://localhost:8080
```

The test/script will:

1. Load scenarios from `docs/rag_eval_scenarios.yaml`.
2. For each scenario, call `POST /api/ai/workflows/run` (or `/api/ai/query` with router) with the scenario query and task card.
3. Log: response text length, whether any `expected_source_substrings` appear in the response, and which tools were used (when returned).
4. Optionally assert that citation and tool-use expectations are met (for CI or regression).

## Tuning playbook

1. Pick one task card (e.g. `code-rag`) and run 5–10 scenarios end-to-end.
2. Inspect router logs for tool calls and errors, and RAG search results vs. what Qwen used.
3. Adjust prompt template (citation instructions), RAG parameters (`k`, threshold, domain weights), and task card `required_tools`.
4. Re-run scenarios and compare quality and metrics.
