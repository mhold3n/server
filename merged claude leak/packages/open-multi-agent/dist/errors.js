/**
 * @fileoverview Framework-specific error classes.
 */
/**
 * Raised when an agent or orchestrator run exceeds its configured token budget.
 */
export class TokenBudgetExceededError extends Error {
    agent;
    tokensUsed;
    budget;
    code = 'TOKEN_BUDGET_EXCEEDED';
    constructor(agent, tokensUsed, budget) {
        super(`Agent "${agent}" exceeded token budget: ${tokensUsed} tokens used (budget: ${budget})`);
        this.agent = agent;
        this.tokensUsed = tokensUsed;
        this.budget = budget;
        this.name = 'TokenBudgetExceededError';
    }
}
//# sourceMappingURL=errors.js.map