import Foundation

/// In-process repository for `Connection`s and `Message`s.
///
/// AC#6: two people can exchange messages only after both have accepted the
/// connection. `sendMessage(...)` enforces this invariant: it rejects any call
/// where the pair does not hold an `.accepted` connection.
///
/// AC#7 / P5 (blocking): `sendConnectionRequest(...)` and `sendMessage(...)`
/// check `ProfileRepository.isBlocked(blockerId:blockedId:)` in both directions
/// so that a blocked user can neither initiate a new request nor send a message
/// to anyone who has blocked them, and vice-versa.
///
/// P1: connection and message data is kept for as long as the connection exists.
/// There is no other copy and no background retention.
///
/// P5: every person-to-person surface ships with blocking in the same phase.
///
/// Persistence is a dictionary and an array, so this is a single-process,
/// non-durable store; it is enough to prove the connect/accept/message
/// round-trip.
///
/// The same logic exists verbatim in the Kotlin lane (MessagingRepository.kt)
/// so that both platforms share one set of rules (constitution P9).
public final class MessagingRepository {

    private var connections: [String: Connection] = [:]
    private var messages: [Message] = []
    private var nextMessageId: Int = 0
    private let profileRepository: ProfileRepository

    /// Tracks the epoch-second timestamps of each successfully sent connection
    /// request, keyed by requester id.
    ///
    /// AC#5: at most `maxConnectionRequestsPerDay` new requests per requester in
    /// any rolling 24-hour window. Entries older than the current window are
    /// pruned on each call to keep the dictionary bounded.
    private var requestTimestamps: [String: [TimeInterval]] = [:]

    public init(profileRepository: ProfileRepository) {
        self.profileRepository = profileRepository
    }

    /// Attempts to send a connection request from `requesterId` to `recipientId`.
    ///
    /// Returns the newly created `Connection` (with status `.pending`) on
    /// success, or `nil` on any failure. To obtain the machine-readable refusal
    /// reason, use `sendConnectionRequestResult(...)` instead.
    ///
    /// Only successfully created connections count toward the rate limit; rejected
    /// duplicates and blocked attempts do not.
    ///
    /// Messaging is not permitted until the recipient calls
    /// `acceptConnectionRequest(...)` (AC#6).
    @discardableResult
    public func sendConnectionRequest(requesterId: String, recipientId: String) -> Connection? {
        switch sendConnectionRequestResult(requesterId: requesterId, recipientId: recipientId) {
        case .allowed(let connection): return connection
        case .refused: return nil
        }
    }

    /// Attempts to send a connection request from `requesterId` to `recipientId`,
    /// returning a `ConnectionRequestResult` that carries the outcome and, on
    /// refusal, the machine-readable `ConnectionRequestRefusal` reason.
    ///
    /// C14: every eligibility and refusal decision the core makes carries a
    /// machine-readable reason so a client can tell a person why something was
    /// refused and an auditor can verify the correct policy was applied.
    ///
    /// Returns `.allowed(connection:)` with the new `Connection` (status `.pending`)
    /// on success. Returns `.refused(reason:)` with a `ConnectionRequestRefusal` when
    /// any of the following are true:
    /// - either id is blank or whitespace-only → `.blankId`;
    /// - the requester and recipient are the same person → `.selfRequest`;
    /// - either party has blocked the other → `.blocked`;
    /// - a connection between this pair already exists → `.alreadyExists`;
    /// - the requester has reached the daily limit → `.rateLimitExceeded`.
    ///
    /// The same algorithm is in the Kotlin lane (MessagingRepository.kt),
    /// constitution P9.
    public func sendConnectionRequestResult(requesterId: String, recipientId: String) -> ConnectionRequestResult {
        guard !requesterId.trimmingCharacters(in: .whitespaces).isEmpty,
              !recipientId.trimmingCharacters(in: .whitespaces).isEmpty else {
            return .refused(reason: .blankId)
        }
        guard requesterId != recipientId else {
            return .refused(reason: .selfRequest)
        }
        // AC#7 / P5: a blocked user cannot initiate or receive a connection request.
        guard !profileRepository.isBlocked(blockerId: recipientId, blockedId: requesterId),
              !profileRepository.isBlocked(blockerId: requesterId, blockedId: recipientId) else {
            return .refused(reason: .blocked)
        }
        let connectionId = canonicalConnectionId(requesterId, recipientId)
        // Idempotency: if a connection already exists (pending or accepted), reject the
        // new attempt rather than silently creating a duplicate.
        guard connections[connectionId] == nil else {
            return .refused(reason: .alreadyExists)
        }
        // AC#5: at most maxConnectionRequestsPerDay new requests in any 24-hour window.
        let nowSeconds = Date().timeIntervalSince1970
        let windowStart = nowSeconds - MessagingRepository.secondsPerDay
        var timestamps = requestTimestamps[requesterId, default: []]
        // Prune expired entries so the dictionary does not grow without bound.
        timestamps = timestamps.filter { $0 >= windowStart }
        guard timestamps.count < MessagingRepository.maxConnectionRequestsPerDay else {
            return .refused(reason: .rateLimitExceeded)
        }
        let connection = Connection(
            id: connectionId,
            requesterId: requesterId,
            recipientId: recipientId
        )
        connections[connectionId] = connection
        timestamps.append(nowSeconds)
        requestTimestamps[requesterId] = timestamps
        return .allowed(connection: connection)
    }

    /// Accepts the pending connection identified by `connectionId` on behalf of
    /// `acceptorId` (the recipient).
    ///
    /// Returns `true` when the connection transitions from `.pending` to
    /// `.accepted`. Returns `false` when:
    /// - no connection with `connectionId` exists;
    /// - `acceptorId` is not the recipient of the request;
    /// - the connection is not currently `.pending`.
    ///
    /// After this call returns `true`, both parties may send messages (AC#6).
    @discardableResult
    public func acceptConnectionRequest(connectionId: String, acceptorId: String) -> Bool {
        guard let connection = connections[connectionId] else { return false }
        guard connection.recipientId == acceptorId else { return false }
        guard connection.status == .pending else { return false }
        connections[connectionId] = Connection(
            id: connection.id,
            requesterId: connection.requesterId,
            recipientId: connection.recipientId,
            status: .accepted
        )
        return true
    }

    /// Returns `true` when `userId1` and `userId2` hold an `.accepted` connection.
    ///
    /// The check is symmetric:
    /// `areConnected(userId1: "a", userId2: "b") == areConnected(userId1: "b", userId2: "a")`.
    ///
    /// AC#6: only an accepted connection permits messaging between the pair.
    public func areConnected(userId1: String, userId2: String) -> Bool {
        let connectionId = canonicalConnectionId(userId1, userId2)
        return connections[connectionId]?.status == .accepted
    }

    /// Sends a message from `senderId` to `recipientId` with the given `body`.
    ///
    /// Returns the persisted `Message` on success. Returns `nil` on any failure.
    /// To obtain the machine-readable refusal reason, use `sendMessageResult(...)`
    /// instead.
    ///
    /// The `body` is stored as supplied; no trimming is applied. The caller is
    /// responsible for any display normalisation before calling.
    public func sendMessage(senderId: String, recipientId: String, body: String) -> Message? {
        switch sendMessageResult(senderId: senderId, recipientId: recipientId, body: body) {
        case .allowed(let message): return message
        case .refused: return nil
        }
    }

    /// Sends a message from `senderId` to `recipientId` with the given `body`,
    /// returning a `MessageResult` that carries the outcome and, on refusal,
    /// the machine-readable `MessageRefusal` reason.
    ///
    /// C14: every eligibility and refusal decision the core makes carries a
    /// machine-readable reason so a client can tell a person why something was
    /// refused and an auditor can verify the correct policy was applied.
    ///
    /// Returns `.allowed(message:)` with the persisted `Message` on success.
    /// Returns `.refused(reason:)` with a `MessageRefusal` when any of the
    /// following are true:
    /// - the pair does not hold an `.accepted` connection → `.notConnected`;
    /// - `recipientId` has blocked `senderId` → `.blocked`;
    /// - `body` is blank or whitespace-only → `.blankBody`;
    /// - `body` exceeds `maxMessageLength` characters → `.bodyTooLong`.
    ///
    /// The `body` is stored as supplied; no trimming is applied.
    ///
    /// The same algorithm is in the Kotlin lane (MessagingRepository.kt),
    /// constitution P9.
    public func sendMessageResult(senderId: String, recipientId: String, body: String) -> MessageResult {
        // AC#6: the pair must hold an .accepted connection.
        guard areConnected(userId1: senderId, userId2: recipientId) else {
            return .refused(reason: .notConnected)
        }
        // AC#7 / P5: a blocked user cannot send messages.
        guard !profileRepository.isBlocked(blockerId: recipientId, blockedId: senderId) else {
            return .refused(reason: .blocked)
        }
        // Message body validation.
        guard !body.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return .refused(reason: .blankBody)
        }
        guard body.count <= MessagingRepository.maxMessageLength else {
            return .refused(reason: .bodyTooLong)
        }
        let messageId = "msg-\(nextMessageId)"
        nextMessageId += 1
        let message = Message(
            id: messageId,
            senderId: senderId,
            recipientId: recipientId,
            body: body
        )
        messages.append(message)
        return .allowed(message: message)
    }

    /// Returns all messages exchanged between `userId1` and `userId2`, in the
    /// order they were sent (chronological insertion order).
    ///
    /// The result includes messages sent in either direction between the pair.
    /// Returns an empty array when no messages have been exchanged.
    public func getMessages(userId1: String, userId2: String) -> [Message] {
        return messages.filter { msg in
            (msg.senderId == userId1 && msg.recipientId == userId2) ||
            (msg.senderId == userId2 && msg.recipientId == userId1)
        }
    }

    // MARK: - Constants

    /// Maximum number of new connection requests a single user may send in any
    /// rolling 24-hour window (AC#5).
    ///
    /// Only successfully created connections count; duplicate and blocked
    /// attempts do not. Mirrors `MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY`
    /// in the Kotlin lane (constitution P9).
    public static let maxConnectionRequestsPerDay: Int = 20

    /// Length of the rate-limit window in seconds (24 hours).
    private static let secondsPerDay: TimeInterval = 24 * 60 * 60

    /// Maximum allowed message body length, measured in extended grapheme
    /// clusters (Swift's `String.count`).
    ///
    /// Placeholder value pending a product decision. Mirrors
    /// `MessagingRepository.MAX_MESSAGE_LENGTH` in the Kotlin lane. Keep it as
    /// the single source of truth for this platform so the length rule lives in
    /// exactly one place.
    public static let maxMessageLength: Int = 2000

    // MARK: - Private helpers

    /// Returns a stable, symmetric storage key for the connection between `id1`
    /// and `id2`.
    ///
    /// The key is identical regardless of argument order, so one `Connection`
    /// record covers both the (A→B) and (B→A) perspectives.
    private func canonicalConnectionId(_ id1: String, _ id2: String) -> String {
        if id1 <= id2 {
            return "\(id1)::\(id2)"
        } else {
            return "\(id2)::\(id1)"
        }
    }
}
