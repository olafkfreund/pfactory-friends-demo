/**
 * In-process repository for [Connection]s and [Message]s.
 *
 * AC#6: two people can exchange messages only after both have accepted the
 * connection.  [sendMessage] enforces this invariant: it rejects any call
 * where the pair does not hold an [ConnectionStatus.ACCEPTED] connection.
 *
 * AC#7 / P5 (blocking): [sendConnectionRequest] and [sendMessage] check
 * [ProfileRepository.isBlocked] in both directions so that a blocked user can
 * neither initiate a new request nor send a message to anyone who has blocked
 * them, and vice-versa.
 *
 * P1: connection and message data is kept for as long as the connection exists.
 * There is no other copy and no background retention.
 *
 * P5: every person-to-person surface ships with blocking in the same phase.
 *
 * Persistence is a [MutableMap] and a [MutableList], so this is a single-process,
 * non-durable store; it is enough to prove the connect/accept/message round-trip.
 *
 * The same logic exists verbatim in the Swift lane (MessagingRepository.swift)
 * so that both platforms share one set of rules (constitution P9).
 */
class MessagingRepository(private val profileRepository: ProfileRepository) {

    private val connections: MutableMap<String, Connection> = mutableMapOf()
    private val messages: MutableList<Message> = mutableListOf()
    private var nextMessageId: Int = 0

    /**
     * Tracks the epoch-millisecond timestamps of each successfully sent connection
     * request, keyed by requester id.
     *
     * AC#5: at most [MAX_CONNECTION_REQUESTS_PER_DAY] new requests per requester
     * in any rolling 24-hour window. Entries older than the current window are
     * pruned on each call to keep the map bounded.
     */
    private val requestTimestamps: MutableMap<String, MutableList<Long>> = mutableMapOf()

    /**
     * Attempts to send a connection request from [requesterId] to [recipientId].
     *
     * Returns the newly created [Connection] (with status [ConnectionStatus.PENDING])
     * on success, or `null` on any failure. To obtain the machine-readable refusal
     * reason, use [sendConnectionRequestResult] instead.
     *
     * Only successfully created connections count toward the rate limit; rejected
     * duplicates and blocked attempts do not.
     *
     * Messaging is not permitted until the recipient calls
     * [acceptConnectionRequest] (AC#6).
     */
    fun sendConnectionRequest(requesterId: String, recipientId: String): Connection? =
        when (val outcome = sendConnectionRequestResult(requesterId, recipientId)) {
            is ConnectionRequestResult.Allowed -> outcome.connection
            is ConnectionRequestResult.Refused -> null
        }

    /**
     * Attempts to send a connection request from [requesterId] to [recipientId],
     * returning a [ConnectionRequestResult] that carries the outcome and, on
     * refusal, the machine-readable [ConnectionRequestRefusal] reason.
     *
     * C14: every eligibility and refusal decision the core makes carries a
     * machine-readable reason so a client can tell a person why something was
     * refused and an auditor can verify the correct policy was applied.
     *
     * Returns [ConnectionRequestResult.Allowed] with the new [Connection] (status
     * [ConnectionStatus.PENDING]) on success. Returns [ConnectionRequestResult.Refused]
     * with a [ConnectionRequestRefusal] when any of the following are true:
     * - either id is blank or whitespace-only → [ConnectionRequestRefusal.BLANK_ID];
     * - the requester and recipient are the same person → [ConnectionRequestRefusal.SELF_REQUEST];
     * - either party has blocked the other → [ConnectionRequestRefusal.BLOCKED];
     * - a connection between this pair already exists → [ConnectionRequestRefusal.ALREADY_EXISTS];
     * - the requester has reached the daily limit → [ConnectionRequestRefusal.RATE_LIMIT_EXCEEDED].
     *
     * The same algorithm is in the Swift lane (MessagingRepository.swift),
     * constitution P9.
     */
    fun sendConnectionRequestResult(
        requesterId: String,
        recipientId: String,
    ): ConnectionRequestResult {
        if (requesterId.isBlank() || recipientId.isBlank())
            return ConnectionRequestResult.Refused(ConnectionRequestRefusal.BLANK_ID)
        if (requesterId == recipientId)
            return ConnectionRequestResult.Refused(ConnectionRequestRefusal.SELF_REQUEST)
        // AC#7 / P5: a blocked user cannot initiate or receive a connection request.
        if (profileRepository.isBlocked(blockerId = recipientId, blockedId = requesterId) ||
            profileRepository.isBlocked(blockerId = requesterId, blockedId = recipientId))
            return ConnectionRequestResult.Refused(ConnectionRequestRefusal.BLOCKED)
        val connectionId = canonicalConnectionId(requesterId, recipientId)
        // Idempotency: if a connection already exists (pending or accepted), refuse the
        // new attempt rather than silently creating a duplicate.
        if (connections.containsKey(connectionId))
            return ConnectionRequestResult.Refused(ConnectionRequestRefusal.ALREADY_EXISTS)
        // AC#5: at most MAX_CONNECTION_REQUESTS_PER_DAY new requests in any 24-hour window.
        val nowMs = System.currentTimeMillis()
        val windowStartMs = nowMs - MILLIS_PER_DAY
        val timestamps = requestTimestamps.getOrPut(requesterId) { mutableListOf() }
        // Prune expired entries so the map does not grow without bound.
        timestamps.removeAll { it < windowStartMs }
        if (timestamps.size >= MAX_CONNECTION_REQUESTS_PER_DAY)
            return ConnectionRequestResult.Refused(ConnectionRequestRefusal.RATE_LIMIT_EXCEEDED)
        val connection = Connection(
            id = connectionId,
            requesterId = requesterId,
            recipientId = recipientId,
        )
        connections[connectionId] = connection
        timestamps.add(nowMs)
        return ConnectionRequestResult.Allowed(connection)
    }

    /**
     * Accepts the pending connection identified by [connectionId] on behalf of
     * [acceptorId] (the recipient).
     *
     * Returns `true` when the connection transitions from [ConnectionStatus.PENDING]
     * to [ConnectionStatus.ACCEPTED].  Returns `false` when:
     * - no connection with [connectionId] exists;
     * - [acceptorId] is not the recipient of the request;
     * - the connection is not currently [ConnectionStatus.PENDING].
     *
     * After this call returns `true`, both parties may send messages (AC#6).
     */
    fun acceptConnectionRequest(connectionId: String, acceptorId: String): Boolean {
        val connection = connections[connectionId] ?: return false
        if (connection.recipientId != acceptorId) return false
        if (connection.status != ConnectionStatus.PENDING) return false
        connections[connectionId] = connection.copy(status = ConnectionStatus.ACCEPTED)
        return true
    }

    /**
     * Returns `true` when [userId1] and [userId2] hold an [ConnectionStatus.ACCEPTED]
     * connection.
     *
     * The check is symmetric: `areConnected("a", "b") == areConnected("b", "a")`.
     *
     * AC#6: only an accepted connection permits messaging between the pair.
     */
    fun areConnected(userId1: String, userId2: String): Boolean {
        val connectionId = canonicalConnectionId(userId1, userId2)
        return connections[connectionId]?.status == ConnectionStatus.ACCEPTED
    }

    /**
     * Sends a message from [senderId] to [recipientId] with the given [body].
     *
     * Returns the persisted [Message] on success. Returns `null` on any failure.
     * To obtain the machine-readable refusal reason, use [sendMessageResult] instead.
     *
     * The [body] is stored as supplied; no trimming is applied. The caller is
     * responsible for any display normalisation before calling.
     */
    fun sendMessage(senderId: String, recipientId: String, body: String): Message? =
        when (val outcome = sendMessageResult(senderId, recipientId, body)) {
            is MessageResult.Allowed -> outcome.message
            is MessageResult.Refused -> null
        }

    /**
     * Sends a message from [senderId] to [recipientId] with the given [body],
     * returning a [MessageResult] that carries the outcome and, on refusal,
     * the machine-readable [MessageRefusal] reason.
     *
     * C14: every eligibility and refusal decision the core makes carries a
     * machine-readable reason so a client can tell a person why something was
     * refused and an auditor can verify the correct policy was applied.
     *
     * Returns [MessageResult.Allowed] with the persisted [Message] on success.
     * Returns [MessageResult.Refused] with a [MessageRefusal] when any of the
     * following are true:
     * - the pair does not hold an ACCEPTED connection → [MessageRefusal.NOT_CONNECTED];
     * - [recipientId] has blocked [senderId] → [MessageRefusal.BLOCKED];
     * - [body] is blank or whitespace-only → [MessageRefusal.BLANK_BODY];
     * - [body] exceeds [MAX_MESSAGE_LENGTH] → [MessageRefusal.BODY_TOO_LONG].
     *
     * The [body] is stored as supplied; no trimming is applied.
     *
     * The same algorithm is in the Swift lane (MessagingRepository.swift),
     * constitution P9.
     */
    fun sendMessageResult(senderId: String, recipientId: String, body: String): MessageResult {
        // AC#6: the pair must hold an ACCEPTED connection.
        if (!areConnected(senderId, recipientId))
            return MessageResult.Refused(MessageRefusal.NOT_CONNECTED)
        // AC#7 / P5: a blocked user cannot send messages.
        if (profileRepository.isBlocked(blockerId = recipientId, blockedId = senderId))
            return MessageResult.Refused(MessageRefusal.BLOCKED)
        // Message body validation.
        if (body.isBlank())
            return MessageResult.Refused(MessageRefusal.BLANK_BODY)
        if (body.length > MAX_MESSAGE_LENGTH)
            return MessageResult.Refused(MessageRefusal.BODY_TOO_LONG)
        val message = Message(
            id = "msg-${nextMessageId++}",
            senderId = senderId,
            recipientId = recipientId,
            body = body,
        )
        messages.add(message)
        return MessageResult.Allowed(message)
    }

    /**
     * Returns all messages exchanged between [userId1] and [userId2], in the
     * order they were sent (chronological insertion order).
     *
     * The result includes messages sent in either direction between the pair.
     * Returns an empty list when no messages have been exchanged.
     */
    fun getMessages(userId1: String, userId2: String): List<Message> =
        messages.filter { msg ->
            (msg.senderId == userId1 && msg.recipientId == userId2) ||
            (msg.senderId == userId2 && msg.recipientId == userId1)
        }

    /**
     * Returns a stable, symmetric storage key for the connection between [id1]
     * and [id2].
     *
     * The key is identical regardless of argument order, so one [Connection]
     * record covers both the (A→B) and (B→A) perspectives.
     */
    private fun canonicalConnectionId(id1: String, id2: String): String {
        val (a, b) = if (id1 <= id2) Pair(id1, id2) else Pair(id2, id1)
        return "$a::$b"
    }

    companion object {
        /**
         * Maximum number of new connection requests a single user may send in
         * any rolling 24-hour window (AC#5).
         *
         * Only successfully created connections count; duplicate and blocked
         * attempts do not. The same constant exists in the Swift lane as
         * `MessagingRepository.maxConnectionRequestsPerDay` (constitution P9).
         */
        const val MAX_CONNECTION_REQUESTS_PER_DAY: Int = 20

        /** Length of the rate-limit window in milliseconds (24 hours). */
        private const val MILLIS_PER_DAY: Long = 24L * 60L * 60L * 1000L

        /**
         * Maximum allowed message body length, measured in characters
         * (UTF-16 code units, i.e. [String.length]).
         *
         * Placeholder value pending a product decision: no validated product
         * requirement has fixed this limit yet. Per `docs/product-decisions.md`,
         * code needing a limit should use a single named constant, mark it as a
         * placeholder, and say so in its PR. Keep it as the single source of
         * truth so the length rule lives in exactly one place.
         *
         * The same constant exists in the Swift lane as
         * `MessagingRepository.maxMessageLength` (constitution P9).
         */
        const val MAX_MESSAGE_LENGTH: Int = 2000
    }
}
