/**
 * Machine-readable refusal reasons for connection-request decisions.
 *
 * AC (C14): every eligibility and refusal decision the core makes carries a
 * machine-readable reason, so a client can tell a person why something was
 * refused and an auditor can verify that the correct policy was applied.
 *
 * The existing [MessagingRepository.sendConnectionRequest] returns null for
 * all failure cases, which is opaque. [MessagingRepository.sendConnectionRequestResult]
 * returns [ConnectionRequestResult] so callers can distinguish between them.
 *
 * The same type exists verbatim in the Swift lane (DomainOutcome.swift)
 * so that both platforms surface the same reasons (constitution P9).
 */
sealed class ConnectionRequestResult {
    /** The request was accepted and a new pending [connection] was created. */
    data class Allowed(
        val connection: Connection,
    ) : ConnectionRequestResult()

    /** The request was refused for [reason]. No connection was created. */
    data class Refused(
        val reason: ConnectionRequestRefusal,
    ) : ConnectionRequestResult()
}

/**
 * The specific reason a connection request was refused.
 *
 * The same values exist verbatim in the Swift lane (DomainOutcome.swift)
 * so that both platforms surface the same reasons (constitution P9).
 */
enum class ConnectionRequestRefusal {
    /** Either the requester or recipient id was blank or whitespace-only. */
    BLANK_ID,

    /** The requester and recipient are the same person. */
    SELF_REQUEST,

    /**
     * One party has blocked the other.
     *
     * Constitution P5 (enforceable): blocking prevents all future
     * person-to-person contact. The caller receives this reason rather than
     * a generic refusal so it can surface it (without revealing who blocked
     * whom) or log it for safety review.
     */
    BLOCKED,

    /**
     * A connection between this pair already exists (in either state).
     *
     * The requester may retry after the existing connection is resolved.
     */
    ALREADY_EXISTS,

    /**
     * The requester has sent [MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY]
     * or more new requests in the rolling 24-hour window.
     *
     * AC#5: at most twenty requests per requester per day.
     */
    RATE_LIMIT_EXCEEDED,
}

/**
 * Machine-readable refusal reasons for message-send decisions.
 *
 * The existing [MessagingRepository.sendMessage] returns null for all
 * failure cases. [MessagingRepository.sendMessageResult] returns
 * [MessageResult] so callers can distinguish between them.
 *
 * The same type exists verbatim in the Swift lane (DomainOutcome.swift)
 * so that both platforms surface the same reasons (constitution P9).
 */
sealed class MessageResult {
    /** The message was accepted and [message] was persisted. */
    data class Allowed(
        val message: Message,
    ) : MessageResult()

    /** The message was refused for [reason]. Nothing was persisted. */
    data class Refused(
        val reason: MessageRefusal,
    ) : MessageResult()
}

/**
 * The specific reason a message was refused.
 *
 * The same values exist verbatim in the Swift lane (DomainOutcome.swift)
 * so that both platforms surface the same reasons (constitution P9).
 */
enum class MessageRefusal {
    /**
     * No accepted connection exists between the sender and recipient.
     *
     * AC#6: messaging is only permitted after both people have accepted a
     * connection.
     */
    NOT_CONNECTED,

    /**
     * One party has blocked the other.
     *
     * Constitution P5 (enforceable): blocking prevents all future
     * person-to-person contact.
     */
    BLOCKED,

    /** The message body was blank or whitespace-only after trimming. */
    BLANK_BODY,

    /** The message body exceeded [MessagingRepository.MAX_MESSAGE_LENGTH] characters. */
    BODY_TOO_LONG,
}
