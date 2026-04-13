/**
 * @fileoverview Team — the central coordination object for a named group of agents.
 *
 * A {@link Team} owns the agent roster, the inter-agent {@link MessageBus},
 * the {@link TaskQueue}, and (optionally) a {@link SharedMemory} instance.
 * It also exposes a typed event bus so orchestrators can react to lifecycle
 * events without polling.
 */
import type { AgentConfig, MemoryStore, Task, TeamConfig } from '../types.js';
import { SharedMemory } from '../memory/shared.js';
import type { Message } from './messaging.js';
export type { Message };
/**
 * Coordinates a named group of agents with shared messaging, task queuing,
 * and optional shared memory.
 *
 * @example
 * ```ts
 * const team = new Team({
 *   name: 'research-team',
 *   agents: [researcherConfig, writerConfig],
 *   sharedMemory: true,
 *   maxConcurrency: 2,
 * })
 *
 * team.on('task:complete', (data) => {
 *   const event = data as OrchestratorEvent
 *   console.log(`Task done: ${event.task}`)
 * })
 *
 * const task = team.addTask({
 *   title: 'Research topic',
 *   description: 'Gather background on quantum computing',
 *   status: 'pending',
 *   assignee: 'researcher',
 * })
 * ```
 */
export declare class Team {
    readonly name: string;
    readonly config: TeamConfig;
    private readonly agentMap;
    private readonly bus;
    private readonly queue;
    private readonly memory;
    private readonly events;
    constructor(config: TeamConfig);
    /** Returns a shallow copy of the agent configs in registration order. */
    getAgents(): AgentConfig[];
    /**
     * Looks up an agent by name.
     *
     * @returns The {@link AgentConfig} or `undefined` when the name is not known.
     */
    getAgent(name: string): AgentConfig | undefined;
    /**
     * Sends a point-to-point message from `from` to `to`.
     *
     * The message is persisted on the bus and any active subscribers for `to`
     * are notified synchronously.
     */
    sendMessage(from: string, to: string, content: string): void;
    /**
     * Returns all messages (read or unread) addressed to `agentName`, in
     * chronological order.
     */
    getMessages(agentName: string): Message[];
    /**
     * Broadcasts `content` from `from` to every other agent.
     *
     * The `to` field of the resulting message is `'*'`.
     */
    broadcast(from: string, content: string): void;
    /**
     * Creates a new task, adds it to the queue, and returns the persisted
     * {@link Task} (with generated `id`, `createdAt`, and `updatedAt`).
     *
     * @param task - Everything except the generated fields.
     */
    addTask(task: Omit<Task, 'id' | 'createdAt' | 'updatedAt'>): Task;
    /** Returns a snapshot of all tasks in the queue (any status). */
    getTasks(): Task[];
    /** Returns all tasks whose `assignee` is `agentName`. */
    getTasksByAssignee(agentName: string): Task[];
    /**
     * Applies a partial update to the task identified by `taskId`.
     *
     * @throws {Error} when the task is not found.
     */
    updateTask(taskId: string, update: Partial<Task>): Task;
    /**
     * Returns the next `'pending'` task for `agentName`, respecting dependencies.
     *
     * Tries to find a task explicitly assigned to the agent first; falls back to
     * the first unassigned pending task.
     *
     * @returns `undefined` when no ready task exists for this agent.
     */
    getNextTask(agentName: string): Task | undefined;
    /**
     * Returns the shared {@link MemoryStore} for this team, or `undefined` if
     * `sharedMemory` was not enabled in {@link TeamConfig}.
     *
     * Note: the returned value satisfies the {@link MemoryStore} interface.
     * Callers that need the full {@link SharedMemory} API can use the
     * `as SharedMemory` cast, but depending on the concrete type is discouraged.
     */
    getSharedMemory(): MemoryStore | undefined;
    /**
     * Returns the raw {@link SharedMemory} instance (team-internal accessor).
     * Use this when you need the namespacing / `getSummary` features.
     *
     * @internal
     */
    getSharedMemoryInstance(): SharedMemory | undefined;
    /**
     * Subscribes to a team event.
     *
     * Built-in events:
     * - `'task:ready'`   — emitted when a task becomes runnable.
     * - `'task:complete'` — emitted when a task completes successfully.
     * - `'task:failed'`  — emitted when a task fails.
     * - `'all:complete'` — emitted when every task in the queue has terminated.
     * - `'message'`      — emitted on point-to-point messages.
     * - `'broadcast'`    — emitted on broadcast messages.
     *
     * `data` is typed as `unknown`; cast to {@link OrchestratorEvent} for
     * structured access.
     *
     * @returns An unsubscribe function.
     */
    on(event: string, handler: (data: unknown) => void): () => void;
    /**
     * Emits a custom event on the team's event bus.
     *
     * Orchestrators can use this to signal domain-specific lifecycle milestones
     * (e.g. `'phase:research:complete'`) without modifying the Team class.
     */
    emit(event: string, data: unknown): void;
}
//# sourceMappingURL=team.d.ts.map