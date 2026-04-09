/**
 * Parallel tool executor with concurrency control and error isolation.
 *
 * Validates input via Zod schemas, enforces a maximum concurrency limit using
 * a lightweight semaphore, tracks execution duration, and surfaces any
 * execution errors as ToolResult objects rather than thrown exceptions.
 *
 * Types are imported from `../types` to ensure consistency with the rest of
 * the framework.
 */
import type { ToolResult, ToolUseContext } from '../types.js';
import { ToolRegistry } from './framework.js';
export interface ToolExecutorOptions {
    /**
     * Maximum number of tool calls that may run in parallel.
     * Defaults to 4.
     */
    maxConcurrency?: number;
}
/** Describes one call in a batch. */
export interface BatchToolCall {
    /** Caller-assigned ID used as the key in the result map. */
    id: string;
    /** Registered tool name. */
    name: string;
    /** Raw (unparsed) input object from the LLM. */
    input: Record<string, unknown>;
}
/**
 * Executes tools from a {@link ToolRegistry}, validating input against each
 * tool's Zod schema and enforcing a concurrency limit for batch execution.
 *
 * All errors — including unknown tool names, Zod validation failures, and
 * execution exceptions — are caught and returned as `ToolResult` objects with
 * `isError: true` so the agent runner can forward them to the LLM.
 */
export declare class ToolExecutor {
    private readonly registry;
    private readonly semaphore;
    constructor(registry: ToolRegistry, options?: ToolExecutorOptions);
    /**
     * Execute a single tool by name.
     *
     * Errors are caught and returned as a {@link ToolResult} with
     * `isError: true` — this method itself never rejects.
     *
     * @param toolName  The registered tool name.
     * @param input     Raw input object (before Zod validation).
     * @param context   Execution context forwarded to the tool.
     */
    execute(toolName: string, input: Record<string, unknown>, context: ToolUseContext): Promise<ToolResult>;
    /**
     * Execute multiple tool calls in parallel, honouring the concurrency limit.
     *
     * Returns a `Map` from call ID to result.  Every call in `calls` is
     * guaranteed to produce an entry — errors are captured as results.
     *
     * @param calls    Array of tool calls to execute.
     * @param context  Shared execution context for all calls in this batch.
     */
    executeBatch(calls: BatchToolCall[], context: ToolUseContext): Promise<Map<string, ToolResult>>;
    /**
     * Validate input with the tool's Zod schema, then call `execute`.
     * Any synchronous or asynchronous error is caught and turned into an error
     * ToolResult.
     */
    private runTool;
    /** Construct an error ToolResult. */
    private errorResult;
}
//# sourceMappingURL=executor.d.ts.map