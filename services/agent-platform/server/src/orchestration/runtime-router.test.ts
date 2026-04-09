import { describe, expect, it } from "vitest"
import type { PlatformConfig } from "../config.js"
import {
  resolveExecutorRuntime,
  resolveMergedOmaRoute,
} from "./runtime-router.js"

function baseConfig(): PlatformConfig {
  return {
    ragUrl: "http://rag",
    asrUrl: "http://asr",
    mcpUrl: "http://mcp",
    toolRegistryUrl: "http://tools",
    llmRunnerUrl: "http://llm:8000",
    llmRunnerApiKey: undefined,
    llmBackend: "mock",
    ollamaModel: "ollama-model",
    vllmModel: "vllm-model",
    apiBrainEnabled: false,
    apiBrainMaxEscalationsPerTask: 1,
    apiBrainProvider: "openai",
    apiBrainModel: "",
    orchestrationDefaultModel: "default-model",
    orchestrationDefaultProvider: "anthropic",
    orchestrationDefaultBaseUrl: undefined,
    orchestrationDefaultApiKey: undefined,
    orchestrationMaxTokenBudget: 1234,
    orchestratorApiUrl: "",
    modelRuntimeBaseUrl: "",
    clawCodeBinary: "claw",
    clawCodeModel: undefined,
    clawCodeTrustedRoots: [],
    clawCodePollIntervalMs: 100,
    clawCodeTimeoutMs: 1000,
    clawCodeMaxConcurrentLanes: 1,
  }
}

describe("runtime-router", () => {
  it("maps every active selected_executor to the expected runtime", () => {
    expect(resolveExecutorRuntime("coding_model")).toBe("claw_code")
    expect(resolveExecutorRuntime("local_general_model")).toBe("merged_oma")
    expect(resolveExecutorRuntime("strategic_reviewer")).toBe("merged_oma")
    expect(resolveExecutorRuntime("multimodal_model")).toBe("model_runtime_multimodal")
    expect(resolveExecutorRuntime("deterministic_validator")).toBe("deterministic")
  })

  it("routes mock backends through the merged OMA mock transport", () => {
    const route = resolveMergedOmaRoute(baseConfig())
    expect(route.runtime).toBe("merged_oma")
    expect(route.transport).toBe("mock")
    expect(route.model).toBe("mock-llm")
  })

  it("routes local OpenAI-compatible backends through merged OMA openai config", () => {
    const cfg = baseConfig()
    cfg.llmBackend = "vllm"
    cfg.llmRunnerUrl = "http://localhost:9000"
    cfg.llmRunnerApiKey = "token"
    const route = resolveMergedOmaRoute(cfg)
    expect(route.transport).toBe("provider")
    expect(route.provider).toBe("openai")
    expect(route.model).toBe("vllm-model")
    expect(route.baseURL).toBe("http://localhost:9000/v1")
    expect(route.apiKey).toBe("token")
  })
})
