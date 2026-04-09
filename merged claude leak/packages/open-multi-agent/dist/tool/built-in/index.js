/**
 * Built-in tool collection.
 *
 * Re-exports every built-in tool and provides a convenience function to
 * register them all with a {@link ToolRegistry} in one call.
 */
import { bashTool } from './bash.js';
import { fileEditTool } from './file-edit.js';
import { fileReadTool } from './file-read.js';
import { fileWriteTool } from './file-write.js';
import { grepTool } from './grep.js';
export { bashTool, fileEditTool, fileReadTool, fileWriteTool, grepTool };
/**
 * The ordered list of all built-in tools.  Import this when you need to
 * iterate over them without calling `registerBuiltInTools`.
 *
 * The array is typed as `ToolDefinition<unknown>[]` so it can be passed to
 * APIs that accept any ToolDefinition without requiring a union type.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const BUILT_IN_TOOLS = [
    bashTool,
    fileReadTool,
    fileWriteTool,
    fileEditTool,
    grepTool,
];
/**
 * Register all built-in tools with the given registry.
 *
 * @example
 * ```ts
 * import { ToolRegistry } from '../framework.js'
 * import { registerBuiltInTools } from './built-in/index.js'
 *
 * const registry = new ToolRegistry()
 * registerBuiltInTools(registry)
 * ```
 */
export function registerBuiltInTools(registry) {
    for (const tool of BUILT_IN_TOOLS) {
        registry.register(tool);
    }
}
//# sourceMappingURL=index.js.map