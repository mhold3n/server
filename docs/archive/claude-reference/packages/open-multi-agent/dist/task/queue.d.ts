/**
 * @fileoverview Dependency-aware task queue.
 *
 * {@link TaskQueue} owns the mutable lifecycle of every task it holds.
 * Completing a task automatically unblocks dependents and fires events so
 * orchestrators can react without polling.
 */
import type { Task, TaskStatus } from '../types.js';
/** Named event types emitted by {@link TaskQueue}. */
export type TaskQueueEvent = 'task:ready' | 'task:complete' | 'task:failed' | 'task:skipped' | 'all:complete';
/** Handler for `'task:ready' | 'task:complete' | 'task:failed'` events. */
type TaskHandler = (task: Task) => void;
/** Handler for `'all:complete'` (no task argument). */
type AllCompleteHandler = () => void;
type HandlerFor<E extends TaskQueueEvent> = E extends 'all:complete' ? AllCompleteHandler : TaskHandler;
/**
 * Mutable, event-driven queue with topological dependency resolution.
 *
 * Tasks enter in `'pending'` state. The queue promotes them to `'blocked'`
 * when unresolved dependencies exist, and back to `'pending'` (firing
 * `'task:ready'`) when those dependencies complete. Callers drive execution by
 * calling {@link next} / {@link nextAvailable} and updating task state via
 * {@link complete} or {@link fail}.
 *
 * @example
 * ```ts
 * const queue = new TaskQueue()
 * queue.on('task:ready', (task) => scheduleExecution(task))
 * queue.on('all:complete', () => shutdown())
 *
 * queue.addBatch(tasks)
 * ```
 */
export declare class TaskQueue {
    private readonly tasks;
    /** Listeners keyed by event type, stored as symbol → handler pairs. */
    private readonly listeners;
    /**
     * Adds a single task.
     *
     * If the task has unresolved dependencies it is immediately promoted to
     * `'blocked'`; otherwise it stays `'pending'` and `'task:ready'` fires.
     */
    add(task: Task): void;
    /**
     * Adds multiple tasks at once.
     *
     * Processing each task re-evaluates the current map state, so inserting a
     * batch where some tasks satisfy others' dependencies produces correct initial
     * statuses when the dependencies appear first in the array. Use
     * {@link getTaskDependencyOrder} from `task.ts` to pre-sort if needed.
     */
    addBatch(tasks: Task[]): void;
    /**
     * Applies a partial update to an existing task.
     *
     * Only `status`, `result`, and `assignee` are accepted to keep the update
     * surface narrow. Use {@link complete} and {@link fail} for terminal states.
     *
     * @throws {Error} when `taskId` is not found.
     */
    update(taskId: string, update: Partial<Pick<Task, 'status' | 'result' | 'assignee'>>): Task;
    /**
     * Marks `taskId` as `'completed'`, records an optional `result` string, and
     * unblocks any dependents that are now ready to run.
     *
     * Fires `'task:complete'`, then `'task:ready'` for each newly-unblocked task,
     * then `'all:complete'` when the queue is fully resolved.
     *
     * @throws {Error} when `taskId` is not found.
     */
    complete(taskId: string, result?: string): Task;
    /**
     * Marks `taskId` as `'failed'` and records `error` in the `result` field.
     *
     * Fires `'task:failed'` for the failed task and for every downstream task
     * that transitively depended on it (cascade failure). This prevents blocked
     * tasks from remaining stuck indefinitely when an upstream dependency fails.
     *
     * @throws {Error} when `taskId` is not found.
     */
    fail(taskId: string, error: string): Task;
    /**
     * Marks `taskId` as `'skipped'` and records `reason` in the `result` field.
     *
     * Fires `'task:skipped'` for the skipped task and cascades to every
     * downstream task that transitively depended on it — even if the dependent
     * has other dependencies that are still pending or completed. A skipped
     * upstream is treated as permanently unsatisfiable, mirroring `fail()`.
     *
     * @throws {Error} when `taskId` is not found.
     */
    skip(taskId: string, reason: string): Task;
    /**
     * Marks all non-terminal tasks as `'skipped'`.
     *
     * Used when an approval gate rejects continuation — every pending, blocked,
     * or in-progress task is skipped with the given reason.
     *
     * **Important:** Call only when no tasks are actively executing. The
     * orchestrator invokes this after `await Promise.all()`, so no tasks are
     * in-flight. Calling while agents are running may mark an in-progress task
     * as skipped while its agent continues executing.
     */
    skipRemaining(reason?: string): void;
    /**
     * Recursively marks all tasks that (transitively) depend on `failedTaskId`
     * as `'failed'` with an informative message, firing `'task:failed'` for each.
     *
     * Only tasks in `'blocked'` or `'pending'` state are affected; tasks already
     * in a terminal state are left untouched.
     */
    private cascadeFailure;
    /**
     * Recursively marks all tasks that (transitively) depend on `skippedTaskId`
     * as `'skipped'`, firing `'task:skipped'` for each.
     */
    private cascadeSkip;
    /**
     * Returns the next `'pending'` task for `assignee` (matched against
     * `task.assignee`), or `undefined` if none exists.
     *
     * If `assignee` is omitted, behaves like {@link nextAvailable}.
     */
    next(assignee?: string): Task | undefined;
    /**
     * Returns the next `'pending'` task that has no `assignee` restriction, or
     * the first `'pending'` task overall when all pending tasks have an assignee.
     */
    nextAvailable(): Task | undefined;
    /** Returns a snapshot array of all tasks (any status). */
    list(): Task[];
    /** Returns all tasks whose `status` matches `status`. */
    getByStatus(status: TaskStatus): Task[];
    /**
     * Returns `true` when every task in the queue has reached a terminal state
     * (`'completed'`, `'failed'`, or `'skipped'`), **or** the queue is empty.
     */
    isComplete(): boolean;
    /**
     * Returns a progress snapshot.
     *
     * @example
     * ```ts
     * const { completed, total } = queue.getProgress()
     * console.log(`${completed}/${total} tasks done`)
     * ```
     */
    getProgress(): {
        total: number;
        completed: number;
        failed: number;
        skipped: number;
        inProgress: number;
        pending: number;
        blocked: number;
    };
    /**
     * Subscribes to a queue event.
     *
     * @returns An unsubscribe function. Calling it is idempotent.
     *
     * @example
     * ```ts
     * const off = queue.on('task:ready', (task) => execute(task))
     * // later…
     * off()
     * ```
     */
    on<E extends TaskQueueEvent>(event: E, handler: HandlerFor<E>): () => void;
    /**
     * Evaluates whether `task` should start as `'blocked'` based on the tasks
     * already registered in the queue.
     */
    private resolveInitialStatus;
    /**
     * After a task completes, scan all `'blocked'` tasks and promote any that are
     * now fully satisfied to `'pending'`, firing `'task:ready'` for each.
     *
     * The task array and lookup map are built once for the entire scan to keep
     * the operation O(n) rather than O(n²).
     */
    private unblockDependents;
    private emit;
    private emitAllComplete;
    private requireTask;
}
export {};
//# sourceMappingURL=queue.d.ts.map