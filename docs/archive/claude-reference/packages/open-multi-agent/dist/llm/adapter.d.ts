/**
 * @fileoverview LLM adapter factory.
 *
 * Re-exports the {@link LLMAdapter} interface and provides a
 * {@link createAdapter} factory that returns the correct concrete
 * implementation based on the requested provider.
 *
 * @example
 * ```ts
 * import { createAdapter } from './adapter.js'
 *
 * const anthropic = createAdapter('anthropic')
 * const openai    = createAdapter('openai', process.env.OPENAI_API_KEY)
 * const gemini    = createAdapter('gemini', process.env.GEMINI_API_KEY)
 * ```
 */
export type { LLMAdapter, LLMChatOptions, LLMStreamOptions, LLMToolDef, LLMMessage, LLMResponse, StreamEvent, TokenUsage, ContentBlock, TextBlock, ToolUseBlock, ToolResultBlock, ImageBlock, } from '../types.js';
import type { LLMAdapter } from '../types.js';
/**
 * The set of LLM providers supported out of the box.
 * Additional providers can be integrated by implementing {@link LLMAdapter}
 * directly and bypassing this factory.
 */
export type SupportedProvider = 'anthropic' | 'copilot' | 'grok' | 'openai' | 'gemini' | 'ollama';
/**
 * Instantiate the appropriate {@link LLMAdapter} for the given provider.
 *
 * API keys fall back to the standard environment variables when not supplied
 * explicitly:
 * - `anthropic` → `ANTHROPIC_API_KEY`
 * - `openai`    → `OPENAI_API_KEY`
 * - `gemini`    → `GEMINI_API_KEY` / `GOOGLE_API_KEY`
 * - `grok`      → `XAI_API_KEY`
 * - `ollama`    → `OLLAMA_API_KEY` (optional; local servers usually use a placeholder)
 * - `copilot`   → `GITHUB_COPILOT_TOKEN` / `GITHUB_TOKEN`, or interactive
 *                  OAuth2 device flow if neither is set
 *
 * Adapters are imported lazily so that projects using only one provider
 * are not forced to install the SDK for the other.
 *
 * @param provider - Which LLM provider to target.
 * @param apiKey   - Optional API key override; falls back to env var.
 * @param baseURL  - Optional base URL for OpenAI-compatible APIs (Ollama, vLLM, etc.).
 * @throws {Error} When the provider string is not recognised.
 */
export declare function createAdapter(provider: SupportedProvider, apiKey?: string, baseURL?: string): Promise<LLMAdapter>;
//# sourceMappingURL=adapter.d.ts.map