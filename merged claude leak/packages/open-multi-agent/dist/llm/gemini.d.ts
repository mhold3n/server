/**
 * @fileoverview Google Gemini adapter implementing {@link LLMAdapter}.
 *
 * Built for `@google/genai` (the unified Google Gen AI SDK, v1.x), NOT the
 * legacy `@google/generative-ai` package.
 *
 * Converts between the framework's internal {@link ContentBlock} types and the
 * `@google/genai` SDK's wire format, handling tool definitions, system prompts,
 * and both batch and streaming response paths.
 *
 * API key resolution order:
 *   1. `apiKey` constructor argument
 *   2. `GEMINI_API_KEY` environment variable
 *   3. `GOOGLE_API_KEY` environment variable
 *
 * @example
 * ```ts
 * import { GeminiAdapter } from './gemini.js'
 *
 * const adapter = new GeminiAdapter()
 * const response = await adapter.chat(messages, {
 *   model: 'gemini-2.5-flash',
 *   maxTokens: 1024,
 * })
 * ```
 */
import type { LLMAdapter, LLMChatOptions, LLMMessage, LLMResponse, LLMStreamOptions, StreamEvent } from '../types.js';
/**
 * LLM adapter backed by the Google Gemini API via `@google/genai`.
 *
 * Thread-safe — a single instance may be shared across concurrent agent runs.
 * The underlying SDK client is stateless across requests.
 */
export declare class GeminiAdapter implements LLMAdapter {
    #private;
    readonly name = "gemini";
    constructor(apiKey?: string);
    /**
     * Send a synchronous (non-streaming) chat request and return the complete
     * {@link LLMResponse}.
     *
     * Uses `ai.models.generateContent()` with the full conversation as `contents`,
     * which is the idiomatic pattern for `@google/genai`.
     */
    chat(messages: LLMMessage[], options: LLMChatOptions): Promise<LLMResponse>;
    /**
     * Send a streaming chat request and yield {@link StreamEvent}s as they
     * arrive from the API.
     *
     * Uses `ai.models.generateContentStream()` which returns an
     * `AsyncGenerator<GenerateContentResponse>`. Each yielded chunk has the same
     * shape as a full response but contains only the delta for that chunk.
     *
     * Because `@google/genai` doesn't expose a `finalMessage()` helper like the
     * Anthropic SDK, we accumulate content and token counts as we stream so that
     * the terminal `done` event carries a complete and accurate {@link LLMResponse}.
     *
     * Sequence guarantees (matching the Anthropic adapter):
     * - Zero or more `text` events with incremental deltas
     * - Zero or more `tool_use` events (one per call; Gemini doesn't stream args)
     * - Exactly one terminal event: `done` or `error`
     */
    stream(messages: LLMMessage[], options: LLMStreamOptions): AsyncIterable<StreamEvent>;
}
//# sourceMappingURL=gemini.d.ts.map