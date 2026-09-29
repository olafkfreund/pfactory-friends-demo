/// The lifecycle state of a connection between two users.
///
/// The same values exist in the Kotlin lane (`ConnectionStatus`) so that both
/// platforms share one model (constitution P9).
public enum ConnectionStatus: Equatable {
    /// The requester has initiated the connection; the recipient has not yet
    /// responded. Messaging is not permitted in this state (AC#6).
    case pending

    /// Both parties have accepted: the requester implicitly accepted by sending,
    /// and the recipient accepted explicitly. Messaging is permitted in this
    /// state (AC#6).
    case accepted
}

/// A directed connection request from `requesterId` to `recipientId`.
///
/// A connection starts as `.pending` and transitions to `.accepted` when the
/// recipient calls `MessagingRepository.acceptConnectionRequest(...)`. Only an
/// `.accepted` connection unlocks messaging between the two people (AC#6).
///
/// P1: connection data is owned by the pair and kept for as long as the
/// connection exists. There is no other copy and no background retention.
/// P5: the messaging surface is gated by this connection status, ensuring
/// every person-to-person channel ships with a clear consent signal.
///
/// The same shape exists verbatim in the Kotlin lane (Connection.kt) so that
/// both platforms share one model (constitution P9).
public struct Connection: Equatable {
    public let id: String
    public let requesterId: String
    public let recipientId: String
    public let status: ConnectionStatus

    public init(
        id: String,
        requesterId: String,
        recipientId: String,
        status: ConnectionStatus = .pending
    ) {
        self.id = id
        self.requesterId = requesterId
        self.recipientId = recipientId
        self.status = status
    }
}
