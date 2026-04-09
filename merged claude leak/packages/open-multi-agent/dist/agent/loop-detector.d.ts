/**
 * @fileoverview Sliding-window loop detector for the agent conversation loop.
 *
 * Tracks tool-call signatures and text outputs across turns to detect when an
 * agent is stuck repeating the same actions. Used by {@link AgentRunner} when
 * {@link LoopDetectionConfig} is provided.
 */
import type { LoopDetectionConfig, LoopDetectionInfo } from '../types.js';
export declare class LoopDetector {
    private readonly maxRepeats;
    private readonly windowSize;
    private readonly toolSignatures;
    private readonly textOutputs;
    constructor(config?: LoopDetectionConfig);
    /**
     * Record a turn's tool calls. Returns detection info when a loop is found.
     */
    recordToolCalls(blocks: ReadonlyArray<{
        name: string;
        input: Record<string, unknown>;
    }>): LoopDetectionInfo | null;
    /**
     * Record a turn's text output. Returns detection info when a loop is found.
     */
    recordText(text: string): LoopDetectionInfo | null;
    /**
     * Deterministic JSON signature for a set of tool calls.
     * Sorts calls by name (for multi-tool turns) and keys within each input.
     */
    private computeToolSignature;
    /** Push an entry and trim the buffer to `windowSize`. */
    private push;
    /**
     * Count how many consecutive identical entries exist at the tail of `buffer`.
     * Returns 1 when the last entry is unique.
     */
    private consecutiveRepeats;
}
//# sourceMappingURL=loop-detector.d.ts.map