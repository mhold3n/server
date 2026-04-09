/**
 * @fileoverview Framework-specific error classes.
 */
/**
 * Raised when an agent or orchestrator run exceeds its configured token budget.
 */
export declare class TokenBudgetExceededError extends Error {
    readonly agent: string;
    readonly tokensUsed: number;
    readonly budget: number;
    readonly code = "TOKEN_BUDGET_EXCEEDED";
    constructor(agent: string, tokensUsed: number, budget: number);
}
//# sourceMappingURL=errors.d.ts.map