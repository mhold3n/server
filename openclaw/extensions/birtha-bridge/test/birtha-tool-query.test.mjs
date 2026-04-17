/**
 * Node native test: birtha_tool_query HTTP client against a stub server.
 */
import assert from "node:assert/strict";
import http from "node:http";
import { test } from "node:test";
import { birthaToolQuery } from "../src/birtha-tool-query.mjs";

test("birthaToolQuery posts JSON and parses result", async () => {
  const server = http.createServer((req, res) => {
    if (req.method !== "POST" || req.url !== "/api/ai/tool-query") {
      res.writeHead(404);
      res.end();
      return;
    }
    let buf = "";
    req.on("data", (c) => {
      buf += c;
    });
    req.on("end", () => {
      const parsed = JSON.parse(buf);
      assert.equal(parsed.tool_name, "summarize_snippet");
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          result_type: "tool_result_structured",
          provenance: {
            origin: "openclaw_tool",
            tool_name: "summarize_snippet",
            tool_call_id: "x",
            model_used: "stub",
            lane: "tool_model",
            confidence_mode: "preliminary",
            mutation_rights: "none",
            authoritative: false,
            requires_validation: true,
          },
          payload: { ok: true },
        }),
      );
    });
  });

  await new Promise((resolve) => server.listen(0, resolve));
  const { port } = server.address();

  try {
    const out = await birthaToolQuery({
      birthaApiBaseUrl: `http://127.0.0.1:${port}`,
      toolName: "summarize_snippet",
      toolVersion: "1",
      toolGoal: "test",
      inputPayload: {},
      openclawBridge: {},
    });
    assert.equal(out.result_type, "tool_result_structured");
    assert.equal(out.provenance.lane, "tool_model");
  } finally {
    server.close();
  }
});
