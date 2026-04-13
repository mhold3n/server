/**
 * @fileoverview Shared OpenAI wire-format conversion helpers.
 *
 * Both the OpenAI and Copilot adapters use the OpenAI Chat Completions API
 * format. This module contains the common conversion logic so it isn't
 * duplicated across adapters.
 */
import type { ChatCompletion, ChatCompletionMessageParam, ChatCompletionTool } from 'openai/resources/chat/completions/index.js';
import type { LLMMessage, LLMResponse, LLMToolDef } from '../types.js';
/**
 * Convert a framework {@link LLMToolDef} to an OpenAI {@link ChatCompletionTool}.
 */
export declare function toOpenAITool(tool: LLMToolDef): ChatCompletionTool;
/**
 * Convert framework {@link LLMMessage}s into OpenAI
 * {@link ChatCompletionMessageParam} entries.
 *
 * `tool_result` blocks are expanded into top-level `tool`-role messages
 * because OpenAI uses a dedicated role for tool results rather than embedding
 * them inside user-content arrays.
 */
export declare function toOpenAIMessages(messages: LLMMessage[]): ChatCompletionMessageParam[];
/**
 * Convert an OpenAI {@link ChatCompletion} into a framework {@link LLMResponse}.
 *
 * Takes only the first choice (index 0), consistent with how the framework
 * is designed for single-output agents.
 *
 * @param completion      - The raw OpenAI completion.
 * @param knownToolNames  - Optional whitelist of tool names. When the model
 *                          returns no `tool_calls` but the text contains JSON
 *                          that looks like a tool call, the fallback extractor
 *                          uses this list to validate matches. Pass the names
 *                          of tools sent in the request for best results.
 */
export declare function fromOpenAICompletion(completion: ChatCompletion, knownToolNames?: string[]): LLMResponse;
/**
 * Normalize an OpenAI `finish_reason` string to the framework's canonical
 * stop-reason vocabulary.
 *
 * Mapping:
 * - `'stop'`           → `'end_turn'`
 * - `'tool_calls'`     → `'tool_use'`
 * - `'length'`         → `'max_tokens'`
 * - `'content_filter'` → `'content_filter'`
 * - anything else      → passed through unchanged
 */
export declare function normalizeFinishReason(reason: string): string;
/**
 * Prepend a system message when `systemPrompt` is provided, then append the
 * converted conversation messages.
 */
export declare function buildOpenAIMessageList(messages: LLMMessage[], systemPrompt: string | undefined): ChatCompletionMessageParam[];
//# sourceMappingURL=openai-common.d.ts.map