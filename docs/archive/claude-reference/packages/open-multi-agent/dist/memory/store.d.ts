/**
 * @fileoverview In-memory implementation of {@link MemoryStore}.
 *
 * All data lives in a plain `Map` and is never persisted to disk. This is the
 * default store used by {@link SharedMemory} and is suitable for testing and
 * single-process use-cases. Swap it for a Redis or SQLite-backed implementation
 * in production by satisfying the same {@link MemoryStore} interface.
 */
import type { MemoryEntry, MemoryStore } from '../types.js';
/**
 * Synchronous-under-the-hood key/value store that exposes an `async` surface
 * so implementations can be swapped for async-native backends without changing
 * callers.
 *
 * All keys are treated as opaque strings. Values are always strings; structured
 * data must be serialised by the caller (e.g. `JSON.stringify`).
 *
 * @example
 * ```ts
 * const store = new InMemoryStore()
 * await store.set('config', JSON.stringify({ model: 'claude-opus-4-6' }))
 * const entry = await store.get('config')
 * ```
 */
export declare class InMemoryStore implements MemoryStore {
    private readonly data;
    /** Returns the entry for `key`, or `null` if not present. */
    get(key: string): Promise<MemoryEntry | null>;
    /**
     * Upserts `key` with `value` and optional `metadata`.
     *
     * If the key already exists its `createdAt` is **preserved** so callers can
     * detect when a value was first written.
     */
    set(key: string, value: string, metadata?: Record<string, unknown>): Promise<void>;
    /** Returns a snapshot of all entries in insertion order. */
    list(): Promise<MemoryEntry[]>;
    /**
     * Removes the entry for `key`.
     * Deleting a non-existent key is a no-op.
     */
    delete(key: string): Promise<void>;
    /** Removes **all** entries from the store. */
    clear(): Promise<void>;
    /**
     * Returns entries whose `key` starts with `query` **or** whose `value`
     * contains `query` (case-insensitive substring match).
     *
     * This is a simple linear scan; it is not suitable for very large stores
     * without an index layer on top.
     *
     * @example
     * ```ts
     * // Find all entries related to "research"
     * const hits = await store.search('research')
     * ```
     */
    search(query: string): Promise<MemoryEntry[]>;
    /** Returns the number of entries currently held in the store. */
    get size(): number;
    /** Returns `true` if `key` exists in the store. */
    has(key: string): boolean;
}
//# sourceMappingURL=store.d.ts.map