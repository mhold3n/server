import { describe, expect, it } from "vitest"
import type { PlatformConfig } from "../config.js"
import {
  resolveExecutorRuntime,
  resolveMergedOmaRoute,
  resolveWorkflowModelRouting,
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
    huggingfaceModel: "hf-model",
    huggingfaceBaseUrl: "https://router.huggingface.co/v1",
    huggingfaceApiKey: "hf-token",
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

  it("keeps local_worker on mock fallback when the configured backend is mock", () => {
    const route = resolveMergedOmaRoute(baseConfig(), {
      providerPreference: "local_worker",
      model: "requested-model",
    })
    expect(route.transport).toBe("mock")
    expect(route.model).toBe("requested-model")
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

  it("routes Ollama through native provider config", () => {
    const cfg = baseConfig()
    cfg.llmBackend = "ollama"
    cfg.llmRunnerUrl = "http://localhost:11434/v1"
    const route = resolveMergedOmaRoute(cfg)
    expect(route.transport).toBe("provider")
    expect(route.provider).toBe("ollama")
    expect(route.model).toBe("ollama-model")
    expect(route.baseURL).toBe("http://localhost:11434")
  })

  it("routes Hugging Face preference through OpenAI-compatible router", () => {
    const route = resolveMergedOmaRoute(baseConfig(), {
      providerPreference: "huggingface",
    })
    expect(route.provider).toBe("openai")
    expect(route.model).toBe("hf-model")
    expect(route.baseURL).toBe("https://router.huggingface.co/v1")
    expect(route.apiKey).toBe("hf-token")
  })

  it("routes workflow model hints from flat input fields", () => {
    const cfg = baseConfig()
    cfg.llmBackend = "ollama"
    cfg.llmRunnerUrl = "http://localhost:11434/v1"
    const route = resolveWorkflowModelRouting(
      cfg,
      {
        provider: "vllm",
        model: "request-model",
        temperature: 0.15,
        max_tokens: 321,
      },
      {},
    )
    expect(route.provider).toBe("openai")
    expect(route.model).toBe("request-model")
    expect(route.baseURL).toBe("http://localhost:11434/v1")
    expect(route.temperature).toBe(0.15)
    expect(route.maxTokens).toBe(321)
  })

  it("lets workflow_config.model_routing override flat input hints", () => {
    const route = resolveWorkflowModelRouting(
      baseConfig(),
      { provider: "ollama", model: "ignored", temperature: 0.1, max_tokens: 100 },
      {
        model_routing: {
          provider_preference: "huggingface",
          model: "hf-override",
          temperature: 0.4,
          max_tokens: 200,
        },
      },
    )
    expect(route.provider).toBe("openai")
    expect(route.model).toBe("hf-override")
    expect(route.baseURL).toBe("https://router.huggingface.co/v1")
    expect(route.apiKey).toBe("hf-token")
    expect(route.temperature).toBe(0.4)
    expect(route.maxTokens).toBe(200)
  })
})
