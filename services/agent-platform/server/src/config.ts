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
    ollamaModel: process.env.OLLAMA_MODEL ?? "llama3:8b-instruct",
    vllmModel: process.env.VLLM_MODEL ?? "default",
  }
}
