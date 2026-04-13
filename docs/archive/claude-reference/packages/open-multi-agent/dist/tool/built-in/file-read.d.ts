/**
 * Built-in file-read tool.
 *
 * Reads a file from disk and returns its contents with 1-based line numbers.
 * Supports reading a slice of lines via `offset` and `limit` for large files.
 */
export declare const fileReadTool: import("../framework.js").ToolDefinition<{
    path: string;
    offset?: number | undefined;
    limit?: number | undefined;
}>;
//# sourceMappingURL=file-read.d.ts.map