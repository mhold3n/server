/**
 * @fileoverview Task scheduling strategies for the open-multi-agent orchestrator.
 *
 * The {@link Scheduler} class encapsulates four distinct strategies for
 * mapping a set of pending {@link Task}s onto a pool of available agents:
 *
 * - `round-robin`        — Distribute tasks evenly across agents by index.
 * - `least-busy`         — Assign to whichever agent has the fewest active tasks.
 * - `capability-match`   — Score agents by keyword overlap with the task description.
 * - `dependency-first`   — Prioritise tasks on the critical path (most blocked dependents).
 *
 * The scheduler is stateless between calls. All mutable task state lives in the
 * {@link TaskQueue} that is passed to {@link Scheduler.autoAssign}.
 */
import type { AgentConfig, Task } from '../types.js';
import type { TaskQueue } from '../task/queue.js';
/**
 * The four scheduling strategies available to the {@link Scheduler}.
 *
 * - `round-robin`       — Equal distribution by agent index.
 * - `least-busy`        — Prefers the agent with the fewest `in_progress` tasks.
 * - `capability-match`  — Keyword-based affinity between task text and agent role.
 * - `dependency-first`  — Prioritise tasks that unblock the most other tasks.
 */
export type SchedulingStrategy = 'round-robin' | 'least-busy' | 'capability-match' | 'dependency-first';
/**
 * Maps pending tasks to available agents using one of four configurable strategies.
 *
 * @example
 * ```ts
 * const scheduler = new Scheduler('capability-match')
 *
 * // Get a full assignment map from tasks to agent names
 * const assignments = scheduler.schedule(pendingTasks, teamAgents)
 *
 * // Or let the scheduler directly update a TaskQueue
 * scheduler.autoAssign(queue, teamAgents)
 * ```
 */
export declare class Scheduler {
    private readonly strategy;
    /** Rolling cursor used by `round-robin` to distribute tasks sequentially. */
    private roundRobinCursor;
    /**
     * @param strategy - The scheduling algorithm to apply. Defaults to
     *                   `'dependency-first'` which is the safest default for
     *                   complex multi-step pipelines.
     */
    constructor(strategy?: SchedulingStrategy);
    /**
     * Given a list of pending `tasks` and `agents`, return a mapping from
     * `taskId` to `agentName` representing the recommended assignment.
     *
     * Only tasks without an existing `assignee` are considered. Tasks that are
     * already assigned are preserved unchanged.
     *
     * The method is deterministic for all strategies except `round-robin`, which
     * advances an internal cursor and therefore produces different results across
     * successive calls with the same inputs.
     *
     * @param tasks  - Snapshot of all tasks in the current run (any status).
     * @param agents - Available agent configurations.
     * @returns A `Map<taskId, agentName>` for every unassigned pending task.
     */
    schedule(tasks: Task[], agents: AgentConfig[]): Map<string, string>;
    /**
     * Convenience method that applies assignments returned by {@link schedule}
     * directly to a live `TaskQueue`.
     *
     * Iterates all pending, unassigned tasks in the queue and sets `assignee` for
     * each according to the current strategy. Skips tasks that are already
     * assigned, non-pending, or whose IDs are not found in the queue snapshot.
     *
     * @param queue  - The live task queue to mutate.
     * @param agents - Available agent configurations.
     */
    autoAssign(queue: TaskQueue, agents: AgentConfig[]): void;
    /**
     * Round-robin: assign tasks to agents in order, cycling back to the start.
     *
     * The cursor advances with every call so that repeated calls with the same
     * task set continue distributing work — rather than always starting from
     * agent[0].
     */
    private scheduleRoundRobin;
    /**
     * Least-busy: assign each task to the agent with the fewest `in_progress`
     * tasks at the time the schedule is computed.
     *
     * Agent load is derived from the `in_progress` count in `allTasks`. Ties are
     * broken by the agent's position in the `agents` array (earlier = preferred).
     */
    private scheduleLeastBusy;
    /**
     * Capability-match: score each agent against each task by keyword overlap
     * between the task's title/description and the agent's `systemPrompt` and
     * `name`. The highest-scoring agent wins.
     *
     * Falls back to round-robin when no agent has any positive score.
     */
    private scheduleCapabilityMatch;
    /**
     * Dependency-first: prioritise tasks by how many other tasks are blocked
     * waiting for them (the "critical path" heuristic).
     *
     * Tasks with more downstream dependents are assigned to agents first. Within
     * the same criticality tier the agents are selected round-robin so no single
     * agent is overloaded.
     */
    private scheduleDependencyFirst;
}
//# sourceMappingURL=scheduler.d.ts.map