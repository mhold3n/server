/**
 * @fileoverview Pure task utility functions.
 *
 * These helpers operate on plain {@link Task} values without any mutable
 * state, making them safe to use in reducers, tests, and reactive pipelines.
 * Stateful orchestration belongs in {@link TaskQueue}.
 */
import type { Task } from '../types.js';
/**
 * Creates a new {@link Task} with a generated UUID, `'pending'` status, and
 * `createdAt`/`updatedAt` timestamps set to the current instant.
 *
 * @example
 * ```ts
 * const task = createTask({
 *   title: 'Research competitors',
 *   description: 'Identify the top 5 competitors and their pricing',
 *   assignee: 'researcher',
 * })
 * ```
 */
export declare function createTask(input: {
    title: string;
    description: string;
    assignee?: string;
    dependsOn?: string[];
    maxRetries?: number;
    retryDelayMs?: number;
    retryBackoff?: number;
}): Task;
/**
 * Returns `true` when `task` can be started immediately.
 *
 * A task is considered ready when:
 * 1. Its status is `'pending'`.
 * 2. Every task listed in `task.dependsOn` has status `'completed'`.
 *
 * Tasks whose dependencies are missing from `allTasks` are treated as
 * unresolvable and therefore **not** ready.
 *
 * @param task      - The task to evaluate.
 * @param allTasks  - The full collection of tasks in the current queue/plan.
 * @param taskById  - Optional pre-built id→task map. When provided the function
 *                    skips rebuilding the map, reducing the complexity of
 *                    call-sites that invoke `isTaskReady` inside a loop from
 *                    O(n²) to O(n).
 */
export declare function isTaskReady(task: Task, allTasks: Task[], taskById?: Map<string, Task>): boolean;
/**
 * Returns `tasks` sorted so that each task appears after all of its
 * dependencies — a standard topological (Kahn's algorithm) ordering.
 *
 * Tasks with no dependencies come first. If the graph contains a cycle the
 * function returns a partial result containing only the tasks that could be
 * ordered; use {@link validateTaskDependencies} to detect cycles before calling
 * this function in production paths.
 *
 * @example
 * ```ts
 * const ordered = getTaskDependencyOrder(tasks)
 * for (const task of ordered) {
 *   await run(task)
 * }
 * ```
 */
export declare function getTaskDependencyOrder(tasks: Task[]): Task[];
/**
 * Validates the dependency graph of a task collection.
 *
 * Checks for:
 * - References to unknown task IDs in `dependsOn`.
 * - Cycles (a task depending on itself, directly or transitively).
 * - Self-dependencies (`task.dependsOn` includes its own `id`).
 *
 * @returns An object with `valid: true` when no issues were found, or
 *          `valid: false` with a non-empty `errors` array describing each
 *          problem.
 *
 * @example
 * ```ts
 * const { valid, errors } = validateTaskDependencies(tasks)
 * if (!valid) throw new Error(errors.join('\n'))
 * ```
 */
export declare function validateTaskDependencies(tasks: Task[]): {
    valid: boolean;
    errors: string[];
};
//# sourceMappingURL=task.d.ts.map