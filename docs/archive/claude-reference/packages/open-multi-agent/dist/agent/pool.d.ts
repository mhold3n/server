/**
 * @fileoverview Agent pool for managing and scheduling multiple agents.
 *
 * {@link AgentPool} is a registry + scheduler that:
 *  - Holds any number of named {@link Agent} instances
 *  - Enforces a concurrency cap across parallel runs via {@link Semaphore}
 *  - Provides `runParallel` for fan-out and `runAny` for round-robin dispatch
 *  - Reports aggregate pool health via `getStatus()`
 *
 * @example
 * ```ts
 * const pool = new AgentPool(3)
 * pool.add(researchAgent)
 * pool.add(writerAgent)
 *
 * const results = await pool.runParallel([
 *   { agent: 'researcher', prompt: 'Find recent AI papers.' },
 *   { agent: 'writer',     prompt: 'Draft an intro section.' },
 * ])
 * ```
 */
import type { AgentRunResult } from '../types.js';
import type { RunOptions } from './runner.js';
import type { Agent } from './agent.js';
export { Semaphore } from '../utils/semaphore.js';
export interface PoolStatus {
    /** Total number of agents registered in the pool. */
    readonly total: number;
    /** Agents currently in `idle` state. */
    readonly idle: number;
    /** Agents currently in `running` state. */
    readonly running: number;
    /** Agents currently in `completed` state. */
    readonly completed: number;
    /** Agents currently in `error` state. */
    readonly error: number;
}
/**
 * Registry and scheduler for a collection of {@link Agent} instances.
 *
 * Thread-safety note: Node.js is single-threaded, so the semaphore approach
 * is safe — no atomics or mutex primitives are needed. The semaphore gates
 * concurrent async operations, not CPU threads.
 */
export declare class AgentPool {
    private readonly maxConcurrency;
    private readonly agents;
    private readonly semaphore;
    /**
     * Per-agent mutex (Semaphore(1)) to serialize concurrent runs on the same
     * Agent instance.  Without this, two tasks assigned to the same agent could
     * race on mutable instance state (`status`, `messages`, `tokenUsage`).
     *
     * @see https://github.com/anthropics/open-multi-agent/issues/72
     */
    private readonly agentLocks;
    /** Cursor used by `runAny` for round-robin dispatch. */
    private roundRobinIndex;
    /**
     * @param maxConcurrency - Maximum number of agent runs allowed at the same
     *                         time across the whole pool. Defaults to `5`.
     */
    constructor(maxConcurrency?: number);
    /**
     * Register an agent with the pool.
     *
     * @throws {Error} If an agent with the same name is already registered.
     */
    add(agent: Agent): void;
    /**
     * Unregister an agent by name.
     *
     * @throws {Error} If the agent is not found.
     */
    remove(name: string): void;
    /**
     * Retrieve a registered agent by name, or `undefined` if not found.
     */
    get(name: string): Agent | undefined;
    /**
     * Return all registered agents in insertion order.
     */
    list(): Agent[];
    /**
     * Run a single prompt on the named agent, respecting the pool concurrency
     * limit.
     *
     * @throws {Error} If the agent name is not found.
     */
    run(agentName: string, prompt: string, runOptions?: Partial<RunOptions>): Promise<AgentRunResult>;
    /**
     * Run prompts on multiple agents in parallel, subject to the concurrency
     * cap set at construction time.
     *
     * Results are returned as a `Map<agentName, AgentRunResult>`. If two tasks
     * target the same agent name, the map will only contain the last result.
     * Use unique agent names or run tasks sequentially in that case.
     *
     * @param tasks - Array of `{ agent, prompt }` descriptors.
     */
    runParallel(tasks: ReadonlyArray<{
        readonly agent: string;
        readonly prompt: string;
    }>): Promise<Map<string, AgentRunResult>>;
    /**
     * Run a prompt on the "best available" agent using round-robin selection.
     *
     * Agents are selected in insertion order, cycling back to the start. The
     * concurrency limit is still enforced — if the selected agent is busy the
     * call will queue via the semaphore.
     *
     * @throws {Error} If the pool is empty.
     */
    runAny(prompt: string): Promise<AgentRunResult>;
    /**
     * Snapshot of how many agents are in each lifecycle state.
     */
    getStatus(): PoolStatus;
    /**
     * Reset all agents in the pool.
     *
     * Clears their conversation histories and returns them to `idle` state.
     * Does not remove agents from the pool.
     *
     * Async for forward compatibility — shutdown may need to perform async
     * cleanup (e.g. draining in-flight requests) in future versions.
     */
    shutdown(): Promise<void>;
    private requireAgent;
    /**
     * Build a failure {@link AgentRunResult} from a caught rejection reason.
     * This keeps `runParallel` returning a complete map even when individual
     * agents fail.
     */
    private errorResult;
}
//# sourceMappingURL=pool.d.ts.map