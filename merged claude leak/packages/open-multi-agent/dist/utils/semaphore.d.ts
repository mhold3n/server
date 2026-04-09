/**
 * @fileoverview Shared counting semaphore for concurrency control.
 *
 * Used by both {@link ToolExecutor} and {@link AgentPool} to cap the number of
 * concurrent async operations without requiring any third-party dependencies.
 *
 * This is intentionally self-contained and tuned for Promise/async use —
 * not a general OS-semaphore replacement.
 */
/**
 * Classic counting semaphore for concurrency control.
 *
 * `acquire()` resolves immediately if a slot is free, otherwise queues the
 * caller. `release()` unblocks the next waiter in FIFO order.
 *
 * Node.js is single-threaded, so this is safe without atomics or mutex
 * primitives — the semaphore gates concurrent async operations, not CPU threads.
 */
export declare class Semaphore {
    private readonly max;
    private current;
    private readonly queue;
    /**
     * @param max - Maximum number of concurrent holders. Must be >= 1.
     */
    constructor(max: number);
    /**
     * Acquire a slot. Resolves immediately when one is free, or waits until a
     * holder calls `release()`.
     */
    acquire(): Promise<void>;
    /**
     * Release a previously acquired slot.
     * If callers are queued, the next one is unblocked synchronously.
     */
    release(): void;
    /**
     * Run `fn` while holding one slot, automatically releasing it afterward
     * even if `fn` throws.
     */
    run<T>(fn: () => Promise<T>): Promise<T>;
    /** Number of slots currently in use. */
    get active(): number;
    /** Number of callers waiting for a slot. */
    get pending(): number;
}
//# sourceMappingURL=semaphore.d.ts.map