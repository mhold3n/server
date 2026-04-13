/**
 * Tool definition framework for open-multi-agent.
 *
 * Provides the core primitives for declaring, registering, and converting
 * tools to the JSON Schema format that LLM APIs expect.
 *
 * Types shared with the rest of the framework (`ToolDefinition`, `ToolResult`,
 * `ToolUseContext`) are imported from `../types` to ensure a single source of
 * truth.  This file re-exports them for the convenience of downstream callers
 * who only need to import from `tool/framework`.
 */
import { type ZodSchema } from 'zod';
import type { ToolDefinition, ToolResult, ToolUseContext, LLMToolDef } from '../types.js';
export type { ToolDefinition, ToolResult, ToolUseContext };
/** Minimal JSON Schema for a single property. */
export type JSONSchemaProperty = {
    type: 'string';
    description?: string;
    enum?: string[];
} | {
    type: 'number';
    description?: string;
} | {
    type: 'integer';
    description?: string;
} | {
    type: 'boolean';
    description?: string;
} | {
    type: 'null';
    description?: string;
} | {
    type: 'array';
    items: JSONSchemaProperty;
    description?: string;
} | {
    type: 'object';
    properties: Record<string, JSONSchemaProperty>;
    required?: string[];
    description?: string;
} | {
    anyOf: JSONSchemaProperty[];
    description?: string;
} | {
    const: unknown;
    description?: string;
} | Record<string, unknown>;
/**
 * Define a typed tool.  This is the single entry-point for creating tools
 * that can be registered with a {@link ToolRegistry}.
 *
 * The returned object satisfies the {@link ToolDefinition} interface imported
 * from `../types`.
 *
 * @example
 * ```ts
 * const echoTool = defineTool({
 *   name: 'echo',
 *   description: 'Echo the input message back to the caller.',
 *   inputSchema: z.object({ message: z.string() }),
 *   execute: async ({ message }) => ({
 *     data: message,
 *     isError: false,
 *   }),
 * })
 * ```
 */
export declare function defineTool<TInput>(config: {
    name: string;
    description: string;
    inputSchema: ZodSchema<TInput>;
    execute: (input: TInput, context: ToolUseContext) => Promise<ToolResult>;
}): ToolDefinition<TInput>;
/**
 * Registry that holds a set of named tools and can produce the JSON Schema
 * representation expected by LLM APIs (Anthropic, OpenAI, etc.).
 */
export declare class ToolRegistry {
    private readonly tools;
    private readonly runtimeToolNames;
    /**
     * Add a tool to the registry.  Throws if a tool with the same name has
     * already been registered — prevents silent overwrites.
     */
    register(tool: ToolDefinition<any>, options?: {
        runtimeAdded?: boolean;
    }): void;
    /** Return a tool by name, or `undefined` if not found. */
    get(name: string): ToolDefinition<any> | undefined;
    /**
     * Return all registered tool definitions as an array.
     *
     * Callers that only need names can do `registry.list().map(t => t.name)`.
     * This matches the agent's `getTools()` pattern.
     */
    list(): ToolDefinition<any>[];
    /**
     * Return all registered tool definitions as an array.
     * Alias for {@link list} — available for callers that prefer explicit naming.
     */
    getAll(): ToolDefinition<any>[];
    /** Return true when a tool with the given name is registered. */
    has(name: string): boolean;
    /**
     * Remove a tool by name.
     * No-op if the tool was not registered — matches the agent's expected
     * behaviour where `removeTool` is a graceful operation.
     */
    unregister(name: string): void;
    /** Alias for {@link unregister} — available for symmetry with `register`. */
    deregister(name: string): void;
    /**
     * Convert all registered tools to the {@link LLMToolDef} format used by LLM
     * adapters.  This is the primary method called by the agent runner before
     * each LLM API call.
     */
    toToolDefs(): LLMToolDef[];
    /**
     * Return only tools that were added dynamically at runtime (e.g. via
     * `agent.addTool()`), in LLM definition format.
     */
    toRuntimeToolDefs(): LLMToolDef[];
    /**
     * Convert all registered tools to the Anthropic-style `input_schema`
     * format.  Prefer {@link toToolDefs} for normal use; this method is exposed
     * for callers that construct their own API payloads.
     */
    toLLMTools(): Array<{
        name: string;
        description: string;
        input_schema: {
            type: 'object';
            properties: Record<string, JSONSchemaProperty>;
            required?: string[];
        };
    }>;
}
/**
 * Convert a Zod schema to a plain JSON Schema object suitable for inclusion
 * in LLM API calls.
 *
 * Supported Zod types:
 *   z.string(), z.number(), z.boolean(), z.enum(), z.array(), z.object(),
 *   z.optional(), z.union(), z.literal(), z.describe(), z.nullable(),
 *   z.default(), z.intersection(), z.discriminatedUnion(), z.record(),
 *   z.tuple(), z.any(), z.unknown(), z.never(), z.effects() (transforms)
 *
 * Unsupported types fall back to `{}` (any) which is still valid JSON Schema.
 */
export declare function zodToJsonSchema(schema: ZodSchema): Record<string, unknown>;
//# sourceMappingURL=framework.d.ts.map