import { describe, expect, it } from "vitest"
import type { PlatformConfig } from "../config.js"
import { LLMManager } from "../llm/manager.js"
import { OrchestrationEngine } from "../orchestration/engine.js"
import { createChatWorkflow } from "./graph.js"

function baseCfg(): PlatformConfig {
  return {
    ragUrl: "http://rag",
    asrUrl: "http://asr",
    mcpUrl: "http://mcp",
    toolRegistryUrl: "http://tools",
    llmRunnerUrl: "http://llm",
    llmBackend: "mock",
    ollamaModel: "x",
    vllmModel: "x",
    huggingfaceModel: "hf-model",
    huggingfaceBaseUrl: "https://router.huggingface.co/v1",
    huggingfaceApiKey: undefined,
    apiBrainEnabled: true,
    apiBrainMaxEscalationsPerTask: 1,
    apiBrainProvider: "openai",
    apiBrainModel: "brain-model",
    orchestrationDefaultModel: "mock-llm",
    orchestrationDefaultProvider: "openai",
    orchestrationDefaultBaseUrl: undefined,
    orchestrationDefaultApiKey: undefined,
    orchestrationMaxTokenBudget: undefined,
    orchestratorApiUrl: "",
    modelRuntimeBaseUrl: "",
    clawCodeBinary: "claw",
    clawCodeModel: undefined,
    clawCodeTrustedRoots: [],
    clawCodePollIntervalMs: 10,
    clawCodeTimeoutMs: 200,
    clawCodeMaxConcurrentLanes: 1,
  }
}

describe("hybrid escalation routing", () => {
  it("does not call api brain unless allowed in workflow_config", async () => {
    const cfg = baseCfg()
    const llm = new LLMManager(cfg)
    const engine = new OrchestrationEngine(cfg, llm)
    let called = 0
    const wf = createChatWorkflow(cfg, engine, async () => {
      called += 1
      return "PLAN\n..."
    })

    await wf.invoke({
      messages: [{ role: "user", content: "architecture tradeoff review please" }],
      current_step: "analyze",
      tools_needed: [],
      tool_results: {},
      escalation_count: 0,
      workflow_config: { allow_api_brain: false },
    })

    expect(called).toBe(0)
  })

  it("calls api brain once when allowed and heuristic triggers hit", async () => {
    const cfg = baseCfg()
    const llm = new LLMManager(cfg)
    const engine = new OrchestrationEngine(cfg, llm)
    let called = 0
    const wf = createChatWorkflow(cfg, engine, async (packet) => {
      called += 1
      expect(packet).toContain("\"type\": \"CODE_STATE\"")
      return "PLAN\ngoal:\nrecommended_strategy:\nordered_steps:\n1.\nstop_condition:"
    })

    const out = await wf.invoke({
      messages: [{ role: "user", content: "Need an architecture tradeoff decision." }],
      current_step: "analyze",
      tools_needed: [],
      tool_results: {},
      escalation_count: 0,
      workflow_config: { allow_api_brain: true },
    })

    expect(called).toBe(1)
    expect((out as any).api_brain_output).toContain("PLAN")
    expect((out as any).escalation_count).toBe(1)
  })

  it("respects max escalations per task budget", async () => {
    const cfg = baseCfg()
    cfg.apiBrainMaxEscalationsPerTask = 0
    const llm = new LLMManager(cfg)
    const engine = new OrchestrationEngine(cfg, llm)
    let called = 0
    const wf = createChatWorkflow(cfg, engine, async () => {
      called += 1
      return "PLAN\n..."
    })

    await wf.invoke({
      messages: [{ role: "user", content: "architecture tradeoff review please" }],
      current_step: "analyze",
      tools_needed: [],
      tool_results: {},
      escalation_count: 0,
      workflow_config: { allow_api_brain: true },
    })

    expect(called).toBe(0)
  })
})
