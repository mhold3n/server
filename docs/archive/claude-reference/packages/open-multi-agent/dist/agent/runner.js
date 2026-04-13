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
import { TokenBudgetExceededError } from '../errors.js';
import { LoopDetector } from './loop-detector.js';
import { emitTrace } from '../utils/trace.js';
// ---------------------------------------------------------------------------
// Tool presets
// ---------------------------------------------------------------------------
/** Predefined tool sets for common agent use cases. */
export const TOOL_PRESETS = {
    readonly: ['file_read', 'grep', 'glob'],
    readwrite: ['file_read', 'file_write', 'file_edit', 'grep', 'glob'],
    full: ['file_read', 'file_write', 'file_edit', 'grep', 'glob', 'bash'],
};
/** Framework-level disallowed tools for safety rails. */
export const AGENT_FRAMEWORK_DISALLOWED = [
// Empty for now, infrastructure for future built-in tools
];
// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------
/** Extract every TextBlock from a content array and join them. */
function extractText(content) {
    return content
        .filter((b) => b.type === 'text')
        .map(b => b.text)
        .join('');
}
/** Extract every ToolUseBlock from a content array. */
function extractToolUseBlocks(content) {
    return content.filter((b) => b.type === 'tool_use');
}
/** Add two {@link TokenUsage} values together, returning a new object. */
function addTokenUsage(a, b) {
    return {
        input_tokens: a.input_tokens + b.input_tokens,
        output_tokens: a.output_tokens + b.output_tokens,
    };
}
const ZERO_USAGE = { input_tokens: 0, output_tokens: 0 };
// ---------------------------------------------------------------------------
// AgentRunner
// ---------------------------------------------------------------------------
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
export class AgentRunner {
    adapter;
    toolRegistry;
    toolExecutor;
    options;
    maxTurns;
    constructor(adapter, toolRegistry, toolExecutor, options) {
        this.adapter = adapter;
        this.toolRegistry = toolRegistry;
        this.toolExecutor = toolExecutor;
        this.options = options;
        this.maxTurns = options.maxTurns ?? 10;
    }
    // -------------------------------------------------------------------------
    // Tool resolution
    // -------------------------------------------------------------------------
    /**
     * Resolve the final set of tools available to this agent based on the
     * three-layer configuration: preset → allowlist → denylist → framework safety.
     *
     * Returns LLMToolDef[] for direct use with LLM adapters.
     */
    resolveTools() {
        // Validate configuration for contradictions
        if (this.options.toolPreset && this.options.allowedTools) {
            console.warn('AgentRunner: both toolPreset and allowedTools are set. ' +
                'Final tool access will be the intersection of both.');
        }
        if (this.options.allowedTools && this.options.disallowedTools) {
            const overlap = this.options.allowedTools.filter(tool => this.options.disallowedTools.includes(tool));
            if (overlap.length > 0) {
                console.warn(`AgentRunner: tools [${overlap.map(name => `"${name}"`).join(', ')}] appear in both allowedTools and disallowedTools. ` +
                    'This is contradictory and may lead to unexpected behavior.');
            }
        }
        const allTools = this.toolRegistry.toToolDefs();
        const runtimeCustomTools = this.toolRegistry.toRuntimeToolDefs();
        const runtimeCustomToolNames = new Set(runtimeCustomTools.map(t => t.name));
        let filteredTools = allTools.filter(t => !runtimeCustomToolNames.has(t.name));
        // 1. Apply preset filter if set
        if (this.options.toolPreset) {
            const presetTools = new Set(TOOL_PRESETS[this.options.toolPreset]);
            filteredTools = filteredTools.filter(t => presetTools.has(t.name));
        }
        // 2. Apply allowlist filter if set
        if (this.options.allowedTools) {
            filteredTools = filteredTools.filter(t => this.options.allowedTools.includes(t.name));
        }
        // 3. Apply denylist filter if set
        if (this.options.disallowedTools) {
            const denied = new Set(this.options.disallowedTools);
            filteredTools = filteredTools.filter(t => !denied.has(t.name));
        }
        // 4. Apply framework-level safety rails
        const frameworkDenied = new Set(AGENT_FRAMEWORK_DISALLOWED);
        filteredTools = filteredTools.filter(t => !frameworkDenied.has(t.name));
        // Runtime-added custom tools stay available regardless of filtering rules.
        return [...filteredTools, ...runtimeCustomTools];
    }
    // -------------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------------
    /**
     * Run a complete conversation starting from `messages`.
     *
     * The call may internally make multiple LLM requests (one per tool-call
     * round-trip). It returns only when:
     *  - The LLM emits `end_turn` with no tool-use blocks, or
     *  - `maxTurns` is exceeded, or
     *  - The abort signal is triggered.
     */
    async run(messages, options = {}) {
        // Collect everything yielded by the internal streaming loop.
        const accumulated = {
            messages: [],
            output: '',
            toolCalls: [],
            tokenUsage: ZERO_USAGE,
            turns: 0,
        };
        for await (const event of this.stream(messages, options)) {
            if (event.type === 'done') {
                Object.assign(accumulated, event.data);
            }
        }
        return accumulated;
    }
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
    async *stream(initialMessages, options = {}) {
        // Working copy of the conversation — mutated as turns progress.
        const conversationMessages = [...initialMessages];
        // Accumulated state across all turns.
        let totalUsage = ZERO_USAGE;
        const allToolCalls = [];
        let finalOutput = '';
        let turns = 0;
        let budgetExceeded = false;
        // Build the stable LLM options once; model / tokens / temp don't change.
        // resolveTools() returns LLMToolDef[] with three-layer filtering applied.
        const toolDefs = this.resolveTools();
        // Per-call abortSignal takes precedence over the static one.
        const effectiveAbortSignal = options.abortSignal ?? this.options.abortSignal;
        const baseChatOptions = {
            model: this.options.model,
            tools: toolDefs.length > 0 ? toolDefs : undefined,
            maxTokens: this.options.maxTokens,
            temperature: this.options.temperature,
            systemPrompt: this.options.systemPrompt,
            abortSignal: effectiveAbortSignal,
        };
        // Loop detection state — only allocated when configured.
        const detector = this.options.loopDetection
            ? new LoopDetector(this.options.loopDetection)
            : null;
        let loopDetected = false;
        let loopWarned = false;
        const loopAction = this.options.loopDetection?.onLoopDetected ?? 'warn';
        try {
            // -----------------------------------------------------------------
            // Main agentic loop — `while (true)` until end_turn or maxTurns
            // -----------------------------------------------------------------
            while (true) {
                // Respect abort before each LLM call.
                if (effectiveAbortSignal?.aborted) {
                    break;
                }
                // Guard against unbounded loops.
                if (turns >= this.maxTurns) {
                    break;
                }
                turns++;
                // ------------------------------------------------------------------
                // Step 1: Call the LLM and collect the full response for this turn.
                // ------------------------------------------------------------------
                const llmStartMs = Date.now();
                const response = await this.adapter.chat(conversationMessages, baseChatOptions);
                if (options.onTrace) {
                    const llmEndMs = Date.now();
                    emitTrace(options.onTrace, {
                        type: 'llm_call',
                        runId: options.runId ?? '',
                        taskId: options.taskId,
                        agent: options.traceAgent ?? this.options.agentName ?? 'unknown',
                        model: this.options.model,
                        turn: turns,
                        tokens: response.usage,
                        startMs: llmStartMs,
                        endMs: llmEndMs,
                        durationMs: llmEndMs - llmStartMs,
                    });
                }
                totalUsage = addTokenUsage(totalUsage, response.usage);
                // ------------------------------------------------------------------
                // Step 2: Build the assistant message from the response content.
                // ------------------------------------------------------------------
                const assistantMessage = {
                    role: 'assistant',
                    content: response.content,
                };
                conversationMessages.push(assistantMessage);
                options.onMessage?.(assistantMessage);
                // Yield text deltas so streaming callers can display them promptly.
                const turnText = extractText(response.content);
                if (turnText.length > 0) {
                    yield { type: 'text', data: turnText };
                }
                const totalTokens = totalUsage.input_tokens + totalUsage.output_tokens;
                if (this.options.maxTokenBudget !== undefined && totalTokens > this.options.maxTokenBudget) {
                    budgetExceeded = true;
                    finalOutput = turnText;
                    yield {
                        type: 'budget_exceeded',
                        data: new TokenBudgetExceededError(this.options.agentName ?? 'unknown', totalTokens, this.options.maxTokenBudget),
                    };
                    break;
                }
                // Extract tool-use blocks for detection and execution.
                const toolUseBlocks = extractToolUseBlocks(response.content);
                // ------------------------------------------------------------------
                // Step 2.5: Loop detection — check before yielding tool_use events
                // so that terminate mode doesn't emit orphaned tool_use without
                // matching tool_result.
                // ------------------------------------------------------------------
                let injectWarning = false;
                let injectWarningKind = 'tool_repetition';
                if (detector && toolUseBlocks.length > 0) {
                    const toolInfo = detector.recordToolCalls(toolUseBlocks);
                    const textInfo = turnText.length > 0 ? detector.recordText(turnText) : null;
                    const info = toolInfo ?? textInfo;
                    if (info) {
                        yield { type: 'loop_detected', data: info };
                        options.onWarning?.(info.detail);
                        const action = typeof loopAction === 'function'
                            ? await loopAction(info)
                            : loopAction;
                        if (action === 'terminate') {
                            loopDetected = true;
                            finalOutput = turnText;
                            break;
                        }
                        else if (action === 'warn' || action === 'inject') {
                            if (loopWarned) {
                                // Second detection after a warning — force terminate.
                                loopDetected = true;
                                finalOutput = turnText;
                                break;
                            }
                            loopWarned = true;
                            injectWarning = true;
                            injectWarningKind = info.kind;
                            // Fall through to execute tools, then inject warning.
                        }
                        // 'continue' — do nothing, let the loop proceed normally.
                    }
                    else {
                        // No loop detected this turn — agent has recovered, so reset
                        // the warning state. A future loop gets a fresh warning cycle.
                        loopWarned = false;
                    }
                }
                // ------------------------------------------------------------------
                // Step 3: Decide whether to continue looping.
                // ------------------------------------------------------------------
                if (toolUseBlocks.length === 0) {
                    // Warn on first turn if tools were provided but model didn't use them.
                    if (turns === 1 && toolDefs.length > 0 && options.onWarning) {
                        const agentName = this.options.agentName ?? 'unknown';
                        options.onWarning(`Agent "${agentName}" has ${toolDefs.length} tool(s) available but the model ` +
                            `returned no tool calls. If using a local model, verify it supports tool calling ` +
                            `(see https://ollama.com/search?c=tools).`);
                    }
                    // No tools requested — this is the terminal assistant turn.
                    finalOutput = turnText;
                    break;
                }
                // Announce each tool-use block the model requested (after loop
                // detection, so terminate mode never emits unpaired events).
                for (const block of toolUseBlocks) {
                    yield { type: 'tool_use', data: block };
                }
                // ------------------------------------------------------------------
                // Step 4: Execute all tool calls in PARALLEL.
                //
                // Parallel execution is critical for multi-tool responses where the
                // tools are independent (e.g. reading several files at once).
                // ------------------------------------------------------------------
                const toolContext = this.buildToolContext();
                const executionPromises = toolUseBlocks.map(async (block) => {
                    options.onToolCall?.(block.name, block.input);
                    const startTime = Date.now();
                    let result;
                    try {
                        result = await this.toolExecutor.execute(block.name, block.input, toolContext);
                    }
                    catch (err) {
                        // Tool executor errors become error results — the loop continues.
                        const message = err instanceof Error ? err.message : String(err);
                        result = { data: message, isError: true };
                    }
                    const endTime = Date.now();
                    const duration = endTime - startTime;
                    options.onToolResult?.(block.name, result);
                    if (options.onTrace) {
                        emitTrace(options.onTrace, {
                            type: 'tool_call',
                            runId: options.runId ?? '',
                            taskId: options.taskId,
                            agent: options.traceAgent ?? this.options.agentName ?? 'unknown',
                            tool: block.name,
                            isError: result.isError ?? false,
                            startMs: startTime,
                            endMs: endTime,
                            durationMs: duration,
                        });
                    }
                    const record = {
                        toolName: block.name,
                        input: block.input,
                        output: result.data,
                        duration,
                    };
                    const resultBlock = {
                        type: 'tool_result',
                        tool_use_id: block.id,
                        content: result.data,
                        is_error: result.isError,
                    };
                    return { resultBlock, record };
                });
                // Wait for every tool in this turn to finish.
                const executions = await Promise.all(executionPromises);
                // ------------------------------------------------------------------
                // Step 5: Accumulate results and build the user message that carries
                //         them back to the LLM in the next turn.
                // ------------------------------------------------------------------
                const toolResultBlocks = executions.map(e => e.resultBlock);
                for (const { record, resultBlock } of executions) {
                    allToolCalls.push(record);
                    yield { type: 'tool_result', data: resultBlock };
                }
                // Inject a loop-detection warning into the tool-result message so
                // the LLM sees it alongside the results (avoids two consecutive user
                // messages which violates the alternating-role constraint).
                if (injectWarning) {
                    const warningText = injectWarningKind === 'text_repetition'
                        ? 'WARNING: You appear to be generating the same response repeatedly. ' +
                            'This suggests you are stuck in a loop. Please try a different approach ' +
                            'or provide new information.'
                        : 'WARNING: You appear to be repeating the same tool calls with identical arguments. ' +
                            'This suggests you are stuck in a loop. Please try a different approach, use different ' +
                            'parameters, or explain what you are trying to accomplish.';
                    toolResultBlocks.push({ type: 'text', text: warningText });
                }
                const toolResultMessage = {
                    role: 'user',
                    content: toolResultBlocks,
                };
                conversationMessages.push(toolResultMessage);
                options.onMessage?.(toolResultMessage);
                // Loop back to Step 1 — send updated conversation to the LLM.
            }
        }
        catch (err) {
            const error = err instanceof Error ? err : new Error(String(err));
            yield { type: 'error', data: error };
            return;
        }
        // If the loop exited due to maxTurns, use whatever text was last emitted.
        if (finalOutput === '' && conversationMessages.length > 0) {
            const lastAssistant = [...conversationMessages]
                .reverse()
                .find(m => m.role === 'assistant');
            if (lastAssistant !== undefined) {
                finalOutput = extractText(lastAssistant.content);
            }
        }
        const runResult = {
            // Return only the messages added during this run (not the initial seed).
            messages: conversationMessages.slice(initialMessages.length),
            output: finalOutput,
            toolCalls: allToolCalls,
            tokenUsage: totalUsage,
            turns,
            ...(loopDetected ? { loopDetected: true } : {}),
            ...(budgetExceeded ? { budgetExceeded: true } : {}),
        };
        yield { type: 'done', data: runResult };
    }
    // -------------------------------------------------------------------------
    // Private helpers
    // -------------------------------------------------------------------------
    /**
     * Build the {@link ToolUseContext} passed to every tool execution.
     * Identifies this runner as the invoking agent.
     */
    buildToolContext() {
        return {
            agent: {
                name: this.options.agentName ?? 'runner',
                role: this.options.agentRole ?? 'assistant',
                model: this.options.model,
            },
            abortSignal: this.options.abortSignal,
        };
    }
}
//# sourceMappingURL=runner.js.map