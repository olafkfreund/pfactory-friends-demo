/** The lifecycle state of a connection between two users. */
enum class ConnectionStatus {
    /**
     * The requester has initiated the connection; the recipient has not yet
     * responded.  Messaging is not permitted in this state (AC#6).
     */
    PENDING,

    /**
     * Both parties have accepted: the requester implicitly accepted by sending,
     * and the recipient accepted explicitly.  Messaging is permitted in this
     * state (AC#6).
     */
    ACCEPTED,
}

/**
 * A directed connection request from [requesterId] to [recipientId].
 *
 * A connection starts as [ConnectionStatus.PENDING] and transitions to
 * [ConnectionStatus.ACCEPTED] when the recipient calls
 * [MessagingRepository.acceptConnectionRequest]. Only an [ConnectionStatus.ACCEPTED]
 * connection unlocks messaging between the two people (AC#6).
 *
 * P1: connection data is owned by the pair and kept for as long as the
 * connection exists. There is no other copy and no background retention.
 * P5: the messaging surface is gated by this connection status, ensuring
 * every person-to-person channel ships with a clear consent signal.
 *
 * The same shape exists verbatim in the Swift lane (Connection.swift) so that
 * both platforms share one model (constitution P9).
 */
data class Connection(
    val id: String,
    val requesterId: String,
    val recipientId: String,
    val status: ConnectionStatus = ConnectionStatus.PENDING,
)
