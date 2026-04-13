/**
 * @fileoverview Core conversation loop engine for open-multi-agent.
 *
 * {@link AgentRunner} is the heart of the framework. It handles:
 *  - Sending messages to the LLM adapter
 *  - Extracting tool-use blocks from the response
 *  - Executing tool calls in parallel via {@link ToolExecutor}
 *  - Appending tool results and looping back until `end_turn`
 *  - Accumulating token usage and timing data across all turns
 *
 * The loop follows a standard agentic conversation pattern:
 * one outer `while (true)` that breaks on `end_turn` or maxTurns exhaustion.
 */
import type { LLMMessage, ToolCallRecord, TokenUsage, StreamEvent, ToolResult, LLMAdapter, TraceEvent, LoopDetectionConfig } from '../types.js';
import type { ToolRegistry } from '../tool/framework.js';
import type { ToolExecutor } from '../tool/executor.js';
/** Predefined tool sets for common agent use cases. */
export declare const TOOL_PRESETS: {
    readonly readonly: readonly ["file_read", "grep", "glob"];
    readonly readwrite: readonly ["file_read", "file_write", "file_edit", "grep", "glob"];
    readonly full: readonly ["file_read", "file_write", "file_edit", "grep", "glob", "bash"];
};
/** Framework-level disallowed tools for safety rails. */
export declare const AGENT_FRAMEWORK_DISALLOWED: readonly string[];
/**
 * Static configuration for an {@link AgentRunner} instance.
 * These values are constant across every `run` / `stream` call.
 */
export interface RunnerOptions {
    /** LLM model identifier, e.g. `'claude-opus-4-6'`. */
    readonly model: string;
    /** Optional system prompt prepended to every conversation. */
    readonly systemPrompt?: string;
    /**
     * Maximum number of tool-call round-trips before the runner stops.
     * Prevents unbounded loops. Defaults to `10`.
     */
    readonly maxTurns?: number;
    /** Maximum output tokens per LLM response. */
    readonly maxTokens?: number;
    /** Sampling temperature passed to the adapter. */
    readonly temperature?: number;
    /** AbortSignal that cancels any in-flight adapter call and stops the loop. */
    readonly abortSignal?: AbortSignal;
    /**
     * Tool access control configuration.
     * - `toolPreset`: Predefined tool sets for common use cases
     * - `allowedTools`: Whitelist of tool names (allowlist)
     * - `disallowedTools`: Blacklist of tool names (denylist)
     * Tools are resolved in order: preset → allowlist → denylist
     */
    readonly toolPreset?: 'readonly' | 'readwrite' | 'full';
    readonly allowedTools?: readonly string[];
    readonly disallowedTools?: readonly string[];
    /** Display name of the agent driving this runner (used in tool context). */
    readonly agentName?: string;
    /** Short role description of the agent (used in tool context). */
    readonly agentRole?: string;
    /** Loop detection configuration. When set, detects stuck agent loops. */
    readonly loopDetection?: LoopDetectionConfig;
    /** Maximum cumulative tokens (input + output) allowed for this run. */
    readonly maxTokenBudget?: number;
}
/**
 * Per-call callbacks for observing tool execution in real time.
 * All callbacks are optional; unused ones are simply skipped.
 */
export interface RunOptions {
    /** Fired just before each tool is dispatched. */
    readonly onToolCall?: (name: string, input: Record<string, unknown>) => void;
    /** Fired after each tool result is received. */
    readonly onToolResult?: (name: string, result: ToolResult) => void;
    /** Fired after each complete {@link LLMMessage} is appended. */
    readonly onMessage?: (message: LLMMessage) => void;
    /**
     * Fired when the runner detects a potential configuration issue.
     * For example, when a model appears to ignore tool definitions.
     */
    readonly onWarning?: (message: string) => void;
    /** Trace callback for observability spans. Async callbacks are safe. */
    readonly onTrace?: (event: TraceEvent) => void | Promise<void>;
    /** Run ID for trace correlation. */
    readonly runId?: string;
    /** Task ID for trace correlation. */
    readonly taskId?: string;
    /** Agent name for trace correlation (overrides RunnerOptions.agentName). */
    readonly traceAgent?: string;
    /**
     * Per-call abort signal. When set, takes precedence over the static
     * {@link RunnerOptions.abortSignal}. Useful for per-run timeouts.
     */
    readonly abortSignal?: AbortSignal;
}
/** The aggregated result returned when a full run completes. */
export interface RunResult {
    /** All messages accumulated during this run (assistant + tool results). */
    readonly messages: LLMMessage[];
    /** The final text output from the last assistant turn. */
    readonly output: string;
    /** All tool calls made during this run, in execution order. */
    readonly toolCalls: ToolCallRecord[];
    /** Aggregated token counts across every LLM call in this run. */
    readonly tokenUsage: TokenUsage;
    /** Total number of LLM turns (including tool-call follow-ups). */
    readonly turns: number;
    /** True when the run was terminated or warned due to loop detection. */
    readonly loopDetected?: boolean;
    /** True when the run was terminated due to token budget limits. */
    readonly budgetExceeded?: boolean;
}
/**
 * Drives a full agentic conversation: LLM calls, tool execution, and looping.
 *
 * @example
 * ```ts
 * const runner = new AgentRunner(adapter, registry, executor, {
 *   model: 'claude-opus-4-6',
 *   maxTurns: 10,
 * })
 * const result = await runner.run(messages)
 * console.log(result.output)
 * ```
 */
export declare class AgentRunner {
    private readonly adapter;
    private readonly toolRegistry;
    private readonly toolExecutor;
    private readonly options;
    private readonly maxTurns;
    constructor(adapter: LLMAdapter, toolRegistry: ToolRegistry, toolExecutor: ToolExecutor, options: RunnerOptions);
    /**
     * Resolve the final set of tools available to this agent based on the
     * three-layer configuration: preset → allowlist → denylist → framework safety.
     *
     * Returns LLMToolDef[] for direct use with LLM adapters.
     */
    private resolveTools;
    /**
     * Run a complete conversation starting from `messages`.
     *
     * The call may internally make multiple LLM requests (one per tool-call
     * round-trip). It returns only when:
     *  - The LLM emits `end_turn` with no tool-use blocks, or
     *  - `maxTurns` is exceeded, or
     *  - The abort signal is triggered.
     */
    run(messages: LLMMessage[], options?: RunOptions): Promise<RunResult>;
    /**
     * Run the conversation and yield {@link StreamEvent}s incrementally.
     *
     * Callers receive:
     *  - `{ type: 'text', data: string }` for each text delta
     *  - `{ type: 'tool_use', data: ToolUseBlock }` when the model requests a tool
     *  - `{ type: 'tool_result', data: ToolResultBlock }` after each execution
   *  - `{ type: 'budget_exceeded', data: TokenBudgetExceededError }` on budget trip
     *  - `{ type: 'done', data: RunResult }` at the very end
     *  - `{ type: 'error', data: Error }` on unrecoverable failure
     */
    stream(initialMessages: LLMMessage[], options?: RunOptions): AsyncGenerator<StreamEvent>;
    /**
     * Build the {@link ToolUseContext} passed to every tool execution.
     * Identifies this runner as the invoking agent.
     */
    private buildToolContext;
}
//# sourceMappingURL=runner.d.ts.map