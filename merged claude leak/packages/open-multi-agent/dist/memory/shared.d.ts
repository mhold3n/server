/**
 * @fileoverview Shared memory layer for teams of cooperating agents.
 *
 * Each agent writes under its own namespace (`<agentName>/<key>`) so entries
 * remain attributable, while any agent may read any entry. The
 * {@link SharedMemory.getSummary} method produces a human-readable digest
 * suitable for injecting into an agent's context window.
 */
import type { MemoryEntry, MemoryStore } from '../types.js';
/**
 * Namespaced shared memory for a team of agents.
 *
 * Writes are namespaced as `<agentName>/<key>` so that entries from different
 * agents never collide and are always attributable. Reads are namespace-aware
 * but also accept fully-qualified keys, making cross-agent reads straightforward.
 *
 * @example
 * ```ts
 * const mem = new SharedMemory()
 *
 * await mem.write('researcher', 'findings', 'TypeScript 5.5 ships const type params')
 * await mem.write('coder', 'plan', 'Implement feature X using const type params')
 *
 * const entry = await mem.read('researcher/findings')
 * const all = await mem.listByAgent('researcher')
 * const summary = await mem.getSummary()
 * ```
 */
export declare class SharedMemory {
    private readonly store;
    constructor();
    /**
     * Write `value` under the namespaced key `<agentName>/<key>`.
     *
     * Metadata is merged with a `{ agent: agentName }` marker so consumers can
     * identify provenance when iterating all entries.
     *
     * @param agentName - The writing agent's name (used as a namespace prefix).
     * @param key       - Logical key within the agent's namespace.
     * @param value     - String value to store (serialise objects before writing).
     * @param metadata  - Optional extra metadata stored alongside the entry.
     */
    write(agentName: string, key: string, value: string, metadata?: Record<string, unknown>): Promise<void>;
    /**
     * Read an entry by its fully-qualified key (`<agentName>/<key>`).
     *
     * Returns `null` when the key is absent.
     */
    read(key: string): Promise<MemoryEntry | null>;
    /** Returns every entry in the shared store, regardless of agent. */
    listAll(): Promise<MemoryEntry[]>;
    /**
     * Returns all entries written by `agentName` (i.e. those whose key starts
     * with `<agentName>/`).
     */
    listByAgent(agentName: string): Promise<MemoryEntry[]>;
    /**
     * Produces a human-readable summary of all entries in the store.
     *
     * The output is structured as a markdown-style block, grouped by agent, and
     * is designed to be prepended to an agent's system prompt or injected as a
     * user turn so the agent has context about what its teammates know.
     *
     * Returns an empty string when the store is empty.
     *
     * @example
     * ```
     * ## Shared Team Memory
     *
     * ### researcher
     * - findings: TypeScript 5.5 ships const type params
     *
     * ### coder
     * - plan: Implement feature X using const type params
     * ```
     */
    getSummary(): Promise<string>;
    /**
     * Returns the underlying {@link MemoryStore} so callers that only need the
     * raw key-value interface can receive a properly typed reference without
     * accessing private fields via bracket notation.
     */
    getStore(): MemoryStore;
    private static namespaceKey;
}
//# sourceMappingURL=shared.d.ts.map