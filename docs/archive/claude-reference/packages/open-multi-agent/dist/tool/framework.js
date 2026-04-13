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
// ---------------------------------------------------------------------------
// defineTool
// ---------------------------------------------------------------------------
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
export function defineTool(config) {
    return {
        name: config.name,
        description: config.description,
        inputSchema: config.inputSchema,
        execute: config.execute,
    };
}
// ---------------------------------------------------------------------------
// ToolRegistry
// ---------------------------------------------------------------------------
/**
 * Registry that holds a set of named tools and can produce the JSON Schema
 * representation expected by LLM APIs (Anthropic, OpenAI, etc.).
 */
export class ToolRegistry {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    tools = new Map();
    runtimeToolNames = new Set();
    /**
     * Add a tool to the registry.  Throws if a tool with the same name has
     * already been registered — prevents silent overwrites.
     */
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    register(tool, options) {
        if (this.tools.has(tool.name)) {
            throw new Error(`ToolRegistry: a tool named "${tool.name}" is already registered. ` +
                'Use a unique name or deregister the existing one first.');
        }
        this.tools.set(tool.name, tool);
        if (options?.runtimeAdded === true) {
            this.runtimeToolNames.add(tool.name);
        }
    }
    /** Return a tool by name, or `undefined` if not found. */
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    get(name) {
        return this.tools.get(name);
    }
    /**
     * Return all registered tool definitions as an array.
     *
     * Callers that only need names can do `registry.list().map(t => t.name)`.
     * This matches the agent's `getTools()` pattern.
     */
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    list() {
        return Array.from(this.tools.values());
    }
    /**
     * Return all registered tool definitions as an array.
     * Alias for {@link list} — available for callers that prefer explicit naming.
     */
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    getAll() {
        return Array.from(this.tools.values());
    }
    /** Return true when a tool with the given name is registered. */
    has(name) {
        return this.tools.has(name);
    }
    /**
     * Remove a tool by name.
     * No-op if the tool was not registered — matches the agent's expected
     * behaviour where `removeTool` is a graceful operation.
     */
    unregister(name) {
        this.tools.delete(name);
        this.runtimeToolNames.delete(name);
    }
    /** Alias for {@link unregister} — available for symmetry with `register`. */
    deregister(name) {
        this.unregister(name);
    }
    /**
     * Convert all registered tools to the {@link LLMToolDef} format used by LLM
     * adapters.  This is the primary method called by the agent runner before
     * each LLM API call.
     */
    toToolDefs() {
        return Array.from(this.tools.values()).map((tool) => {
            const schema = zodToJsonSchema(tool.inputSchema);
            return {
                name: tool.name,
                description: tool.description,
                inputSchema: schema,
            };
        });
    }
    /**
     * Return only tools that were added dynamically at runtime (e.g. via
     * `agent.addTool()`), in LLM definition format.
     */
    toRuntimeToolDefs() {
        return this.toToolDefs().filter(tool => this.runtimeToolNames.has(tool.name));
    }
    /**
     * Convert all registered tools to the Anthropic-style `input_schema`
     * format.  Prefer {@link toToolDefs} for normal use; this method is exposed
     * for callers that construct their own API payloads.
     */
    toLLMTools() {
        return Array.from(this.tools.values()).map((tool) => {
            const schema = zodToJsonSchema(tool.inputSchema);
            return {
                name: tool.name,
                description: tool.description,
                input_schema: {
                    type: 'object',
                    properties: schema.properties ?? {},
                    ...(schema.required !== undefined
                        ? { required: schema.required }
                        : {}),
                },
            };
        });
    }
}
// ---------------------------------------------------------------------------
// zodToJsonSchema
// ---------------------------------------------------------------------------
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
export function zodToJsonSchema(schema) {
    return convertZodType(schema);
}
// Internal recursive converter.  We access Zod's internal `_def` structure
// because Zod v3 does not ship a first-class JSON Schema exporter.
function convertZodType(schema) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const def = schema._def;
    const description = def.description;
    const withDesc = (result) => description !== undefined ? { ...result, description } : result;
    switch (def.typeName) {
        // -----------------------------------------------------------------------
        // Primitives
        // -----------------------------------------------------------------------
        case ZodTypeName.ZodString:
            return withDesc({ type: 'string' });
        case ZodTypeName.ZodNumber:
            return withDesc({ type: 'number' });
        case ZodTypeName.ZodBigInt:
            return withDesc({ type: 'integer' });
        case ZodTypeName.ZodBoolean:
            return withDesc({ type: 'boolean' });
        case ZodTypeName.ZodNull:
            return withDesc({ type: 'null' });
        case ZodTypeName.ZodUndefined:
            return withDesc({ type: 'null' });
        case ZodTypeName.ZodDate:
            return withDesc({ type: 'string', format: 'date-time' });
        // -----------------------------------------------------------------------
        // Literals
        // -----------------------------------------------------------------------
        case ZodTypeName.ZodLiteral: {
            const literalDef = def;
            return withDesc({ const: literalDef.value });
        }
        // -----------------------------------------------------------------------
        // Enums
        // -----------------------------------------------------------------------
        case ZodTypeName.ZodEnum: {
            const enumDef = def;
            return withDesc({ type: 'string', enum: enumDef.values });
        }
        case ZodTypeName.ZodNativeEnum: {
            const nativeEnumDef = def;
            const values = Object.values(nativeEnumDef.values).filter((v) => typeof v === 'string' || typeof v === 'number');
            return withDesc({ enum: values });
        }
        // -----------------------------------------------------------------------
        // Arrays
        // -----------------------------------------------------------------------
        case ZodTypeName.ZodArray: {
            const arrayDef = def;
            return withDesc({
                type: 'array',
                items: convertZodType(arrayDef.type),
            });
        }
        case ZodTypeName.ZodTuple: {
            const tupleDef = def;
            return withDesc({
                type: 'array',
                prefixItems: tupleDef.items.map(convertZodType),
            });
        }
        // -----------------------------------------------------------------------
        // Objects
        // -----------------------------------------------------------------------
        case ZodTypeName.ZodObject: {
            const objectDef = def;
            const properties = {};
            const required = [];
            for (const [key, value] of Object.entries(objectDef.shape())) {
                properties[key] = convertZodType(value);
                const innerDef = value._def;
                const isOptional = innerDef.typeName === ZodTypeName.ZodOptional ||
                    innerDef.typeName === ZodTypeName.ZodDefault ||
                    innerDef.typeName === ZodTypeName.ZodNullable;
                if (!isOptional) {
                    required.push(key);
                }
            }
            const result = { type: 'object', properties };
            if (required.length > 0)
                result.required = required;
            return withDesc(result);
        }
        case ZodTypeName.ZodRecord: {
            const recordDef = def;
            return withDesc({
                type: 'object',
                additionalProperties: convertZodType(recordDef.valueType),
            });
        }
        // -----------------------------------------------------------------------
        // Optional / Nullable / Default
        // -----------------------------------------------------------------------
        case ZodTypeName.ZodOptional: {
            const optionalDef = def;
            const inner = convertZodType(optionalDef.innerType);
            return description !== undefined ? { ...inner, description } : inner;
        }
        case ZodTypeName.ZodNullable: {
            const nullableDef = def;
            const inner = convertZodType(nullableDef.innerType);
            const type = inner.type;
            if (typeof type === 'string') {
                return withDesc({ ...inner, type: [type, 'null'] });
            }
            return withDesc({ anyOf: [inner, { type: 'null' }] });
        }
        case ZodTypeName.ZodDefault: {
            const defaultDef = def;
            const inner = convertZodType(defaultDef.innerType);
            return withDesc({ ...inner, default: defaultDef.defaultValue() });
        }
        // -----------------------------------------------------------------------
        // Union / Intersection / Discriminated Union
        // -----------------------------------------------------------------------
        case ZodTypeName.ZodUnion: {
            const unionDef = def;
            const options = unionDef.options.map(convertZodType);
            return withDesc({ anyOf: options });
        }
        case ZodTypeName.ZodDiscriminatedUnion: {
            const duDef = def;
            const options = duDef.options.map(convertZodType);
            return withDesc({ anyOf: options });
        }
        case ZodTypeName.ZodIntersection: {
            const intDef = def;
            return withDesc({
                allOf: [convertZodType(intDef.left), convertZodType(intDef.right)],
            });
        }
        // -----------------------------------------------------------------------
        // Wrappers that forward to their inner type
        // -----------------------------------------------------------------------
        case ZodTypeName.ZodEffects: {
            const effectsDef = def;
            const inner = convertZodType(effectsDef.schema);
            return description !== undefined ? { ...inner, description } : inner;
        }
        case ZodTypeName.ZodBranded: {
            const brandedDef = def;
            return withDesc(convertZodType(brandedDef.type));
        }
        case ZodTypeName.ZodReadonly: {
            const readonlyDef = def;
            return withDesc(convertZodType(readonlyDef.innerType));
        }
        case ZodTypeName.ZodCatch: {
            const catchDef = def;
            return withDesc(convertZodType(catchDef.innerType));
        }
        case ZodTypeName.ZodPipeline: {
            const pipelineDef = def;
            return withDesc(convertZodType(pipelineDef.in));
        }
        // -----------------------------------------------------------------------
        // Any / Unknown – JSON Schema wildcard
        // -----------------------------------------------------------------------
        case ZodTypeName.ZodAny:
        case ZodTypeName.ZodUnknown:
            return withDesc({});
        case ZodTypeName.ZodNever:
            return withDesc({ not: {} });
        case ZodTypeName.ZodVoid:
            return withDesc({ type: 'null' });
        // -----------------------------------------------------------------------
        // Fallback
        // -----------------------------------------------------------------------
        default:
            return withDesc({});
    }
}
// ---------------------------------------------------------------------------
// Internal Zod type-name enum (mirrors Zod's internal ZodFirstPartyTypeKind)
// ---------------------------------------------------------------------------
var ZodTypeName;
(function (ZodTypeName) {
    ZodTypeName["ZodString"] = "ZodString";
    ZodTypeName["ZodNumber"] = "ZodNumber";
    ZodTypeName["ZodBigInt"] = "ZodBigInt";
    ZodTypeName["ZodBoolean"] = "ZodBoolean";
    ZodTypeName["ZodDate"] = "ZodDate";
    ZodTypeName["ZodUndefined"] = "ZodUndefined";
    ZodTypeName["ZodNull"] = "ZodNull";
    ZodTypeName["ZodAny"] = "ZodAny";
    ZodTypeName["ZodUnknown"] = "ZodUnknown";
    ZodTypeName["ZodNever"] = "ZodNever";
    ZodTypeName["ZodVoid"] = "ZodVoid";
    ZodTypeName["ZodArray"] = "ZodArray";
    ZodTypeName["ZodObject"] = "ZodObject";
    ZodTypeName["ZodUnion"] = "ZodUnion";
    ZodTypeName["ZodDiscriminatedUnion"] = "ZodDiscriminatedUnion";
    ZodTypeName["ZodIntersection"] = "ZodIntersection";
    ZodTypeName["ZodTuple"] = "ZodTuple";
    ZodTypeName["ZodRecord"] = "ZodRecord";
    ZodTypeName["ZodMap"] = "ZodMap";
    ZodTypeName["ZodSet"] = "ZodSet";
    ZodTypeName["ZodFunction"] = "ZodFunction";
    ZodTypeName["ZodLazy"] = "ZodLazy";
    ZodTypeName["ZodLiteral"] = "ZodLiteral";
    ZodTypeName["ZodEnum"] = "ZodEnum";
    ZodTypeName["ZodEffects"] = "ZodEffects";
    ZodTypeName["ZodNativeEnum"] = "ZodNativeEnum";
    ZodTypeName["ZodOptional"] = "ZodOptional";
    ZodTypeName["ZodNullable"] = "ZodNullable";
    ZodTypeName["ZodDefault"] = "ZodDefault";
    ZodTypeName["ZodCatch"] = "ZodCatch";
    ZodTypeName["ZodPromise"] = "ZodPromise";
    ZodTypeName["ZodBranded"] = "ZodBranded";
    ZodTypeName["ZodPipeline"] = "ZodPipeline";
    ZodTypeName["ZodReadonly"] = "ZodReadonly";
})(ZodTypeName || (ZodTypeName = {}));
//# sourceMappingURL=framework.js.map