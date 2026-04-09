/**
 * @fileoverview Inter-agent message bus.
 *
 * Provides a lightweight pub/sub system so agents can exchange typed messages
 * without direct references to each other. All messages are retained in memory
 * for replay and audit; read-state is tracked per recipient.
 */
/** A single message exchanged between agents (or broadcast to all). */
export interface Message {
    /** Stable UUID for this message. */
    readonly id: string;
    /** Name of the sending agent. */
    readonly from: string;
    /**
     * Recipient agent name, or `'*'` when the message is a broadcast intended
     * for every agent except the sender.
     */
    readonly to: string;
    readonly content: string;
    readonly timestamp: Date;
}
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
export declare class MessageBus {
    /** All messages ever sent, in insertion order. */
    private readonly messages;
    /**
     * Per-agent set of message IDs that have already been marked as read.
     * A message absent from this set is considered unread.
     */
    private readonly readState;
    /**
     * Active subscribers keyed by agent name. Each subscriber is a callback
     * paired with a unique subscription ID used for unsubscription.
     */
    private readonly subscribers;
    /**
     * Send a message from `from` to `to`.
     *
     * @returns The persisted {@link Message} including its generated ID and timestamp.
     */
    send(from: string, to: string, content: string): Message;
    /**
     * Broadcast a message from `from` to all other agents (`to === '*'`).
     *
     * @returns The persisted broadcast {@link Message}.
     */
    broadcast(from: string, content: string): Message;
    /**
     * Returns messages that have not yet been marked as read by `agentName`,
     * including both direct messages and broadcasts addressed to them.
     */
    getUnread(agentName: string): Message[];
    /**
     * Returns every message (read or unread) addressed to `agentName`,
     * preserving insertion order.
     */
    getAll(agentName: string): Message[];
    /**
     * Mark a set of messages as read for `agentName`.
     * Passing IDs that were already marked, or do not exist, is a no-op.
     */
    markRead(agentName: string, messageIds: string[]): void;
    /**
     * Returns all messages exchanged between `agent1` and `agent2` (in either
     * direction), sorted chronologically.
     */
    getConversation(agent1: string, agent2: string): Message[];
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
    subscribe(agentName: string, callback: (message: Message) => void): () => void;
    private persist;
    private notifySubscribers;
    private fireCallbacks;
}
//# sourceMappingURL=messaging.d.ts.map