/**
 * @fileoverview OpenMultiAgent — the top-level multi-agent orchestration class.
 *
 * {@link OpenMultiAgent} is the primary public API of the open-multi-agent framework.
 * It ties together every subsystem:
 *
 *  - {@link Team}       — Agent roster, shared memory, inter-agent messaging
 *  - {@link TaskQueue}  — Dependency-aware work queue
 *  - {@link Scheduler}  — Task-to-agent assignment strategies
 *  - {@link AgentPool}  — Concurrency-controlled execution pool
 *  - {@link Agent}      — Conversation + tool-execution loop
 *
 * ## Quick start
 *
 * ```ts
 * const orchestrator = new OpenMultiAgent({ defaultModel: 'claude-opus-4-6' })
 *
 * const team = orchestrator.createTeam('research', {
 *   name: 'research',
 *   agents: [
 *     { name: 'researcher', model: 'claude-opus-4-6', systemPrompt: 'You are a researcher.' },
 *     { name: 'writer',     model: 'claude-opus-4-6', systemPrompt: 'You are a technical writer.' },
 *   ],
 *   sharedMemory: true,
 * })
 *
 * const result = await orchestrator.runTeam(team, 'Produce a report on TypeScript 5.5.')
 * console.log(result.agentResults.get('coordinator')?.output)
 * ```
 *
 * ## Key design decisions
 *
 * - **Coordinator pattern** — `runTeam()` spins up a temporary "coordinator" agent
 *   that breaks the high-level goal into tasks, assigns them, and synthesises the
 *   final answer. This is the framework's killer feature.
 * - **Parallel-by-default** — Independent tasks (no shared dependency) run in
 *   parallel up to `maxConcurrency`.
 * - **Graceful failure** — A failed task marks itself `'failed'` and its direct
 *   dependents remain `'blocked'` indefinitely; all non-dependent tasks continue.
 * - **Progress callbacks** — Callers can pass `onProgress` in the config to receive
 *   structured {@link OrchestratorEvent}s without polling.
 */
import type { AgentConfig, AgentRunResult, CoordinatorConfig, OrchestratorConfig, Task, TeamConfig, TeamRunResult } from '../types.js';
import { Team } from '../team/team.js';
/**
 * Determine whether a goal is simple enough to skip coordinator decomposition.
 *
 * A goal is considered "simple" when ALL of the following hold:
 *   1. Its length is ≤ {@link SIMPLE_GOAL_MAX_LENGTH}.
 *   2. It does not match any {@link COMPLEXITY_PATTERNS}.
 *
 * The complexity patterns are deliberately conservative — they only fire on
 * imperative coordination directives (e.g. "collaborate with the team",
 * "coordinate the workers"), so descriptive uses ("how do pods coordinate
 * state", "explain microservice collaboration") remain classified as simple.
 *
 * Exported for unit testing.
 */
export declare function isSimpleGoal(goal: string): boolean;
/**
 * Select the best-matching agent for a goal using keyword affinity scoring.
 *
 * The scoring logic mirrors {@link Scheduler}'s `capability-match` strategy
 * exactly, including its asymmetric use of the agent's `model` field:
 *
 *  - `agentKeywords` is computed from `name + systemPrompt + model` so that
 *    a goal which mentions a model name (e.g. "haiku") can boost an agent
 *    bound to that model.
 *  - `agentText` (used for the reverse direction) is computed from
 *    `name + systemPrompt` only — model names should not bias the
 *    text-vs-goal-keywords match.
 *
 * The two-direction sum (`scoreA + scoreB`) ensures both "agent describes
 * goal" and "goal mentions agent capability" contribute to the final score.
 *
 * Exported for unit testing.
 */
export declare function selectBestAgent(goal: string, agents: AgentConfig[]): AgentConfig;
/**
 * Compute the retry delay for a given attempt, capped at {@link MAX_RETRY_DELAY_MS}.
 */
export declare function computeRetryDelay(baseDelay: number, backoff: number, attempt: number): number;
/**
 * Execute an agent task with optional retry and exponential backoff.
 *
 * Exported for testability — called internally by {@link executeQueue}.
 *
 * @param run      - The function that executes the task (typically `pool.run`).
 * @param task     - The task to execute (retry config read from its fields).
 * @param onRetry  - Called before each retry sleep with event data.
 * @param delayFn  - Injectable delay function (defaults to real `sleep`).
 * @returns The final {@link AgentRunResult} from the last attempt.
 */
export declare function executeWithRetry(run: () => Promise<AgentRunResult>, task: Task, onRetry?: (data: {
    attempt: number;
    maxAttempts: number;
    error: string;
    nextDelayMs: number;
}) => void, delayFn?: (ms: number) => Promise<void>): Promise<AgentRunResult>;
/**
 * Top-level orchestrator for the open-multi-agent framework.
 *
 * Manages teams, coordinates task execution, and surfaces progress events.
 * Most users will interact with this class exclusively.
 */
export declare class OpenMultiAgent {
    private readonly config;
    private readonly teams;
    private completedTaskCount;
    /**
     * @param config - Optional top-level configuration.
     *
     * Sensible defaults:
     *   - `maxConcurrency`: 5
     *   - `defaultModel`:   `'claude-opus-4-6'`
     *   - `defaultProvider`: `'anthropic'`
     */
    constructor(config?: OrchestratorConfig);
    private agentOptions;
    /**
     * Create and register a {@link Team} with the orchestrator.
     *
     * The team is stored internally so {@link getStatus} can report aggregate
     * agent counts. Returns the new {@link Team} for further configuration.
     *
     * @param name   - Unique team identifier. Throws if already registered.
     * @param config - Team configuration (agents, shared memory, concurrency).
     */
    createTeam(name: string, config: TeamConfig): Team;
    /**
     * Run a single prompt with a one-off agent.
     *
     * Constructs a fresh agent from `config`, runs `prompt` in a single turn,
     * and returns the result. The agent is not registered with any pool or team.
     *
     * Useful for simple one-shot queries that do not need team orchestration.
     *
     * @param config - Agent configuration.
     * @param prompt - The user prompt to send.
     */
    runAgent(config: AgentConfig, prompt: string, options?: {
        abortSignal?: AbortSignal;
    }): Promise<AgentRunResult>;
    /**
     * Run a team on a high-level goal with full automatic orchestration.
     *
     * This is the flagship method of the framework. It works as follows:
     *
     * 1. A temporary "coordinator" agent receives the goal and the team's agent
     *    roster, and is asked to decompose it into an ordered list of tasks with
     *    JSON output.
     * 2. The tasks are loaded into a {@link TaskQueue}. Title-based dependency
     *    tokens in the coordinator's output are resolved to task IDs.
     * 3. The {@link Scheduler} assigns unassigned tasks to team agents.
     * 4. Tasks are executed in dependency order, with independent tasks running
     *    in parallel up to `maxConcurrency`.
     * 5. Results are persisted to shared memory after each task so subsequent
     *    agents can read them.
     * 6. The coordinator synthesises a final answer from all task outputs.
     * 7. A {@link TeamRunResult} is returned.
     *
     * @param team - A team created via {@link createTeam} (or `new Team(...)`).
     * @param goal - High-level natural-language goal for the team.
     */
    runTeam(team: Team, goal: string, options?: {
        abortSignal?: AbortSignal;
        coordinator?: CoordinatorConfig;
    }): Promise<TeamRunResult>;
    /**
     * Run a team with an explicitly provided task list.
     *
     * Simpler than {@link runTeam}: no coordinator agent is involved. Tasks are
     * loaded directly into the queue, unassigned tasks are auto-assigned via the
     * {@link Scheduler}, and execution proceeds in dependency order.
     *
     * @param team  - A team created via {@link createTeam}.
     * @param tasks - Array of task descriptors.
     */
    runTasks(team: Team, tasks: ReadonlyArray<{
        title: string;
        description: string;
        assignee?: string;
        dependsOn?: string[];
        maxRetries?: number;
        retryDelayMs?: number;
        retryBackoff?: number;
    }>, options?: {
        abortSignal?: AbortSignal;
    }): Promise<TeamRunResult>;
    /**
     * Returns a lightweight status snapshot.
     *
     * - `teams`          — Number of teams registered with this orchestrator.
     * - `activeAgents`   — Total agents currently in `running` state.
     * - `completedTasks` — Cumulative count of successfully completed tasks
     *                      (coordinator meta-steps excluded).
     */
    getStatus(): {
        teams: number;
        activeAgents: number;
        completedTasks: number;
    };
    /**
     * Deregister all teams and reset internal counters.
     *
     * Does not cancel in-flight runs. Call this when you want to reuse the
     * orchestrator instance for a fresh set of teams.
     *
     * Async for forward compatibility — shutdown may need to perform async
     * cleanup (e.g. graceful agent drain) in future versions.
     */
    shutdown(): Promise<void>;
    /** Build the system prompt given to the coordinator agent. */
    private buildCoordinatorSystemPrompt;
    /** Build coordinator system prompt with optional caller overrides. */
    private buildCoordinatorPrompt;
    /** Build the coordinator team roster section. */
    private buildCoordinatorRosterSection;
    /** Build the coordinator JSON output-format section. */
    private buildCoordinatorOutputFormatSection;
    /** Build the coordinator synthesis guidance section. */
    private buildCoordinatorSynthesisSection;
    /** Build the decomposition prompt for the coordinator. */
    private buildDecompositionPrompt;
    /** Build the synthesis prompt shown to the coordinator after all tasks complete. */
    private buildSynthesisPrompt;
    /**
     * Load a list of task specs into a queue.
     *
     * Handles title-based `dependsOn` references by building a title→id map first,
     * then resolving them to real IDs before adding tasks to the queue.
     */
    private loadSpecsIntoQueue;
    /** Build an {@link AgentPool} from a list of agent configurations. */
    private buildPool;
    /**
     * Aggregate the per-run `agentResults` map into a {@link TeamRunResult}.
     *
     * Merges results keyed as `agentName:taskId` back into a per-agent map
     * by agent name for the public result surface.
     *
     * Only non-coordinator entries are counted toward `completedTaskCount` to
     * avoid double-counting the coordinator's internal decompose/synthesis steps.
     */
    private buildTeamRunResult;
}
//# sourceMappingURL=orchestrator.d.ts.map