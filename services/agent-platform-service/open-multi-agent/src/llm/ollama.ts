/**
 * @fileoverview Ollama adapter implementing {@link LLMAdapter}.
 *
 * This targets Ollama's native `/api/chat` endpoint (not the OpenAI-compatible `/v1` shim)
 * so local inference can be used by the TypeScript agent-platform without a GPU worker.
 *
 * Environment variables:
 * - `OLLAMA_BASE_URL`: defaults to `http://127.0.0.1:11434`
 * - `OLLAMA_API_KEY`: optional; if set, sent as Bearer token
 */
import { randomUUID } from 'node:crypto'

import type {
  ContentBlock,
  ImageBlock,
  LLMAdapter,
  LLMChatOptions,
  LLMMessage,
  LLMResponse,
  LLMStreamOptions,
  LLMToolDef,
  StreamEvent,
  TextBlock,
  ToolResultBlock,
  ToolUseBlock,
} from '../types.js'
import { waitForGovernorAllowance, type GovernorProfile } from './host-memory-governor.js'

type OllamaRole = 'system' | 'user' | 'assistant' | 'tool'

interface OllamaToolCall {
  function: {
    name: string
    arguments: Record<string, unknown> | string
  }
}

interface OllamaChatMessage {
  role: OllamaRole
  content: string
  images?: string[]
  tool_calls?: OllamaToolCall[]
}

interface OllamaTool {
  type: 'function'
  function: {
    name: string
    description: string
    parameters: Record<string, unknown>
  }
}

interface OllamaChatResponse {
  model?: string
  message?: {
    role?: 'assistant'
    content?: string
    tool_calls?: OllamaToolCall[]
  }
  done_reason?: string
  prompt_eval_count?: number
  eval_count?: number
}

function normalizeBaseURL(baseURL: string | undefined): string {
  const raw = baseURL ?? process.env['OLLAMA_BASE_URL'] ?? 'http://127.0.0.1:11434'
  return raw.trim().replace(/\/+$/, '').replace(/\/v1$/i, '')
}

function modelForProfile(profile: GovernorProfile | undefined, fallback: string): string {
  const key =
    profile === 'large'
      ? 'OLLAMA_MODEL_LARGE'
      : profile === 'medium'
        ? 'OLLAMA_MODEL_MEDIUM'
        : profile === 'small'
          ? 'OLLAMA_MODEL_SMALL'
          : profile === 'tiny'
            ? 'OLLAMA_MODEL_TINY'
            : undefined
  const override = key ? process.env[key] : undefined
  return override && override.trim().length > 0 ? override.trim() : fallback
}

function authHeaders(apiKey: string | undefined): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const key = apiKey ?? process.env['OLLAMA_API_KEY']
  if (key && key !== 'ollama' && key !== 'ollama-local') {
    headers.Authorization = `Bearer ${key}`
  }
  return headers
}

function normalizeFinishReason(reason: string): 'stop' | 'tool_use' {
  // Ollama's `done_reason` varies by model/version; map common values.
  const r = reason.toLowerCase()
  if (r.includes('tool')) return 'tool_use'
  return 'stop'
}

function textFromBlocks(blocks: readonly ContentBlock[]): string {
  return blocks
    .filter((block): block is TextBlock => block.type === 'text')
    .map((block) => block.text)
    .join('')
}

function imagesFromBlocks(blocks: readonly ContentBlock[]): string[] {
  return blocks
    .filter((block): block is ImageBlock => block.type === 'image')
    .map((block) => block.source.data)
}

function toolUsesFromBlocks(blocks: readonly ContentBlock[]): OllamaToolCall[] {
  return blocks
    .filter((block): block is ToolUseBlock => block.type === 'tool_use')
    .map((block) => ({
      function: {
        name: block.name,
        arguments: block.input,
      },
    }))
}

function toolResultsFromBlocks(blocks: readonly ContentBlock[]): ToolResultBlock[] {
  return blocks.filter((block): block is ToolResultBlock => block.type === 'tool_result')
}

function toOllamaMessages(
  messages: readonly LLMMessage[],
  systemPrompt?: string,
): OllamaChatMessage[] {
  const result: OllamaChatMessage[] = []
  if (systemPrompt && systemPrompt.length > 0) {
    result.push({ role: 'system', content: systemPrompt })
  }

  for (const message of messages) {
    if (message.role === 'assistant') {
      const text = textFromBlocks(message.content)
      const toolCalls = toolUsesFromBlocks(message.content)
      result.push({
        role: 'assistant',
        content: text,
        ...(toolCalls.length > 0 ? { tool_calls: toolCalls } : {}),
      })
      continue
    }

    const text = textFromBlocks(message.content)
    const images = imagesFromBlocks(message.content)
    if (text.length > 0 || images.length > 0) {
      result.push({
        role: 'user',
        content: text,
        ...(images.length > 0 ? { images } : {}),
      })
    }

    for (const block of toolResultsFromBlocks(message.content)) {
      result.push({ role: 'tool', content: block.content })
    }
  }

  return result
}

function toOllamaTools(tools: readonly LLMToolDef[] | undefined): OllamaTool[] | undefined {
  if (!tools || tools.length === 0) return undefined
  return tools.map((tool) => ({
    type: 'function',
    function: {
      name: tool.name,
      description: tool.description,
      parameters: tool.inputSchema,
    },
  }))
}

function toRecord(value: Record<string, unknown> | string): Record<string, unknown> {
  if (typeof value !== 'string') return value
  try {
    const parsed: unknown = JSON.parse(value)
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>
    }
  } catch {
    // Ignore malformed args; surface as empty object.
  }
  return {}
}

function fromOllamaResponse(response: OllamaChatResponse, requestModel: string): LLMResponse {
  const content: ContentBlock[] = []
  const text = response.message?.content ?? ''
  if (text.length > 0) {
    content.push({ type: 'text', text })
  }

  for (const toolCall of response.message?.tool_calls ?? []) {
    content.push({
      type: 'tool_use',
      id: `ollama_call_${randomUUID()}`,
      name: toolCall.function.name,
      input: toRecord(toolCall.function.arguments),
    })
  }

  const hasToolUseBlocks = content.some((block) => block.type === 'tool_use')
  const stopReason = hasToolUseBlocks
    ? 'tool_use'
    : normalizeFinishReason(response.done_reason ?? 'stop')

  return {
    id: `ollama-${Date.now()}`,
    content,
    model: response.model ?? requestModel,
    stop_reason: stopReason,
    usage: {
      input_tokens: response.prompt_eval_count ?? 0,
      output_tokens: response.eval_count ?? 0,
    },
  }
}

export class OllamaAdapter implements LLMAdapter {
  readonly name = 'ollama'

  readonly #baseURL: string
  readonly #apiKey?: string

  constructor(apiKey?: string, baseURL?: string) {
    this.#apiKey = apiKey
    this.#baseURL = normalizeBaseURL(baseURL)
  }

  async health(): Promise<{ healthy: boolean; models?: string[] }> {
    try {
      const res = await fetch(`${this.#baseURL}/api/tags`, {
        headers: authHeaders(this.#apiKey),
      })
      if (!res.ok) return { healthy: false }
      const data = (await res.json()) as { models?: Array<{ name?: string; model?: string }> }
      return {
        healthy: true,
        models: (data.models ?? [])
          .map((model) => model.name ?? model.model)
          .filter((model): model is string => Boolean(model)),
      }
    } catch {
      return { healthy: false }
    }
  }

  async chat(messages: LLMMessage[], options: LLMChatOptions): Promise<LLMResponse> {
    const governorRec = await waitForGovernorAllowance({
      workload: 'ollama',
      abortSignal: options.abortSignal,
      pollIntervalMs: 1500,
    })
    if (governorRec && !governorRec.allow_start) {
      throw new Error(
        `Ollama blocked by host memory governor (${governorRec.target_profile}).`,
      )
    }
    const model = modelForProfile(governorRec?.target_profile, options.model)
    const payload = {
      model,
      messages: toOllamaMessages(messages, options.systemPrompt),
      stream: false,
      ...(options.tools && options.tools.length > 0 ? { tools: toOllamaTools(options.tools) } : {}),
      options: {
        ...(typeof options.temperature === 'number' ? { temperature: options.temperature } : {}),
        ...(typeof options.maxTokens === 'number' ? { num_predict: options.maxTokens } : {}),
      },
    }

    const res = await fetch(`${this.#baseURL}/api/chat`, {
      method: 'POST',
      headers: authHeaders(this.#apiKey),
      body: JSON.stringify(payload),
      signal: options.abortSignal,
    })
    if (!res.ok) {
      const body = await res.text().catch(() => '')
      throw new Error(`Ollama HTTP ${res.status}${body ? `: ${body}` : ''}`)
    }

    const data = (await res.json()) as OllamaChatResponse
    return fromOllamaResponse(data, model)
  }

  async *stream(messages: LLMMessage[], options: LLMStreamOptions): AsyncIterable<StreamEvent> {
    // Ollama supports streaming, but for parity with the rest of this codebase we
    // stream the already-produced content as discrete events.
    const response = await this.chat(messages, options)
    for (const block of response.content) {
      if (block.type === 'text') {
        yield { type: 'text', data: block.text }
      } else if (block.type === 'tool_use') {
        yield { type: 'tool_use', data: block }
      }
    }
    yield { type: 'done', data: response }
  }
}

