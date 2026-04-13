/**
 * Built-in grep tool.
 *
 * Searches for a regex pattern in files.  Prefers the `rg` (ripgrep) binary
 * when available for performance; falls back to a pure Node.js recursive
 * implementation using the standard `fs` module so the tool works in
 * environments without ripgrep installed.
 */
export declare const grepTool: import("../framework.js").ToolDefinition<{
    pattern: string;
    glob?: string | undefined;
    path?: string | undefined;
    maxResults?: number | undefined;
}>;
//# sourceMappingURL=grep.d.ts.map