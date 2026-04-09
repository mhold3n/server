import type { SupportedProvider } from "@server/open-multi-agent"
import type { PlatformConfig } from "../config.js"

export type ExecutorRuntime =
  | "merged_oma"
  | "claw_code"
  | "model_runtime_multimodal"
  | "deterministic"

export interface ResolvedModelRoute {
  runtime: "merged_oma"
  transport: "provider" | "mock"
  provider?: SupportedProvider
  model: string
  baseURL?: string
  apiKey?: string
  maxTokenBudget?: number
}

const EXECUTOR_RUNTIME: Record<string, ExecutorRuntime> = {
  coding_model: "claw_code",
  local_general_model: "merged_oma",
  strategic_reviewer: "merged_oma",
  multimodal_model: "model_runtime_multimodal",
  deterministic_validator: "deterministic",
}

export function resolveExecutorRuntime(selectedExecutor?: string): ExecutorRuntime | undefined {
  if (!selectedExecutor) return undefined
  return EXECUTOR_RUNTIME[selectedExecutor]
}

export function isMockLlmBackend(cfg: PlatformConfig): boolean {
  return ["mock", "none", "disabled"].includes(cfg.llmBackend)
}

function normalizeOpenAiCompatBaseUrl(url: string): string {
  const trimmed = url.replace(/\/$/, "")
  return trimmed.endsWith("/v1") ? trimmed : `${trimmed}/v1`
}

export function resolveMergedOmaRoute(
  cfg: PlatformConfig,
  overrides: Partial<{
    provider: SupportedProvider
    model: string
    baseURL: string
    apiKey: string
  }> = {},
): ResolvedModelRoute {
  const runtime: ResolvedModelRoute = {
    runtime: "merged_oma",
    transport: isMockLlmBackend(cfg) ? "mock" : "provider",
    model: overrides.model ?? cfg.orchestrationDefaultModel,
    maxTokenBudget: cfg.orchestrationMaxTokenBudget,
  }

  if (runtime.transport === "mock") {
    runtime.model = overrides.model ?? "mock-llm"
    return runtime
  }

  let provider = overrides.provider ?? cfg.orchestrationDefaultProvider
  let model = overrides.model ?? cfg.orchestrationDefaultModel
  let baseURL = overrides.baseURL ?? cfg.orchestrationDefaultBaseUrl
  let apiKey = overrides.apiKey ?? cfg.orchestrationDefaultApiKey

  if (cfg.llmBackend === "vllm" || cfg.llmBackend === "ollama") {
    if (overrides.provider === undefined) {
      provider = "openai"
    }
    if (overrides.model === undefined) {
      model = cfg.llmBackend === "vllm" ? cfg.vllmModel : cfg.ollamaModel
    }
    if (overrides.baseURL === undefined) {
      baseURL = normalizeOpenAiCompatBaseUrl(cfg.llmRunnerUrl)
    }
    if (overrides.apiKey === undefined && provider === "openai" && !apiKey) {
      apiKey = cfg.llmBackend === "ollama" ? "ollama" : cfg.llmRunnerApiKey ?? "local-openai"
    }
  }

  return {
    runtime: "merged_oma",
    transport: "provider",
    provider,
    model,
    baseURL,
    apiKey,
    maxTokenBudget: cfg.orchestrationMaxTokenBudget,
  }
}
