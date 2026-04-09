/**
 * @fileoverview Inter-agent message bus.
 *
 * Provides a lightweight pub/sub system so agents can exchange typed messages
 * without direct references to each other. All messages are retained in memory
 * for replay and audit; read-state is tracked per recipient.
 */
import { randomUUID } from 'node:crypto';
// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------
/** Returns true when `message` is addressed to `agentName`. */
function isAddressedTo(message, agentName) {
    if (message.to === '*') {
        // Broadcasts are delivered to everyone except the sender.
        return message.from !== agentName;
    }
    return message.to === agentName;
}
// ---------------------------------------------------------------------------
// MessageBus
// ---------------------------------------------------------------------------
/**
 * In-memory message bus for inter-agent communication.
 *
 * Agents can send point-to-point messages or broadcasts. Subscribers are
 * notified synchronously (within the same microtask) when a new message
 * arrives addressed to them.
 *
 * @example
 * ```ts
 * const bus = new MessageBus()
 *
 * const unsubscribe = bus.subscribe('worker', (msg) => {
 *   console.log(`worker received: ${msg.content}`)
 * })
 *
 * bus.send('coordinator', 'worker', 'Start task A')
 * bus.broadcast('coordinator', 'All agents: stand by')
 *
 * unsubscribe()
 * ```
 */
export class MessageBus {
    /** All messages ever sent, in insertion order. */
    messages = [];
    /**
     * Per-agent set of message IDs that have already been marked as read.
     * A message absent from this set is considered unread.
     */
    readState = new Map();
    /**
     * Active subscribers keyed by agent name. Each subscriber is a callback
     * paired with a unique subscription ID used for unsubscription.
     */
    subscribers = new Map();
    // ---------------------------------------------------------------------------
    // Write operations
    // ---------------------------------------------------------------------------
    /**
     * Send a message from `from` to `to`.
     *
     * @returns The persisted {@link Message} including its generated ID and timestamp.
     */
    send(from, to, content) {
        const message = {
            id: randomUUID(),
            from,
            to,
            content,
            timestamp: new Date(),
        };
        this.persist(message);
        return message;
    }
    /**
     * Broadcast a message from `from` to all other agents (`to === '*'`).
     *
     * @returns The persisted broadcast {@link Message}.
     */
    broadcast(from, content) {
        return this.send(from, '*', content);
    }
    // ---------------------------------------------------------------------------
    // Read operations
    // ---------------------------------------------------------------------------
    /**
     * Returns messages that have not yet been marked as read by `agentName`,
     * including both direct messages and broadcasts addressed to them.
     */
    getUnread(agentName) {
        const read = this.readState.get(agentName) ?? new Set();
        return this.messages.filter((m) => isAddressedTo(m, agentName) && !read.has(m.id));
    }
    /**
     * Returns every message (read or unread) addressed to `agentName`,
     * preserving insertion order.
     */
    getAll(agentName) {
        return this.messages.filter((m) => isAddressedTo(m, agentName));
    }
    /**
     * Mark a set of messages as read for `agentName`.
     * Passing IDs that were already marked, or do not exist, is a no-op.
     */
    markRead(agentName, messageIds) {
        if (messageIds.length === 0)
            return;
        let read = this.readState.get(agentName);
        if (!read) {
            read = new Set();
            this.readState.set(agentName, read);
        }
        for (const id of messageIds) {
            read.add(id);
        }
    }
    /**
     * Returns all messages exchanged between `agent1` and `agent2` (in either
     * direction), sorted chronologically.
     */
    getConversation(agent1, agent2) {
        return this.messages.filter((m) => (m.from === agent1 && m.to === agent2) ||
            (m.from === agent2 && m.to === agent1));
    }
    // ---------------------------------------------------------------------------
    // Subscriptions
    // ---------------------------------------------------------------------------
    /**
     * Subscribe to new messages addressed to `agentName`.
     *
     * The `callback` is invoked synchronously after each matching message is
     * persisted. Returns an unsubscribe function; calling it is idempotent.
     *
     * @example
     * ```ts
     * const off = bus.subscribe('agent-b', (msg) => handleMessage(msg))
     * // Later…
     * off()
     * ```
     */
    subscribe(agentName, callback) {
        let agentSubs = this.subscribers.get(agentName);
        if (!agentSubs) {
            agentSubs = new Map();
            this.subscribers.set(agentName, agentSubs);
        }
        const id = Symbol();
        agentSubs.set(id, callback);
        return () => {
            agentSubs.delete(id);
        };
    }
    // ---------------------------------------------------------------------------
    // Private helpers
    // ---------------------------------------------------------------------------
    persist(message) {
        this.messages.push(message);
        this.notifySubscribers(message);
    }
    notifySubscribers(message) {
        // Notify direct subscribers of `message.to` (unless broadcast).
        if (message.to !== '*') {
            this.fireCallbacks(message.to, message);
            return;
        }
        // Broadcast: notify all subscribers except the sender.
        for (const [agentName, subs] of this.subscribers) {
            if (agentName !== message.from && subs.size > 0) {
                this.fireCallbacks(agentName, message);
            }
        }
    }
    fireCallbacks(agentName, message) {
        const subs = this.subscribers.get(agentName);
        if (!subs)
            return;
        for (const callback of subs.values()) {
            callback(message);
        }
    }
}
//# sourceMappingURL=messaging.js.map