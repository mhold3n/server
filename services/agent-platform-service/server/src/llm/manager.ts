import type { PlatformConfig } from "../config.js"
import type { ChatMessage } from "../tools/wrkhrs.js"

export class LLMBackendError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "LLMBackendError"
  }
}

export type OpenAICompatResult = {
  id: string
  object: string
  created: number
  model: string
  choices: Array<{
    index: number
    message: { role: string; content: string }
    finish_reason: string
  }>
  usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number }
}

export class LLMManager {
  constructor(private readonly cfg: PlatformConfig) {}

  async chatCompletion(
    messages: ChatMessage[],
    options: { temperature?: number; max_tokens?: number } = {},
  ): Promise<OpenAICompatResult> {
    const { llmBackend } = this.cfg
    const temperature = options.temperature ?? 0.7
    const maxTokens = options.max_tokens ?? 1000

    if (llmBackend === "ollama") {
      return this.ollamaChat(messages, temperature, maxTokens)
    }
    if (llmBackend === "vllm") {
      return this.vllmChat(messages, temperature, maxTokens)
    }
    if (llmBackend === "huggingface" || llmBackend === "hf") {
      return this.openAiCompatChat(
        messages,
        temperature,
        maxTokens,
        this.cfg.huggingfaceBaseUrl,
        this.cfg.huggingfaceModel,
        this.cfg.huggingfaceApiKey,
      )
    }
    return this.mockChat(messages)
  }

  private async ollamaChat(
    messages: ChatMessage[],
    temperature: number,
    maxTokens: number,
  ): Promise<OpenAICompatResult> {
    const payload = {
      model: this.cfg.ollamaModel,
      messages,
      stream: false,
      options: {
        temperature,
        num_predict: maxTokens,
      },
    }
    const base = this.cfg.llmRunnerUrl
    const headers: Record<string, string> = { "Content-Type": "application/json" }
    if (this.cfg.llmRunnerApiKey) {
      headers.Authorization = `Bearer ${this.cfg.llmRunnerApiKey}`
    }
    const res = await fetch(`${base}/api/chat`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(120_000),
    })
    if (!res.ok) {
      throw new LLMBackendError(`Ollama HTTP ${res.status}`)
    }
    const result = (await res.json()) as {
      message?: { content?: string }
      prompt_eval_count?: number
      eval_count?: number
    }
    const content = result.message?.content ?? ""
    const prompt = result.prompt_eval_count ?? 0
    const completion = result.eval_count ?? 0
    const now = Math.floor(Date.now() / 1000)
    return {
      id: `ollama-${now}`,
      object: "chat.completion",
      created: now,
      model: this.cfg.ollamaModel,
      choices: [
        {
          index: 0,
          message: { role: "assistant", content },
          finish_reason: "stop",
        },
      ],
      usage: {
        prompt_tokens: prompt,
        completion_tokens: completion,
        total_tokens: prompt + completion,
      },
    }
  }

  private async vllmChat(
    messages: ChatMessage[],
    temperature: number,
    maxTokens: number,
  ): Promise<OpenAICompatResult> {
    return this.openAiCompatChat(
      messages,
      temperature,
      maxTokens,
      `${this.cfg.llmRunnerUrl.replace(/\/$/, "")}/v1`,
      this.cfg.vllmModel,
      this.cfg.llmRunnerApiKey,
    )
  }

  private async openAiCompatChat(
    messages: ChatMessage[],
    temperature: number,
    maxTokens: number,
    baseUrl: string,
    model: string,
    apiKey?: string,
  ): Promise<OpenAICompatResult> {
    const base = baseUrl.replace(/\/$/, "")
    const payload = {
      model,
      messages,
      temperature,
      max_tokens: maxTokens,
      stream: false,
    }
    const headers: Record<string, string> = { "Content-Type": "application/json" }
    if (apiKey) {
      headers.Authorization = `Bearer ${apiKey}`
    }
    const res = await fetch(`${base}/chat/completions`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(120_000),
    })
    if (!res.ok) {
      throw new LLMBackendError(`OpenAI-compatible HTTP ${res.status}`)
    }
    return (await res.json()) as OpenAICompatResult
  }

  private mockChat(messages: ChatMessage[]): OpenAICompatResult {
    const lastUser = [...messages].reverse().find((m) => m.role === "user")
    const prefix = "[MOCK]"
    const content = `${prefix} Echo: ${(lastUser?.content ?? "").slice(0, 256)}`
    const now = Math.floor(Date.now() / 1000)
    return {
      id: `mock-${now}`,
      object: "chat.completion",
      created: now,
      model: "mock-llm",
      choices: [
        {
          index: 0,
          message: { role: "assistant", content },
          finish_reason: "stop",
        },
      ],
      usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
    }
  }

  async healthCheck(): Promise<{ healthy: boolean; backend: string; detail?: string }> {
    const { llmBackend } = this.cfg
    if (llmBackend === "mock" || llmBackend === "none" || llmBackend === "disabled") {
      return { healthy: true, backend: llmBackend }
    }
    if (llmBackend === "ollama") {
      try {
        const res = await fetch(`${this.cfg.llmRunnerUrl}/api/tags`, {
          signal: AbortSignal.timeout(5_000),
        })
        return { healthy: res.ok, backend: "ollama" }
      } catch (e) {
        return {
          healthy: false,
          backend: "ollama",
          detail: e instanceof Error ? e.message : String(e),
        }
      }
    }
    if (llmBackend === "vllm") {
      const base = this.cfg.llmRunnerUrl.replace(/\/$/, "")
      try {
        let res = await fetch(`${base}/health`, { signal: AbortSignal.timeout(5_000) })
        if (!res.ok) {
          res = await fetch(`${base}/v1/models`, { signal: AbortSignal.timeout(5_000) })
        }
        return { healthy: res.ok, backend: "vllm" }
      } catch (e) {
        return {
          healthy: false,
          backend: "vllm",
          detail: e instanceof Error ? e.message : String(e),
        }
      }
    }
    if (llmBackend === "huggingface" || llmBackend === "hf") {
      const headers: Record<string, string> = {}
      if (this.cfg.huggingfaceApiKey) {
        headers.Authorization = `Bearer ${this.cfg.huggingfaceApiKey}`
      }
      try {
        const res = await fetch(`${this.cfg.huggingfaceBaseUrl}/models`, {
          headers,
          signal: AbortSignal.timeout(10_000),
        })
        return { healthy: res.ok, backend: "huggingface" }
      } catch (e) {
        return {
          healthy: false,
          backend: "huggingface",
          detail: e instanceof Error ? e.message : String(e),
        }
      }
    }
    return { healthy: true, backend: llmBackend }
  }

  async listModels(): Promise<string[]> {
    if (this.cfg.llmBackend === "mock") {
      return ["mock-llm"]
    }
    if (this.cfg.llmBackend === "ollama") {
      try {
        const res = await fetch(`${this.cfg.llmRunnerUrl}/api/tags`, {
          signal: AbortSignal.timeout(10_000),
        })
        if (!res.ok) return []
        const data = (await res.json()) as { models?: Array<{ name: string }> }
        return (data.models ?? []).map((m) => m.name)
      } catch {
        return []
      }
    }
    if (this.cfg.llmBackend === "vllm") {
      const base = this.cfg.llmRunnerUrl.replace(/\/$/, "")
      try {
        const res = await fetch(`${base}/v1/models`, { signal: AbortSignal.timeout(10_000) })
        if (!res.ok) return []
        const data = (await res.json()) as { data?: Array<{ id: string }> }
        return (data.data ?? []).map((m) => m.id)
      } catch {
        return []
      }
    }
    if (this.cfg.llmBackend === "huggingface" || this.cfg.llmBackend === "hf") {
      const headers: Record<string, string> = {}
      if (this.cfg.huggingfaceApiKey) {
        headers.Authorization = `Bearer ${this.cfg.huggingfaceApiKey}`
      }
      try {
        const res = await fetch(`${this.cfg.huggingfaceBaseUrl}/models`, {
          headers,
          signal: AbortSignal.timeout(10_000),
        })
        if (!res.ok) return []
        const data = (await res.json()) as { data?: Array<{ id: string }> }
        return (data.data ?? []).map((m) => m.id)
      } catch {
        return []
      }
    }
    return []
  }

  getBackendInfo(): { type: string; model: string } {
    return {
      type: this.cfg.llmBackend,
      model:
        this.cfg.llmBackend === "vllm"
          ? this.cfg.vllmModel
          : this.cfg.llmBackend === "huggingface" || this.cfg.llmBackend === "hf"
            ? this.cfg.huggingfaceModel
          : this.cfg.ollamaModel,
    }
  }
}
