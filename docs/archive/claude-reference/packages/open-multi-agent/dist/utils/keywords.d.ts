/**
 * Shared keyword-affinity helpers used by capability-match scheduling
 * and short-circuit agent selection. Kept in one place so behaviour
 * can't drift between Scheduler and Orchestrator.
 */
export declare const STOP_WORDS: ReadonlySet<string>;
/**
 * Tokenise `text` into a deduplicated set of lower-cased keywords.
 * Words shorter than 4 characters and entries in {@link STOP_WORDS}
 * are filtered out.
 */
export declare function extractKeywords(text: string): string[];
/**
 * Count how many `keywords` appear (case-insensitively) in `text`.
 * Each keyword contributes at most 1 to the score.
 */
export declare function keywordScore(text: string, keywords: readonly string[]): number;
//# sourceMappingURL=keywords.d.ts.map