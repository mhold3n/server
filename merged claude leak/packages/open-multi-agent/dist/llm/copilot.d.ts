/**
 * @fileoverview GitHub Copilot adapter implementing {@link LLMAdapter}.
 *
 * Uses the OpenAI-compatible Copilot Chat Completions endpoint at
 * `https://api.githubcopilot.com`. Authentication requires a GitHub token
 * which is exchanged for a short-lived Copilot session token via the
 * internal token endpoint.
 *
 * API key resolution order:
 *   1. `apiKey` constructor argument
 *   2. `GITHUB_COPILOT_TOKEN` environment variable
 *   3. `GITHUB_TOKEN` environment variable
 *   4. Interactive OAuth2 device flow (prompts the user to sign in)
 *
 * @example
 * ```ts
 * import { CopilotAdapter } from './copilot.js'
 *
 * const adapter = new CopilotAdapter()          // uses GITHUB_COPILOT_TOKEN, falling back to GITHUB_TOKEN
 * const response = await adapter.chat(messages, {
 *   model: 'claude-sonnet-4',
 *   maxTokens: 4096,
 * })
 * ```
 */
import type { LLMAdapter, LLMChatOptions, LLMMessage, LLMResponse, LLMStreamOptions, StreamEvent } from '../types.js';
/**
 * Callback invoked when the OAuth2 device flow needs the user to authorize.
 * Receives the verification URI and user code. If not provided, defaults to
 * printing them to stdout.
 */
export type DeviceCodeCallback = (verificationUri: string, userCode: string) => void;
/** Options for the {@link CopilotAdapter} constructor. */
export interface CopilotAdapterOptions {
    /** GitHub OAuth token already scoped for Copilot. Falls back to env vars. */
    apiKey?: string;
    /**
     * Callback invoked when the OAuth2 device flow needs user action.
     * Defaults to printing the verification URI and user code to stdout.
     */
    onDeviceCode?: DeviceCodeCallback;
}
/**
 * LLM adapter backed by the GitHub Copilot Chat Completions API.
 *
 * Authentication options (tried in order):
 *   1. `apiKey` constructor arg — a GitHub OAuth token already scoped for Copilot
 *   2. `GITHUB_COPILOT_TOKEN` env var
 *   3. `GITHUB_TOKEN` env var
 *   4. Interactive OAuth2 device flow
 *
 * The GitHub token is exchanged for a short-lived Copilot session token, which
 * is cached and auto-refreshed.
 *
 * Thread-safe — a single instance may be shared across concurrent agent runs.
 * Concurrent token refreshes are serialised via an internal mutex.
 */
export declare class CopilotAdapter implements LLMAdapter {
    #private;
    readonly name = "copilot";
    constructor(apiKeyOrOptions?: string | CopilotAdapterOptions);
    chat(messages: LLMMessage[], options: LLMChatOptions): Promise<LLMResponse>;
    stream(messages: LLMMessage[], options: LLMStreamOptions): AsyncIterable<StreamEvent>;
}
/**
 * Model metadata used for display names, context windows, and premium request
 * multiplier lookup.
 */
export interface CopilotModelInfo {
    readonly id: string;
    readonly name: string;
    readonly contextWindow: number;
}
/**
 * Return the premium-request multiplier for a Copilot model.
 *
 * Copilot doesn't charge per-token — instead each request costs
 * `multiplier × 1 premium request` from the user's monthly allowance.
 * A multiplier of 0 means the model is included at no premium cost.
 *
 * Based on https://docs.github.com/en/copilot/reference/ai-models/supported-models#model-multipliers
 */
export declare function getCopilotMultiplier(modelId: string): number;
/**
 * Human-readable string describing the premium-request cost for a model.
 *
 * Examples: `"included (0×)"`, `"1× premium request"`, `"0.33× premium request"`
 */
export declare function formatCopilotMultiplier(multiplier: number): string;
/** Known model metadata for Copilot-available models. */
export declare const COPILOT_MODELS: readonly CopilotModelInfo[];
//# sourceMappingURL=copilot.d.ts.map