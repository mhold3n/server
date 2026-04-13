/**
 * @fileoverview Team — the central coordination object for a named group of agents.
 *
 * A {@link Team} owns the agent roster, the inter-agent {@link MessageBus},
 * the {@link TaskQueue}, and (optionally) a {@link SharedMemory} instance.
 * It also exposes a typed event bus so orchestrators can react to lifecycle
 * events without polling.
 */
import { SharedMemory } from '../memory/shared.js';
import { MessageBus } from './messaging.js';
import { TaskQueue } from '../task/queue.js';
import { createTask } from '../task/task.js';
/** Minimal synchronous event emitter. */
class EventBus {
    listeners = new Map();
    on(event, handler) {
        let map = this.listeners.get(event);
        if (!map) {
            map = new Map();
            this.listeners.set(event, map);
        }
        const id = Symbol();
        map.set(id, handler);
        return () => {
            map.delete(id);
        };
    }
    emit(event, data) {
        const map = this.listeners.get(event);
        if (!map)
            return;
        for (const handler of map.values()) {
            handler(data);
        }
    }
}
// ---------------------------------------------------------------------------
// Team
// ---------------------------------------------------------------------------
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
export class Team {
    name;
    config;
    agentMap;
    bus;
    queue;
    memory;
    events;
    constructor(config) {
        this.config = config;
        this.name = config.name;
        // Index agents by name for O(1) lookup.
        this.agentMap = new Map(config.agents.map((a) => [a.name, a]));
        this.bus = new MessageBus();
        this.queue = new TaskQueue();
        this.memory = config.sharedMemory ? new SharedMemory() : undefined;
        this.events = new EventBus();
        // Bridge queue events onto the team's event bus.
        this.queue.on('task:ready', (task) => {
            const event = {
                type: 'task_start',
                task: task.id,
                data: task,
            };
            this.events.emit('task:ready', event);
        });
        this.queue.on('task:complete', (task) => {
            const event = {
                type: 'task_complete',
                task: task.id,
                data: task,
            };
            this.events.emit('task:complete', event);
        });
        this.queue.on('task:failed', (task) => {
            const event = {
                type: 'error',
                task: task.id,
                data: task,
            };
            this.events.emit('task:failed', event);
        });
        this.queue.on('all:complete', () => {
            this.events.emit('all:complete', undefined);
        });
    }
    // ---------------------------------------------------------------------------
    // Agent roster
    // ---------------------------------------------------------------------------
    /** Returns a shallow copy of the agent configs in registration order. */
    getAgents() {
        return Array.from(this.agentMap.values());
    }
    /**
     * Looks up an agent by name.
     *
     * @returns The {@link AgentConfig} or `undefined` when the name is not known.
     */
    getAgent(name) {
        return this.agentMap.get(name);
    }
    // ---------------------------------------------------------------------------
    // Messaging
    // ---------------------------------------------------------------------------
    /**
     * Sends a point-to-point message from `from` to `to`.
     *
     * The message is persisted on the bus and any active subscribers for `to`
     * are notified synchronously.
     */
    sendMessage(from, to, content) {
        const message = this.bus.send(from, to, content);
        const event = {
            type: 'message',
            agent: from,
            data: message,
        };
        this.events.emit('message', event);
    }
    /**
     * Returns all messages (read or unread) addressed to `agentName`, in
     * chronological order.
     */
    getMessages(agentName) {
        return this.bus.getAll(agentName);
    }
    /**
     * Broadcasts `content` from `from` to every other agent.
     *
     * The `to` field of the resulting message is `'*'`.
     */
    broadcast(from, content) {
        const message = this.bus.broadcast(from, content);
        const event = {
            type: 'message',
            agent: from,
            data: message,
        };
        this.events.emit('broadcast', event);
    }
    // ---------------------------------------------------------------------------
    // Task management
    // ---------------------------------------------------------------------------
    /**
     * Creates a new task, adds it to the queue, and returns the persisted
     * {@link Task} (with generated `id`, `createdAt`, and `updatedAt`).
     *
     * @param task - Everything except the generated fields.
     */
    addTask(task) {
        const created = createTask({
            title: task.title,
            description: task.description,
            assignee: task.assignee,
            dependsOn: task.dependsOn ? [...task.dependsOn] : undefined,
        });
        // Preserve any non-default status (e.g. 'blocked') supplied by the caller.
        const finalTask = task.status !== 'pending'
            ? { ...created, status: task.status, result: task.result }
            : created;
        this.queue.add(finalTask);
        return finalTask;
    }
    /** Returns a snapshot of all tasks in the queue (any status). */
    getTasks() {
        return this.queue.list();
    }
    /** Returns all tasks whose `assignee` is `agentName`. */
    getTasksByAssignee(agentName) {
        return this.queue.list().filter((t) => t.assignee === agentName);
    }
    /**
     * Applies a partial update to the task identified by `taskId`.
     *
     * @throws {Error} when the task is not found.
     */
    updateTask(taskId, update) {
        // Extract only mutable fields accepted by the queue.
        const { status, result, assignee } = update;
        return this.queue.update(taskId, {
            ...(status !== undefined && { status }),
            ...(result !== undefined && { result }),
            ...(assignee !== undefined && { assignee }),
        });
    }
    /**
     * Returns the next `'pending'` task for `agentName`, respecting dependencies.
     *
     * Tries to find a task explicitly assigned to the agent first; falls back to
     * the first unassigned pending task.
     *
     * @returns `undefined` when no ready task exists for this agent.
     */
    getNextTask(agentName) {
        // Prefer a task explicitly assigned to this agent.
        const assigned = this.queue.next(agentName);
        if (assigned)
            return assigned;
        // Fall back to any unassigned pending task.
        return this.queue.nextAvailable();
    }
    // ---------------------------------------------------------------------------
    // Memory
    // ---------------------------------------------------------------------------
    /**
     * Returns the shared {@link MemoryStore} for this team, or `undefined` if
     * `sharedMemory` was not enabled in {@link TeamConfig}.
     *
     * Note: the returned value satisfies the {@link MemoryStore} interface.
     * Callers that need the full {@link SharedMemory} API can use the
     * `as SharedMemory` cast, but depending on the concrete type is discouraged.
     */
    getSharedMemory() {
        return this.memory?.getStore();
    }
    /**
     * Returns the raw {@link SharedMemory} instance (team-internal accessor).
     * Use this when you need the namespacing / `getSummary` features.
     *
     * @internal
     */
    getSharedMemoryInstance() {
        return this.memory;
    }
    // ---------------------------------------------------------------------------
    // Events
    // ---------------------------------------------------------------------------
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
    on(event, handler) {
        return this.events.on(event, handler);
    }
    /**
     * Emits a custom event on the team's event bus.
     *
     * Orchestrators can use this to signal domain-specific lifecycle milestones
     * (e.g. `'phase:research:complete'`) without modifying the Team class.
     */
    emit(event, data) {
        this.events.emit(event, data);
    }
}
//# sourceMappingURL=team.js.map