/**
 * @fileoverview Anthropic Claude adapter implementing {@link LLMAdapter}.
 *
 * Converts between the framework's internal {@link ContentBlock} types and the
 * Anthropic SDK's wire format, handling tool definitions, system prompts, and
 * both batch and streaming response paths.
 *
 * API key resolution order:
 *   1. `apiKey` constructor argument
 *   2. `ANTHROPIC_API_KEY` environment variable
 *
 * @example
 * ```ts
 * import { AnthropicAdapter } from './anthropic.js'
 *
 * const adapter = new AnthropicAdapter()
 * const response = await adapter.chat(messages, {
 *   model: 'claude-opus-4-6',
 *   maxTokens: 1024,
 * })
 * ```
 */
import type { ContentBlock, ImageBlock, LLMAdapter, LLMChatOptions, LLMMessage, LLMResponse, LLMStreamOptions, LLMToolDef, StreamEvent, TextBlock, ToolResultBlock, ToolUseBlock } from '../types.js';
/**
 * LLM adapter backed by the Anthropic Claude API.
 *
 * Thread-safe — a single instance may be shared across concurrent agent runs.
 * The underlying SDK client is stateless across requests.
 */
export declare class AnthropicAdapter implements LLMAdapter {
    #private;
    readonly name = "anthropic";
    constructor(apiKey?: string, baseURL?: string);
    /**
     * Send a synchronous (non-streaming) chat request and return the complete
     * {@link LLMResponse}.
     *
     * Throws an `Anthropic.APIError` on non-2xx responses. Callers should catch
     * and handle these (e.g. rate limits, context window exceeded).
     */
    chat(messages: LLMMessage[], options: LLMChatOptions): Promise<LLMResponse>;
    /**
     * Send a streaming chat request and yield {@link StreamEvent}s as they
     * arrive from the API.
     *
     * Sequence guarantees:
     * - Zero or more `text` events containing incremental deltas
     * - Zero or more `tool_use` events when the model calls a tool (emitted once
     *   per tool use, after input JSON has been fully assembled)
     * - Exactly one terminal event: `done` (with the complete {@link LLMResponse}
     *   as `data`) or `error` (with an `Error` as `data`)
     */
    stream(messages: LLMMessage[], options: LLMStreamOptions): AsyncIterable<StreamEvent>;
}
export type { ContentBlock, ImageBlock, LLMAdapter, LLMChatOptions, LLMMessage, LLMResponse, LLMStreamOptions, LLMToolDef, StreamEvent, TextBlock, ToolResultBlock, ToolUseBlock, };
//# sourceMappingURL=anthropic.d.ts.map