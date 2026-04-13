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
import { GoogleGenAI, FunctionCallingConfigMode, } from '@google/genai';
// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------
/**
 * Map framework role names to Gemini role names.
 *
 * Gemini uses `"model"` instead of `"assistant"`.
 */
function toGeminiRole(role) {
    return role === 'assistant' ? 'model' : 'user';
}
/**
 * Convert framework messages into Gemini's {@link Content}[] format.
 *
 * Key differences from Anthropic:
 * - Gemini uses `"model"` instead of `"assistant"`.
 * - `functionResponse` parts (tool results) must appear in `"user"` turns.
 * - `functionCall` parts appear in `"model"` turns.
 * - We build a name lookup map from tool_use blocks so tool_result blocks
 *   can resolve the function name required by Gemini's `functionResponse`.
 */
function toGeminiContents(messages) {
    // First pass: build id → name map for resolving tool results.
    const toolNameById = new Map();
    for (const msg of messages) {
        for (const block of msg.content) {
            if (block.type === 'tool_use') {
                toolNameById.set(block.id, block.name);
            }
        }
    }
    return messages.map((msg) => {
        const parts = msg.content.map((block) => {
            switch (block.type) {
                case 'text':
                    return { text: block.text };
                case 'tool_use':
                    return {
                        functionCall: {
                            id: block.id,
                            name: block.name,
                            args: block.input,
                        },
                    };
                case 'tool_result': {
                    const name = toolNameById.get(block.tool_use_id) ?? block.tool_use_id;
                    return {
                        functionResponse: {
                            id: block.tool_use_id,
                            name,
                            response: {
                                content: typeof block.content === 'string'
                                    ? block.content
                                    : JSON.stringify(block.content),
                                isError: block.is_error ?? false,
                            },
                        },
                    };
                }
                case 'image':
                    return {
                        inlineData: {
                            mimeType: block.source.media_type,
                            data: block.source.data,
                        },
                    };
                default: {
                    const _exhaustive = block;
                    throw new Error(`Unhandled content block type: ${JSON.stringify(_exhaustive)}`);
                }
            }
        });
        return { role: toGeminiRole(msg.role), parts };
    });
}
/**
 * Convert framework {@link LLMToolDef}s into a Gemini `tools` config array.
 *
 * In `@google/genai`, function declarations use `parametersJsonSchema` (not
 * `parameters` or `input_schema`). All declarations are grouped under a single
 * tool entry.
 */
function toGeminiTools(tools) {
    const functionDeclarations = tools.map((t) => ({
        name: t.name,
        description: t.description,
        parametersJsonSchema: t.inputSchema,
    }));
    return [{ functionDeclarations }];
}
/**
 * Build the {@link GenerateContentConfig} shared by chat() and stream().
 */
function buildConfig(options) {
    return {
        maxOutputTokens: options.maxTokens ?? 4096,
        temperature: options.temperature,
        systemInstruction: options.systemPrompt,
        tools: options.tools ? toGeminiTools(options.tools) : undefined,
        toolConfig: options.tools
            ? { functionCallingConfig: { mode: FunctionCallingConfigMode.AUTO } }
            : undefined,
    };
}
/**
 * Generate a stable pseudo-random ID string for tool use blocks.
 *
 * Gemini may not always return call IDs (especially in streaming), so we
 * fabricate them when absent to satisfy the framework's {@link ToolUseBlock}
 * contract.
 */
function generateId() {
    return `gemini-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}
/**
 * Extract the function call ID from a Gemini part, or generate one.
 *
 * The `id` field exists in newer API versions but may be absent in older
 * responses, so we cast conservatively and fall back to a generated ID.
 */
function getFunctionCallId(part) {
    return part.functionCall?.id ?? generateId();
}
/**
 * Convert a Gemini {@link GenerateContentResponse} into a framework
 * {@link LLMResponse}.
 */
function fromGeminiResponse(response, id, model) {
    const candidate = response.candidates?.[0];
    const content = [];
    for (const part of candidate?.content?.parts ?? []) {
        if (part.text !== undefined && part.text !== '') {
            content.push({ type: 'text', text: part.text });
        }
        else if (part.functionCall !== undefined) {
            content.push({
                type: 'tool_use',
                id: getFunctionCallId(part),
                name: part.functionCall.name ?? '',
                input: (part.functionCall.args ?? {}),
            });
        }
        // inlineData echoes and other part types are silently ignored.
    }
    // Map Gemini finish reasons to framework stop_reason vocabulary.
    const finishReason = candidate?.finishReason;
    let stop_reason = 'end_turn';
    if (finishReason === 'MAX_TOKENS') {
        stop_reason = 'max_tokens';
    }
    else if (content.some((b) => b.type === 'tool_use')) {
        // Gemini may report STOP even when it returned function calls.
        stop_reason = 'tool_use';
    }
    const usage = response.usageMetadata;
    return {
        id,
        content,
        model,
        stop_reason,
        usage: {
            input_tokens: usage?.promptTokenCount ?? 0,
            output_tokens: usage?.candidatesTokenCount ?? 0,
        },
    };
}
// ---------------------------------------------------------------------------
// Adapter implementation
// ---------------------------------------------------------------------------
/**
 * LLM adapter backed by the Google Gemini API via `@google/genai`.
 *
 * Thread-safe — a single instance may be shared across concurrent agent runs.
 * The underlying SDK client is stateless across requests.
 */
export class GeminiAdapter {
    name = 'gemini';
    #client;
    constructor(apiKey) {
        this.#client = new GoogleGenAI({
            apiKey: apiKey ?? process.env['GEMINI_API_KEY'] ?? process.env['GOOGLE_API_KEY'],
        });
    }
    // -------------------------------------------------------------------------
    // chat()
    // -------------------------------------------------------------------------
    /**
     * Send a synchronous (non-streaming) chat request and return the complete
     * {@link LLMResponse}.
     *
     * Uses `ai.models.generateContent()` with the full conversation as `contents`,
     * which is the idiomatic pattern for `@google/genai`.
     */
    async chat(messages, options) {
        const id = generateId();
        const contents = toGeminiContents(messages);
        const response = await this.#client.models.generateContent({
            model: options.model,
            contents,
            config: buildConfig(options),
        });
        return fromGeminiResponse(response, id, options.model);
    }
    // -------------------------------------------------------------------------
    // stream()
    // -------------------------------------------------------------------------
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
    async *stream(messages, options) {
        const id = generateId();
        const contents = toGeminiContents(messages);
        try {
            const streamResponse = await this.#client.models.generateContentStream({
                model: options.model,
                contents,
                config: buildConfig(options),
            });
            // Accumulators for building the done payload.
            const accumulatedContent = [];
            let inputTokens = 0;
            let outputTokens = 0;
            let lastFinishReason;
            for await (const chunk of streamResponse) {
                const candidate = chunk.candidates?.[0];
                // Accumulate token counts — the API emits these on the final chunk.
                if (chunk.usageMetadata) {
                    inputTokens = chunk.usageMetadata.promptTokenCount ?? inputTokens;
                    outputTokens = chunk.usageMetadata.candidatesTokenCount ?? outputTokens;
                }
                if (candidate?.finishReason) {
                    lastFinishReason = candidate.finishReason;
                }
                for (const part of candidate?.content?.parts ?? []) {
                    if (part.text) {
                        accumulatedContent.push({ type: 'text', text: part.text });
                        yield { type: 'text', data: part.text };
                    }
                    else if (part.functionCall) {
                        const toolId = getFunctionCallId(part);
                        const toolUseBlock = {
                            type: 'tool_use',
                            id: toolId,
                            name: part.functionCall.name ?? '',
                            input: (part.functionCall.args ?? {}),
                        };
                        accumulatedContent.push(toolUseBlock);
                        yield { type: 'tool_use', data: toolUseBlock };
                    }
                }
            }
            // Determine stop_reason from the accumulated response.
            const hasToolUse = accumulatedContent.some((b) => b.type === 'tool_use');
            let stop_reason = 'end_turn';
            if (lastFinishReason === 'MAX_TOKENS') {
                stop_reason = 'max_tokens';
            }
            else if (hasToolUse) {
                stop_reason = 'tool_use';
            }
            const finalResponse = {
                id,
                content: accumulatedContent,
                model: options.model,
                stop_reason,
                usage: { input_tokens: inputTokens, output_tokens: outputTokens },
            };
            yield { type: 'done', data: finalResponse };
        }
        catch (err) {
            const error = err instanceof Error ? err : new Error(String(err));
            yield { type: 'error', data: error };
        }
    }
}
//# sourceMappingURL=gemini.js.map