/**
 * ESM runtime (no TypeScript build). Keep in sync with birtha-tool-query.ts.
 */

export async function birthaToolQuery(args) {
  const base = args.birthaApiBaseUrl.replace(/\/$/, "");
  const url = `${base}/api/ai/tool-query`;
  const headers = {
    "Content-Type": "application/json",
  };
  if (args.bearerToken) {
    headers.Authorization = `Bearer ${args.bearerToken}`;
  }
  const body = {
    tool_name: args.toolName,
    tool_version: args.toolVersion,
    tool_goal: args.toolGoal,
    input_payload: args.inputPayload,
    tool_schema_expected: args.toolSchemaExpected,
    max_tokens: args.maxTokens,
    timeout_budget_ms: args.timeoutBudgetMs,
    openclaw_bridge: args.openclawBridge,
  };
  const res = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  const text = await res.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error(`birtha_tool_query: non-JSON response (${res.status}): ${text.slice(0, 400)}`);
  }
  if (!res.ok) {
    const err = new Error(`birtha_tool_query: HTTP ${res.status}`);
    err.body = data;
    throw err;
  }
  return data;
}
