/// Machine-readable outcome of a connection-request attempt.
///
/// AC (C14): every eligibility and refusal decision the core makes carries a
/// machine-readable reason, so a client can tell a person why something was
/// refused and an auditor can verify that the correct policy was applied.
///
/// The existing `MessagingRepository.sendConnectionRequest(...)` returns `nil`
/// for all failure cases, which is opaque. `sendConnectionRequestResult(...)`
/// returns `ConnectionRequestResult` so callers can distinguish between them.
///
/// The same type exists verbatim in the Kotlin lane (DomainOutcome.kt) so that
/// both platforms surface the same reasons (constitution P9).
public enum ConnectionRequestResult {
    /// The request was accepted and a new pending `connection` was created.
    case allowed(connection: Connection)

    /// The request was refused for `reason`. No connection was created.
    case refused(reason: ConnectionRequestRefusal)
}

/// The specific reason a connection request was refused.
///
/// The same values exist verbatim in the Kotlin lane (DomainOutcome.kt) so
/// that both platforms surface the same reasons (constitution P9).
public enum ConnectionRequestRefusal {
    /// Either the requester or recipient id was blank or whitespace-only.
    case blankId

    /// The requester and recipient are the same person.
    case selfRequest

    /// One party has blocked the other.
    ///
    /// Constitution P5 (enforceable): blocking prevents all future
    /// person-to-person contact. The caller receives this reason rather than a
    /// generic refusal so it can surface it (without revealing who blocked whom)
    /// or log it for safety review.
    case blocked

    /// A connection between this pair already exists (in either state).
    ///
    /// The requester may retry after the existing connection is resolved.
    case alreadyExists

    /// The requester has reached `MessagingRepository.maxConnectionRequestsPerDay`
    /// or more new requests in the rolling 24-hour window.
    ///
    /// AC#5: at most twenty requests per requester per day.
    case rateLimitExceeded
}

/// Machine-readable outcome of a message-send attempt.
///
/// The existing `MessagingRepository.sendMessage(...)` returns `nil` for all
/// failure cases. `sendMessageResult(...)` returns `MessageResult` so callers
/// can distinguish between them.
///
/// The same type exists verbatim in the Kotlin lane (DomainOutcome.kt) so that
/// both platforms surface the same reasons (constitution P9).
public enum MessageResult {
    /// The message was accepted and `message` was persisted.
    case allowed(message: Message)

    /// The message was refused for `reason`. Nothing was persisted.
    case refused(reason: MessageRefusal)
}

/// The specific reason a message was refused.
///
/// The same values exist verbatim in the Kotlin lane (DomainOutcome.kt) so
/// that both platforms surface the same reasons (constitution P9).
public enum MessageRefusal {
    /// No accepted connection exists between the sender and recipient.
    ///
    /// AC#6: messaging is only permitted after both people have accepted a
    /// connection.
    case notConnected

    /// One party has blocked the other.
    ///
    /// Constitution P5 (enforceable): blocking prevents all future
    /// person-to-person contact.
    case blocked

    /// The message body was blank or whitespace-only.
    case blankBody

    /// The message body exceeded `MessagingRepository.maxMessageLength` characters.
    case bodyTooLong
}
