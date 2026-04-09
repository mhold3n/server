/**
 * @fileoverview Shared counting semaphore for concurrency control.
 *
 * Used by both {@link ToolExecutor} and {@link AgentPool} to cap the number of
 * concurrent async operations without requiring any third-party dependencies.
 *
 * This is intentionally self-contained and tuned for Promise/async use —
 * not a general OS-semaphore replacement.
 */
// ---------------------------------------------------------------------------
// Semaphore
// ---------------------------------------------------------------------------
/**
 * Classic counting semaphore for concurrency control.
 *
 * `acquire()` resolves immediately if a slot is free, otherwise queues the
 * caller. `release()` unblocks the next waiter in FIFO order.
 *
 * Node.js is single-threaded, so this is safe without atomics or mutex
 * primitives — the semaphore gates concurrent async operations, not CPU threads.
 */
export class Semaphore {
    max;
    current = 0;
    queue = [];
    /**
     * @param max - Maximum number of concurrent holders. Must be >= 1.
     */
    constructor(max) {
        this.max = max;
        if (max < 1) {
            throw new RangeError(`Semaphore max must be at least 1, got ${max}`);
        }
    }
    /**
     * Acquire a slot. Resolves immediately when one is free, or waits until a
     * holder calls `release()`.
     */
    acquire() {
        if (this.current < this.max) {
            this.current++;
            return Promise.resolve();
        }
        return new Promise(resolve => {
            this.queue.push(resolve);
        });
    }
    /**
     * Release a previously acquired slot.
     * If callers are queued, the next one is unblocked synchronously.
     */
    release() {
        const next = this.queue.shift();
        if (next !== undefined) {
            // A queued caller is waiting — hand the slot directly to it.
            // `current` stays the same: we consumed the slot immediately.
            next();
        }
        else {
            this.current--;
        }
    }
    /**
     * Run `fn` while holding one slot, automatically releasing it afterward
     * even if `fn` throws.
     */
    async run(fn) {
        await this.acquire();
        try {
            return await fn();
        }
        finally {
            this.release();
        }
    }
    /** Number of slots currently in use. */
    get active() {
        return this.current;
    }
    /** Number of callers waiting for a slot. */
    get pending() {
        return this.queue.length;
    }
}
//# sourceMappingURL=semaphore.js.map