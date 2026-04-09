/**
 * @fileoverview High-level Agent class for open-multi-agent.
 *
 * {@link Agent} is the primary interface most consumers interact with.
 * It wraps {@link AgentRunner} with:
 *  - Persistent conversation history (`prompt()`)
 *  - Fresh-conversation semantics (`run()`)
 *  - Streaming support (`stream()`)
 *  - Dynamic tool registration at runtime
 *  - Full lifecycle state tracking (`idle → running → completed | error`)
 *
 * @example
 * ```ts
 * const agent = new Agent({
 *   name: 'researcher',
 *   model: 'claude-opus-4-6',
 *   systemPrompt: 'You are a rigorous research assistant.',
 *   tools: ['web_search', 'read_file'],
 * })
 *
 * const result = await agent.run('Summarise the last 3 IPCC reports.')
 * console.log(result.output)
 * ```
 */
import type { AgentConfig, AgentState, AgentRunResult, LLMMessage, StreamEvent, ToolUseContext } from '../types.js';
import type { ToolDefinition as FrameworkToolDefinition, ToolRegistry } from '../tool/framework.js';
import type { ToolExecutor } from '../tool/executor.js';
import { type RunOptions } from './runner.js';
/**
 * High-level wrapper around {@link AgentRunner} that manages conversation
 * history, state transitions, and tool lifecycle.
 */
export declare class Agent {
    readonly name: string;
    readonly config: AgentConfig;
    private runner;
    private state;
    private readonly _toolRegistry;
    private readonly _toolExecutor;
    private messageHistory;
    /**
     * @param config       - Static configuration for this agent.
     * @param toolRegistry - Registry used to resolve and manage tools.
     * @param toolExecutor - Executor that dispatches tool calls.
     *
     * `toolRegistry` and `toolExecutor` are injected rather than instantiated
     * internally so that teams of agents can share a single registry.
     */
    constructor(config: AgentConfig, toolRegistry: ToolRegistry, toolExecutor: ToolExecutor);
    /**
     * Lazily create the {@link AgentRunner}.
     *
     * The adapter is created asynchronously (it may lazy-import provider SDKs),
     * so we defer construction until the first `run` / `prompt` / `stream` call.
     */
    private getRunner;
    /**
     * Run `prompt` in a fresh conversation (history is NOT used).
     *
     * Equivalent to constructing a brand-new messages array `[{ role:'user', … }]`
     * and calling the runner once. The agent's persistent history is not modified.
     *
     * Use this for one-shot queries where past context is irrelevant.
     */
    run(prompt: string, runOptions?: Partial<RunOptions>): Promise<AgentRunResult>;
    /**
     * Run `prompt` as part of the ongoing conversation.
     *
     * Appends the user message to the persistent history, runs the agent, then
     * appends the resulting messages to the history for the next call.
     *
     * Use this for multi-turn interactions.
     */
    prompt(message: string): Promise<AgentRunResult>;
    /**
     * Stream a fresh-conversation response, yielding {@link StreamEvent}s.
     *
     * Like {@link run}, this does not use or update the persistent history.
     */
    stream(prompt: string): AsyncGenerator<StreamEvent>;
    /** Return a snapshot of the current agent state (does not clone nested objects). */
    getState(): AgentState;
    /** Return a copy of the persistent message history. */
    getHistory(): LLMMessage[];
    /**
     * Clear the persistent conversation history and reset state to `idle`.
     * Does NOT discard the runner instance — the adapter connection is reused.
     */
    reset(): void;
    /**
     * Register a new tool with this agent's tool registry at runtime.
     *
     * The tool becomes available to the next LLM call — no restart required.
     */
    addTool(tool: FrameworkToolDefinition): void;
    /**
     * Deregister a tool by name.
     * If the tool is not registered this is a no-op (no error is thrown).
     */
    removeTool(name: string): void;
    /** Return the names of all currently registered tools. */
    getTools(): string[];
    /**
     * Shared execution path used by both `run` and `prompt`.
     * Handles state transitions and error wrapping.
     */
    private executeRun;
    /** Emit an `agent` trace event if `onTrace` is provided. */
    private emitAgentTrace;
    /**
     * Validate agent output against the configured `outputSchema`.
     * On first validation failure, retry once with error feedback.
     */
    private validateStructuredOutput;
    /**
     * Shared streaming path used by `stream`.
     * Handles state transitions and error wrapping.
     */
    private executeStream;
    /** Extract the prompt text from the last user message to build hook context. */
    private buildBeforeRunHookContext;
    /**
     * Apply a (possibly modified) hook context back to the messages array.
     *
     * Only text blocks in the last user message are replaced; non-text content
     * (images, tool results) is preserved. The array element is replaced (not
     * mutated in place) so that shallow copies of the original array (e.g. from
     * `prompt()`) are not affected.
     */
    private applyHookContext;
    private transitionTo;
    private transitionToError;
    private toAgentRunResult;
    /**
     * Build a {@link ToolUseContext} that identifies this agent.
     * Exposed so team orchestrators can inject richer context (e.g. `TeamInfo`).
     */
    buildToolContext(abortSignal?: AbortSignal): ToolUseContext;
}
//# sourceMappingURL=agent.d.ts.map