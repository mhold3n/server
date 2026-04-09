/**
 * @fileoverview Trace emission utilities for the observability layer.
 */
import type { TraceEvent } from '../types.js';
/**
 * Safely emit a trace event. Swallows callback errors so a broken
 * subscriber never crashes agent execution.
 */
export declare function emitTrace(fn: ((event: TraceEvent) => void | Promise<void>) | undefined, event: TraceEvent): void;
/** Generate a unique run ID for trace correlation. */
export declare function generateRunId(): string;
//# sourceMappingURL=trace.d.ts.map