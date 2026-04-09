/**
 * Built-in bash tool.
 *
 * Executes a shell command and returns its stdout + stderr.  Supports an
 * optional timeout and a custom working directory.
 */
export declare const bashTool: import("../framework.js").ToolDefinition<{
    command: string;
    timeout?: number | undefined;
    cwd?: string | undefined;
}>;
//# sourceMappingURL=bash.d.ts.map