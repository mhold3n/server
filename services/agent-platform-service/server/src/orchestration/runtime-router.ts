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

export interface ModelRoutingRequest {
  providerPreference?: string
  provider?: SupportedProvider
  model?: string
  baseURL?: string
  apiKey?: string
  temperature?: number
  maxTokens?: number
}

export interface ResolvedWorkflowModelRouting {
  model?: string
  provider?: SupportedProvider
  baseURL?: string
  apiKey?: string
  temperature?: number
  maxTokens?: number
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

function normalizeNativeOllamaBaseUrl(url: string): string {
  return url.replace(/\/$/, "").replace(/\/v1$/i, "")
}

function normalizeProviderPreference(value: string | undefined): string | undefined {
  const normalized = value?.trim().toLowerCase()
  return normalized || undefined
}

function isSupportedProvider(value: string | undefined): value is SupportedProvider {
  return (
    value === "anthropic" ||
    value === "copilot" ||
    value === "grok" ||
    value === "openai" ||
    value === "gemini" ||
    value === "ollama"
  )
}

function hfApiKey(cfg: PlatformConfig, override?: string): string | undefined {
  return override ?? cfg.huggingfaceApiKey
}

export function resolveMergedOmaRoute(
  cfg: PlatformConfig,
  overrides: Partial<{
    provider: SupportedProvider
    providerPreference: string
    model: string
    baseURL: string
    apiKey: string
  }> = {},
): ResolvedModelRoute {
  const preference = normalizeProviderPreference(
    overrides.providerPreference ?? overrides.provider,
  )
  const localWorkerPreference =
    preference === "local_worker" || preference === "local" || preference === "swarm"
  const hasExplicitProviderRoute = Boolean(
    (preference && !localWorkerPreference) ||
      overrides.provider ||
      overrides.baseURL ||
      overrides.apiKey,
  )
  const runtime: ResolvedModelRoute = {
    runtime: "merged_oma",
    transport: isMockLlmBackend(cfg) && !hasExplicitProviderRoute ? "mock" : "provider",
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

  const routeLocalWorker = () => {
    const backend = cfg.llmBackend
    if (backend === "ollama") {
      provider = "ollama"
      model = overrides.model ?? cfg.ollamaModel
      baseURL = overrides.baseURL ?? normalizeNativeOllamaBaseUrl(cfg.llmRunnerUrl)
      apiKey = overrides.apiKey ?? cfg.llmRunnerApiKey ?? "ollama-local"
      return
    }
    if (backend === "huggingface" || backend === "hf") {
      provider = "openai"
      model = overrides.model ?? cfg.huggingfaceModel
      baseURL = overrides.baseURL ?? cfg.huggingfaceBaseUrl
      apiKey = hfApiKey(cfg, overrides.apiKey)
      return
    }
    provider = "openai"
    model = overrides.model ?? cfg.vllmModel
    baseURL = overrides.baseURL ?? normalizeOpenAiCompatBaseUrl(cfg.llmRunnerUrl)
    apiKey = overrides.apiKey ?? cfg.llmRunnerApiKey ?? "local-openai"
  }

  if (preference === "ollama") {
    provider = "ollama"
    model = overrides.model ?? cfg.ollamaModel
    baseURL = overrides.baseURL ?? normalizeNativeOllamaBaseUrl(cfg.llmRunnerUrl)
    apiKey = overrides.apiKey ?? cfg.llmRunnerApiKey ?? "ollama-local"
  } else if (preference === "vllm") {
    provider = "openai"
    model = overrides.model ?? cfg.vllmModel
    baseURL = overrides.baseURL ?? normalizeOpenAiCompatBaseUrl(cfg.llmRunnerUrl)
    apiKey = overrides.apiKey ?? cfg.llmRunnerApiKey ?? "local-openai"
  } else if (preference === "huggingface" || preference === "hf") {
    provider = "openai"
    model = overrides.model ?? cfg.huggingfaceModel
    baseURL = overrides.baseURL ?? cfg.huggingfaceBaseUrl
    apiKey = hfApiKey(cfg, overrides.apiKey)
  } else if (
    preference === "local_worker" ||
    preference === "local" ||
    preference === "swarm"
  ) {
    routeLocalWorker()
  } else if (preference === "hosted_api") {
    provider = cfg.orchestrationDefaultProvider
    model = overrides.model ?? cfg.orchestrationDefaultModel
    baseURL = overrides.baseURL ?? cfg.orchestrationDefaultBaseUrl
    apiKey = overrides.apiKey ?? cfg.orchestrationDefaultApiKey
  } else if (!preference && (cfg.llmBackend === "vllm" || cfg.llmBackend === "ollama")) {
    routeLocalWorker()
  } else if (!preference && (cfg.llmBackend === "huggingface" || cfg.llmBackend === "hf")) {
    provider = "openai"
    model = overrides.model ?? cfg.huggingfaceModel
    baseURL = overrides.baseURL ?? cfg.huggingfaceBaseUrl
    apiKey = hfApiKey(cfg, overrides.apiKey)
  } else if (isSupportedProvider(preference)) {
    provider = preference
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

function readString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined
}

function readNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined
}

function readRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

export function resolveWorkflowModelRouting(
  cfg: PlatformConfig,
  inputData: Record<string, unknown> = {},
  workflowConfig: Record<string, unknown> = {},
): ResolvedWorkflowModelRouting {
  const modelRouting = readRecord(workflowConfig.model_routing)
  const providerPreference =
    readString(modelRouting.provider_preference) ??
    readString(modelRouting.provider) ??
    readString(workflowConfig.provider_preference) ??
    readString(inputData.provider)
  const providerValue = normalizeProviderPreference(readString(modelRouting.provider))
  const provider = isSupportedProvider(providerValue) ? providerValue : undefined
  const maxTokens =
    readNumber(modelRouting.max_tokens) ??
    readNumber(modelRouting.maxTokens) ??
    readNumber(inputData.max_tokens) ??
    readNumber(inputData.maxTokens)
  const request: ModelRoutingRequest = {
    providerPreference,
    provider,
    model: readString(modelRouting.model) ?? readString(inputData.model),
    baseURL: readString(modelRouting.base_url) ?? readString(modelRouting.baseURL),
    apiKey: readString(modelRouting.api_key) ?? readString(modelRouting.apiKey),
    temperature: readNumber(modelRouting.temperature) ?? readNumber(inputData.temperature),
    maxTokens,
  }
  const route = resolveMergedOmaRoute(cfg, request)
  return {
    model: route.model,
    provider: route.provider,
    baseURL: route.baseURL,
    apiKey: route.apiKey,
    temperature: request.temperature,
    maxTokens: request.maxTokens,
  }
}
