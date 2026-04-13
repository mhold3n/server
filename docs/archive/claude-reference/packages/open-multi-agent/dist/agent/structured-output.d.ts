/**
 * @fileoverview Structured output utilities for agent responses.
 *
 * Provides JSON extraction, Zod validation, and system-prompt injection so
 * that agents can return typed, schema-validated output.
 */
import { type ZodSchema } from 'zod';
/**
 * Build a JSON-mode instruction block to append to the agent's system prompt.
 *
 * Converts the Zod schema to JSON Schema and formats it as a clear directive
 * for the LLM to respond with valid JSON matching the schema.
 */
export declare function buildStructuredOutputInstruction(schema: ZodSchema): string;
/**
 * Attempt to extract and parse JSON from the agent's raw text output.
 *
 * Handles three cases in order:
 * 1. The output is already valid JSON (ideal case)
 * 2. The output contains a ` ```json ` fenced block
 * 3. The output contains a bare JSON object/array (first `{`/`[` to last `}`/`]`)
 *
 * @throws {Error} when no valid JSON can be extracted
 */
export declare function extractJSON(raw: string): unknown;
/**
 * Validate a parsed JSON value against a Zod schema.
 *
 * @returns The validated (and potentially transformed) value on success.
 * @throws {Error} with a human-readable Zod error message on failure.
 */
export declare function validateOutput(schema: ZodSchema, data: unknown): unknown;
//# sourceMappingURL=structured-output.d.ts.map