/// A message sent from `senderId` to `recipientId` with the given `body`.
///
/// Messages can only exist within an `.accepted` connection;
/// `MessagingRepository.sendMessage(...)` enforces this invariant before
/// persisting anything (AC#6).
///
/// The `body` must be non-blank and at most
/// `MessagingRepository.maxMessageLength` characters. Both checks are performed
/// by `MessagingRepository.sendMessage(...)` before the message is stored.
///
/// P1: message data is personal data. It is kept for as long as the connection
/// exists and is the caller's responsibility to purge on account deletion.
/// P5: the messaging surface is gated by connection status so that a blocked
/// user can never send a message (constitution P5 / AC#7).
///
/// The same shape exists verbatim in the Kotlin lane (Message.kt) so that both
/// platforms share one model (constitution P9).
public struct Message: Equatable {
    public let id: String
    public let senderId: String
    public let recipientId: String
    public let body: String

    public init(id: String, senderId: String, recipientId: String, body: String) {
        self.id = id
        self.senderId = senderId
        self.recipientId = recipientId
        self.body = body
    }
}
