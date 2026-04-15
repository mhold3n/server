import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

export interface PlatformConfig {
  ragUrl: string
  asrUrl: string
  mcpUrl: string
  toolRegistryUrl: string
  llmRunnerUrl: string
  llmRunnerApiKey?: string
  llmBackend: string
  ollamaModel: string
  vllmModel: string
  huggingfaceModel: string
  huggingfaceBaseUrl: string
  huggingfaceApiKey?: string
  apiBrainEnabled: boolean
  apiBrainMaxEscalationsPerTask: number
  apiBrainProvider: "anthropic" | "openai"
  apiBrainModel: string
  orchestrationDefaultModel: string
  orchestrationDefaultProvider: "anthropic" | "copilot" | "grok" | "openai" | "gemini" | "ollama"
  orchestrationDefaultBaseUrl?: string
  orchestrationDefaultApiKey?: string
  orchestrationMaxTokenBudget?: number
  /** Base URL of FastAPI control plane (for structure classify + contract gates). */
  orchestratorApiUrl: string
  /** Python model-runtime (`/infer/*`, `/solve/*`); empty disables physics harness HTTP. */
  modelRuntimeBaseUrl: string
  clawCodeBinary: string
  clawCodeModel?: string
  clawCodeTrustedRoots: string[]
  clawCodePollIntervalMs: number
  clawCodeTimeoutMs: number
  clawCodeMaxConcurrentLanes: number
  /** Repo root used for knowledge-pool GUI scripts. */
  repoRoot?: string
  /** Python executable used for knowledge-pool GUI script wrappers. */
  knowledgeGuiPython?: string
}

const DEFAULT_REPO_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../..",
)
const DEFAULT_KNOWLEDGE_GUI_PYTHON = fs.existsSync(
  path.join(DEFAULT_REPO_ROOT, ".venv", "bin", "python"),
)
  ? path.join(DEFAULT_REPO_ROOT, ".venv", "bin", "python")
  : "python3"

function parseCsv(value: string | undefined): string[] {
  return (value ?? "")
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean)
}

export function loadConfig(): PlatformConfig {
  return {
    ragUrl: (process.env.RAG_URL ?? "http://wrkhrs-rag:8000").replace(/\/$/, ""),
    asrUrl: (process.env.ASR_URL ?? "http://wrkhrs-asr:8000").replace(/\/$/, ""),
    mcpUrl: (process.env.MCP_URL ?? "http://wrkhrs-mcp:8000").replace(/\/$/, ""),
    toolRegistryUrl: (
      process.env.TOOL_REGISTRY_URL ?? "http://wrkhrs-tool-registry:8000"
    ).replace(/\/$/, ""),
    llmRunnerUrl: (
      process.env.LLM_RUNNER_URL ?? "http://llm-runner:11434"
    ).replace(/\/$/, ""),
    llmRunnerApiKey: process.env.LLM_RUNNER_API_KEY,
    llmBackend: (process.env.LLM_BACKEND ?? "mock").toLowerCase(),
    // Default Ollama tag matches planned Qwen local lane (see docker-compose.local-ai Qwen/Qwen3-4B, e2e_mac_host_ollama.sh).
    ollamaModel: process.env.OLLAMA_MODEL ?? "qwen3:4b-instruct",
    vllmModel: process.env.VLLM_MODEL ?? "default",
    huggingfaceModel:
      process.env.HF_INFERENCE_MODEL ?? process.env.HUGGINGFACE_MODEL ?? "Qwen/Qwen3-8B",
    huggingfaceBaseUrl: (
      process.env.HF_INFERENCE_BASE_URL ?? "https://router.huggingface.co/v1"
    ).replace(/\/$/, ""),
    huggingfaceApiKey:
      process.env.HUGGINGFACE_HUB_TOKEN?.trim() || process.env.HF_TOKEN?.trim() || undefined,
    apiBrainEnabled: (process.env.API_BRAIN_ENABLED ?? "false").toLowerCase() === "true",
    apiBrainMaxEscalationsPerTask: Number(process.env.API_BRAIN_MAX_ESCALATIONS_PER_TASK ?? "1"),
    apiBrainProvider:
      ((process.env.API_BRAIN_PROVIDER as "anthropic" | "openai" | undefined) ??
        "anthropic"),
    apiBrainModel: process.env.API_BRAIN_MODEL ?? "",
    orchestrationDefaultModel:
      process.env.OMA_DEFAULT_MODEL ?? process.env.API_BRAIN_MODEL ?? "claude-sonnet-4-20250514",
    orchestrationDefaultProvider:
      ((process.env.OMA_DEFAULT_PROVIDER as
        | "anthropic"
        | "copilot"
        | "grok"
        | "openai"
        | "gemini"
        | "ollama"
        | undefined) ?? "anthropic"),
    orchestrationDefaultBaseUrl: (process.env.OMA_DEFAULT_BASE_URL ?? "").trim() || undefined,
    orchestrationDefaultApiKey: (process.env.OMA_DEFAULT_API_KEY ?? "").trim() || undefined,
    orchestrationMaxTokenBudget:
      process.env.OMA_MAX_TOKEN_BUDGET !== undefined
        ? Number(process.env.OMA_MAX_TOKEN_BUDGET)
        : undefined,
    orchestratorApiUrl: (
      process.env.ORCHESTRATOR_API_URL ?? process.env.DEVPLANE_PUBLIC_BASE_URL ?? ""
    ).replace(/\/$/, ""),
    modelRuntimeBaseUrl: (process.env.MODEL_RUNTIME_URL ?? "").replace(/\/$/, ""),
    clawCodeBinary: process.env.CLAW_CODE_BINARY ?? "claw",
    clawCodeModel: (process.env.CLAW_CODE_MODEL ?? "").trim() || undefined,
    clawCodeTrustedRoots: parseCsv(process.env.CLAW_CODE_TRUSTED_ROOTS),
    clawCodePollIntervalMs: Number(process.env.CLAW_CODE_POLL_INTERVAL_MS ?? "1000"),
    clawCodeTimeoutMs: Number(process.env.CLAW_CODE_TIMEOUT_MS ?? "120000"),
    clawCodeMaxConcurrentLanes: Number(process.env.CLAW_CODE_MAX_CONCURRENT_LANES ?? "4"),
    repoRoot: process.env.REPO_ROOT ?? DEFAULT_REPO_ROOT,
    knowledgeGuiPython: process.env.KNOWLEDGE_GUI_PYTHON ?? DEFAULT_KNOWLEDGE_GUI_PYTHON,
  }
}
