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
import { Semaphore } from '../utils/semaphore.js';
/**
 * Executes tools from a {@link ToolRegistry}, validating input against each
 * tool's Zod schema and enforcing a concurrency limit for batch execution.
 *
 * All errors — including unknown tool names, Zod validation failures, and
 * execution exceptions — are caught and returned as `ToolResult` objects with
 * `isError: true` so the agent runner can forward them to the LLM.
 */
export class ToolExecutor {
    registry;
    semaphore;
    constructor(registry, options = {}) {
        this.registry = registry;
        this.semaphore = new Semaphore(options.maxConcurrency ?? 4);
    }
    // -------------------------------------------------------------------------
    // Single execution
    // -------------------------------------------------------------------------
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
    async execute(toolName, input, context) {
        const tool = this.registry.get(toolName);
        if (tool === undefined) {
            return this.errorResult(`Tool "${toolName}" is not registered in the ToolRegistry.`);
        }
        // Check abort before even starting
        if (context.abortSignal?.aborted === true) {
            return this.errorResult(`Tool "${toolName}" was aborted before execution began.`);
        }
        return this.runTool(tool, input, context);
    }
    // -------------------------------------------------------------------------
    // Batch execution
    // -------------------------------------------------------------------------
    /**
     * Execute multiple tool calls in parallel, honouring the concurrency limit.
     *
     * Returns a `Map` from call ID to result.  Every call in `calls` is
     * guaranteed to produce an entry — errors are captured as results.
     *
     * @param calls    Array of tool calls to execute.
     * @param context  Shared execution context for all calls in this batch.
     */
    async executeBatch(calls, context) {
        const results = new Map();
        await Promise.all(calls.map(async (call) => {
            const result = await this.semaphore.run(() => this.execute(call.name, call.input, context));
            results.set(call.id, result);
        }));
        return results;
    }
    // -------------------------------------------------------------------------
    // Private helpers
    // -------------------------------------------------------------------------
    /**
     * Validate input with the tool's Zod schema, then call `execute`.
     * Any synchronous or asynchronous error is caught and turned into an error
     * ToolResult.
     */
    async runTool(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    tool, rawInput, context) {
        // --- Zod validation ---
        const parseResult = tool.inputSchema.safeParse(rawInput);
        if (!parseResult.success) {
            const issues = parseResult.error.issues
                .map((issue) => `  • ${issue.path.join('.')}: ${issue.message}`)
                .join('\n');
            return this.errorResult(`Invalid input for tool "${tool.name}":\n${issues}`);
        }
        // --- Abort check after parse (parse can be expensive for large inputs) ---
        if (context.abortSignal?.aborted === true) {
            return this.errorResult(`Tool "${tool.name}" was aborted before execution began.`);
        }
        // --- Execute ---
        try {
            const result = await tool.execute(parseResult.data, context);
            return result;
        }
        catch (err) {
            const message = err instanceof Error
                ? err.message
                : typeof err === 'string'
                    ? err
                    : JSON.stringify(err);
            return this.errorResult(`Tool "${tool.name}" threw an error: ${message}`);
        }
    }
    /** Construct an error ToolResult. */
    errorResult(message) {
        return {
            data: message,
            isError: true,
        };
    }
}
//# sourceMappingURL=executor.js.map