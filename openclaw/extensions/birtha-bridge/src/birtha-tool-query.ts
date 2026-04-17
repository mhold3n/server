/**
 * OpenClaw tool: birtha_tool_query
 *
 * Calls POST /api/ai/tool-query on Birtha api-service (tool-model lane).
 * Wire this module into the host plugin loader per openclaw.plugin.json.
 *
 * Responses are non-authoritative; the shell must not treat them as final user truth.
 */

export type BirthaToolQueryArgs = {
  birthaApiBaseUrl: string;
  bearerToken?: string;
  toolName: string;
  toolVersion: string;
  toolGoal: string;
  inputPayload: Record<string, unknown>;
  toolSchemaExpected?: Record<string, unknown>;
  openclawBridge: Record<string, unknown>;
  maxTokens?: number;
  timeoutBudgetMs?: number;
};

export type ToolQueryResult = Record<string, unknown>;

/**
 * Execute a tool-model lane request (fetch + JSON parse).
 */
export async function birthaToolQuery(args: BirthaToolQueryArgs): Promise<ToolQueryResult> {
  const base = args.birthaApiBaseUrl.replace(/\/$/, "");
  const url = `${base}/api/ai/tool-query`;
  const headers: Record<string, string> = {
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
  let data: ToolQueryResult;
  try {
    data = JSON.parse(text) as ToolQueryResult;
  } catch {
    throw new Error(`birtha_tool_query: non-JSON response (${res.status}): ${text.slice(0, 400)}`);
  }
  if (!res.ok) {
    const err = new Error(`birtha_tool_query: HTTP ${res.status}`);
    (err as Error & { body?: ToolQueryResult }).body = data;
    throw err;
  }
  return data;
}
