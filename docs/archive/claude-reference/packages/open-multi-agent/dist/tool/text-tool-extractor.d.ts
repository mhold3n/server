/**
 * @fileoverview Fallback tool-call extractor for local models.
 *
 * When a local model (Ollama, vLLM, LM Studio) returns tool calls as plain
 * text instead of using the OpenAI `tool_calls` wire format, this module
 * attempts to extract them from the text output.
 *
 * Common scenarios:
 * - Ollama thinking-model bug: tool call JSON ends up inside unclosed `<think>` tags
 * - Model outputs raw JSON tool calls without the server parsing them
 * - Model wraps tool calls in markdown code fences
 * - Hermes-format `<tool_call>` tags
 *
 * This is a **safety net**, not the primary path. Native `tool_calls` from
 * the server are always preferred.
 */
import type { ToolUseBlock } from '../types.js';
/**
 * Attempt to extract tool calls from a model's text output.
 *
 * Tries multiple strategies in order:
 * 1. Hermes `<tool_call>` tags
 * 2. JSON objects in text (bare or inside code fences)
 *
 * @param text           - The model's text output.
 * @param knownToolNames - Whitelist of registered tool names. When non-empty,
 *                         only JSON objects whose `name` matches a known tool
 *                         are treated as tool calls.
 * @returns Extracted {@link ToolUseBlock}s, or an empty array if none found.
 */
export declare function extractToolCallsFromText(text: string, knownToolNames: string[]): ToolUseBlock[];
//# sourceMappingURL=text-tool-extractor.d.ts.map