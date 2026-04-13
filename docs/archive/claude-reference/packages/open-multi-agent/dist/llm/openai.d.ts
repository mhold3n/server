/**
 * @fileoverview OpenAI adapter implementing {@link LLMAdapter}.
 *
 * Converts between the framework's internal {@link ContentBlock} types and the
 * OpenAI Chat Completions wire format. Key mapping decisions:
 *
 * - Framework `tool_use` blocks in assistant messages → OpenAI `tool_calls`
 * - Framework `tool_result` blocks in user messages  → OpenAI `tool` role messages
 * - Framework `image` blocks in user messages        → OpenAI image content parts
 * - System prompt in {@link LLMChatOptions}           → prepended `system` message
 *
 * Because OpenAI and Anthropic use fundamentally different role-based structures
 * for tool calling (Anthropic embeds tool results in user-role content arrays;
 * OpenAI uses a dedicated `tool` role), the conversion necessarily splits
 * `tool_result` blocks out into separate top-level messages.
 *
 * API key resolution order:
 *   1. `apiKey` constructor argument
 *   2. `OPENAI_API_KEY` environment variable
 *
 * @example
 * ```ts
 * import { OpenAIAdapter } from './openai.js'
 *
 * const adapter = new OpenAIAdapter()
 * const response = await adapter.chat(messages, {
 *   model: 'gpt-5.4',
 *   maxTokens: 1024,
 * })
 * ```
 */
import type { ContentBlock, LLMAdapter, LLMChatOptions, LLMMessage, LLMResponse, LLMStreamOptions, LLMToolDef, StreamEvent } from '../types.js';
/**
 * LLM adapter backed by the OpenAI Chat Completions API.
 *
 * Thread-safe — a single instance may be shared across concurrent agent runs.
 */
export declare class OpenAIAdapter implements LLMAdapter {
    #private;
    readonly name: string;
    constructor(apiKey?: string, baseURL?: string);
    /**
     * Send a synchronous (non-streaming) chat request and return the complete
     * {@link LLMResponse}.
     *
     * Throws an `OpenAI.APIError` on non-2xx responses. Callers should catch and
     * handle these (e.g. rate limits, context length exceeded).
     */
    chat(messages: LLMMessage[], options: LLMChatOptions): Promise<LLMResponse>;
    /**
     * Send a streaming chat request and yield {@link StreamEvent}s incrementally.
     *
     * Sequence guarantees match {@link AnthropicAdapter.stream}:
     * - Zero or more `text` events
     * - Zero or more `tool_use` events (emitted once per tool call, after
     *   arguments have been fully assembled)
     * - Exactly one terminal event: `done` or `error`
     */
    stream(messages: LLMMessage[], options: LLMStreamOptions): AsyncIterable<StreamEvent>;
}
export type { ContentBlock, LLMAdapter, LLMChatOptions, LLMMessage, LLMResponse, LLMStreamOptions, LLMToolDef, StreamEvent, };
//# sourceMappingURL=openai.d.ts.map