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
import Anthropic from '@anthropic-ai/sdk';
// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------
/**
 * Convert a single framework {@link ContentBlock} into an Anthropic
 * {@link ContentBlockParam} suitable for the `messages` array.
 *
 * `tool_result` blocks are only valid inside `user`-role messages, which is
 * handled by {@link toAnthropicMessages} based on role context.
 */
function toAnthropicContentBlockParam(block) {
    switch (block.type) {
        case 'text': {
            const param = { type: 'text', text: block.text };
            return param;
        }
        case 'tool_use': {
            const param = {
                type: 'tool_use',
                id: block.id,
                name: block.name,
                input: block.input,
            };
            return param;
        }
        case 'tool_result': {
            const param = {
                type: 'tool_result',
                tool_use_id: block.tool_use_id,
                content: block.content,
                is_error: block.is_error,
            };
            return param;
        }
        case 'image': {
            // Anthropic only accepts a subset of MIME types; we pass them through
            // trusting the caller to supply a valid media_type value.
            const param = {
                type: 'image',
                source: {
                    type: 'base64',
                    media_type: block.source.media_type,
                    data: block.source.data,
                },
            };
            return param;
        }
        default: {
            // Exhaustiveness guard — TypeScript will flag this at compile time if a
            // new variant is added to ContentBlock without updating this switch.
            const _exhaustive = block;
            throw new Error(`Unhandled content block type: ${JSON.stringify(_exhaustive)}`);
        }
    }
}
/**
 * Convert framework messages into Anthropic's `MessageParam[]` format.
 *
 * The Anthropic API requires strict user/assistant alternation. We do not
 * enforce that here — the caller is responsible for producing a valid
 * conversation history.
 */
function toAnthropicMessages(messages) {
    return messages.map((msg) => ({
        role: msg.role,
        content: msg.content.map(toAnthropicContentBlockParam),
    }));
}
/**
 * Convert framework {@link LLMToolDef}s into Anthropic's `Tool` objects.
 *
 * The `inputSchema` on {@link LLMToolDef} is already a plain JSON Schema
 * object, so we just need to reshape the wrapper.
 */
function toAnthropicTools(tools) {
    return tools.map((t) => ({
        name: t.name,
        description: t.description,
        input_schema: {
            type: 'object',
            ...t.inputSchema,
        },
    }));
}
/**
 * Convert an Anthropic SDK `ContentBlock` into a framework {@link ContentBlock}.
 *
 * We only map the subset of SDK types that the framework exposes. Unknown
 * variants (thinking, server_tool_use, etc.) are converted to a text block
 * carrying a stringified representation so data is never silently dropped.
 */
function fromAnthropicContentBlock(block) {
    switch (block.type) {
        case 'text': {
            const text = { type: 'text', text: block.text };
            return text;
        }
        case 'tool_use': {
            const toolUse = {
                type: 'tool_use',
                id: block.id,
                name: block.name,
                input: block.input,
            };
            return toolUse;
        }
        default: {
            // Graceful degradation for SDK types we don't model (thinking, etc.).
            const fallback = {
                type: 'text',
                text: `[unsupported block type: ${block.type}]`,
            };
            return fallback;
        }
    }
}
// ---------------------------------------------------------------------------
// Adapter implementation
// ---------------------------------------------------------------------------
/**
 * LLM adapter backed by the Anthropic Claude API.
 *
 * Thread-safe — a single instance may be shared across concurrent agent runs.
 * The underlying SDK client is stateless across requests.
 */
export class AnthropicAdapter {
    name = 'anthropic';
    #client;
    constructor(apiKey, baseURL) {
        this.#client = new Anthropic({
            apiKey: apiKey ?? process.env['ANTHROPIC_API_KEY'],
            baseURL,
        });
    }
    // -------------------------------------------------------------------------
    // chat()
    // -------------------------------------------------------------------------
    /**
     * Send a synchronous (non-streaming) chat request and return the complete
     * {@link LLMResponse}.
     *
     * Throws an `Anthropic.APIError` on non-2xx responses. Callers should catch
     * and handle these (e.g. rate limits, context window exceeded).
     */
    async chat(messages, options) {
        const anthropicMessages = toAnthropicMessages(messages);
        const response = await this.#client.messages.create({
            model: options.model,
            max_tokens: options.maxTokens ?? 4096,
            messages: anthropicMessages,
            system: options.systemPrompt,
            tools: options.tools ? toAnthropicTools(options.tools) : undefined,
            temperature: options.temperature,
        }, {
            signal: options.abortSignal,
        });
        const content = response.content.map(fromAnthropicContentBlock);
        return {
            id: response.id,
            content,
            model: response.model,
            stop_reason: response.stop_reason ?? 'end_turn',
            usage: {
                input_tokens: response.usage.input_tokens,
                output_tokens: response.usage.output_tokens,
            },
        };
    }
    // -------------------------------------------------------------------------
    // stream()
    // -------------------------------------------------------------------------
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
    async *stream(messages, options) {
        const anthropicMessages = toAnthropicMessages(messages);
        // MessageStream gives us typed events and handles SSE reconnect internally.
        const stream = this.#client.messages.stream({
            model: options.model,
            max_tokens: options.maxTokens ?? 4096,
            messages: anthropicMessages,
            system: options.systemPrompt,
            tools: options.tools ? toAnthropicTools(options.tools) : undefined,
            temperature: options.temperature,
        }, {
            signal: options.abortSignal,
        });
        // Accumulate tool-use input JSON as it streams in.
        // key = content block index, value = partially assembled input JSON string
        const toolInputBuffers = new Map();
        try {
            for await (const event of stream) {
                switch (event.type) {
                    case 'content_block_start': {
                        const block = event.content_block;
                        if (block.type === 'tool_use') {
                            toolInputBuffers.set(event.index, {
                                id: block.id,
                                name: block.name,
                                json: '',
                            });
                        }
                        break;
                    }
                    case 'content_block_delta': {
                        const delta = event.delta;
                        if (delta.type === 'text_delta') {
                            const textEvent = { type: 'text', data: delta.text };
                            yield textEvent;
                        }
                        else if (delta.type === 'input_json_delta') {
                            const buf = toolInputBuffers.get(event.index);
                            if (buf !== undefined) {
                                buf.json += delta.partial_json;
                            }
                        }
                        break;
                    }
                    case 'content_block_stop': {
                        const buf = toolInputBuffers.get(event.index);
                        if (buf !== undefined) {
                            // Parse the accumulated JSON and emit a tool_use event.
                            let parsedInput = {};
                            try {
                                const parsed = JSON.parse(buf.json);
                                if (parsed !== null &&
                                    typeof parsed === 'object' &&
                                    !Array.isArray(parsed)) {
                                    parsedInput = parsed;
                                }
                            }
                            catch {
                                // Malformed JSON from the model — surface as an empty object
                                // rather than crashing the stream.
                            }
                            const toolUseBlock = {
                                type: 'tool_use',
                                id: buf.id,
                                name: buf.name,
                                input: parsedInput,
                            };
                            const toolUseEvent = { type: 'tool_use', data: toolUseBlock };
                            yield toolUseEvent;
                            toolInputBuffers.delete(event.index);
                        }
                        break;
                    }
                    // message_start, message_delta, message_stop — we handle the final
                    // response via stream.finalMessage() below rather than piecemeal.
                    default:
                        break;
                }
            }
            // Await the fully assembled final message (token counts, stop_reason, etc.)
            const finalMessage = await stream.finalMessage();
            const content = finalMessage.content.map(fromAnthropicContentBlock);
            const finalResponse = {
                id: finalMessage.id,
                content,
                model: finalMessage.model,
                stop_reason: finalMessage.stop_reason ?? 'end_turn',
                usage: {
                    input_tokens: finalMessage.usage.input_tokens,
                    output_tokens: finalMessage.usage.output_tokens,
                },
            };
            const doneEvent = { type: 'done', data: finalResponse };
            yield doneEvent;
        }
        catch (err) {
            const error = err instanceof Error ? err : new Error(String(err));
            const errorEvent = { type: 'error', data: error };
            yield errorEvent;
        }
    }
}
//# sourceMappingURL=anthropic.js.map