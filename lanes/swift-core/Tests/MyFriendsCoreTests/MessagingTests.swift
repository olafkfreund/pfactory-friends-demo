import XCTest
@testable import MyFriendsCore

final class MessagingTests: XCTestCase {

    // MARK: - Helpers

    private func validPhoto(bytes: [UInt8] = [1, 2, 3], format: String = "png") -> ProfilePhoto {
        return ProfilePhoto(bytes: bytes, format: format)
    }

    /// Creates a `ProfileRepository` pre-populated with profiles whose ids are
    /// `ids`, then wraps it in a `MessagingRepository`.
    private func reposWithUsers(_ ids: String...) -> (ProfileRepository, MessagingRepository) {
        let profileRepo = ProfileRepository()
        for id in ids {
            try! profileRepo.save(Profile(id: id, displayName: "User \(id)", photo: validPhoto()))
        }
        let messagingRepo = MessagingRepository(profileRepository: profileRepo)
        return (profileRepo, messagingRepo)
    }

    // MARK: - AC#6: connection-state gate on sendMessage

    func testSendMessageWithoutAnyConnectionReturnsNil() {
        let (_, messaging) = reposWithUsers("alice", "bob")

        XCTAssertNil(messaging.sendMessage(senderId: "alice", recipientId: "bob", body: "Hello"))
    }

    func testSendMessageWithPendingConnectionReturnsNil() {
        // AC#6: a .pending connection is not enough — the recipient must accept first.
        let (_, messaging) = reposWithUsers("alice", "bob")
        messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")

        XCTAssertNil(messaging.sendMessage(senderId: "alice", recipientId: "bob", body: "Hello"))
    }

    func testSendMessageAfterAcceptedConnectionReturnsThePersistedMessage() {
        let (_, messaging) = reposWithUsers("alice", "bob")
        let connection = messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")!
        messaging.acceptConnectionRequest(connectionId: connection.id, acceptorId: "bob")

        let message = messaging.sendMessage(senderId: "alice", recipientId: "bob", body: "Hello")

        XCTAssertNotNil(message)
        XCTAssertEqual(message?.senderId, "alice")
        XCTAssertEqual(message?.recipientId, "bob")
        XCTAssertEqual(message?.body, "Hello")
    }

    func testSendMessageWorksInBothDirectionsAfterAcceptance() {
        // AC#6: the connection is mutual — either party can message once connected.
        let (_, messaging) = reposWithUsers("alice", "bob")
        let connection = messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")!
        messaging.acceptConnectionRequest(connectionId: connection.id, acceptorId: "bob")

        XCTAssertNotNil(messaging.sendMessage(senderId: "alice", recipientId: "bob", body: "Hi Bob"))
        XCTAssertNotNil(messaging.sendMessage(senderId: "bob", recipientId: "alice", body: "Hi Alice"))
    }

    // MARK: - areConnected

    func testAreConnectedReturnsFalseBeforeAnyConnectionRequest() {
        let (_, messaging) = reposWithUsers("alice", "bob")

        XCTAssertFalse(messaging.areConnected(userId1: "alice", userId2: "bob"))
    }

    func testAreConnectedReturnsFalseWhenConnectionIsPending() {
        let (_, messaging) = reposWithUsers("alice", "bob")
        messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")

        XCTAssertFalse(messaging.areConnected(userId1: "alice", userId2: "bob"))
    }

    func testAreConnectedReturnsTrueAfterAcceptanceAndCheckIsSymmetric() {
        let (_, messaging) = reposWithUsers("alice", "bob")
        let connection = messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")!
        messaging.acceptConnectionRequest(connectionId: connection.id, acceptorId: "bob")

        XCTAssertTrue(messaging.areConnected(userId1: "alice", userId2: "bob"))
        // Symmetric: swapping the arguments gives the same result.
        XCTAssertTrue(messaging.areConnected(userId1: "bob", userId2: "alice"))
    }

    // MARK: - sendConnectionRequest

    func testSendConnectionRequestCreatesAPendingConnection() {
        let (_, messaging) = reposWithUsers("alice", "bob")

        let connection = messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")

        XCTAssertNotNil(connection)
        XCTAssertEqual(connection?.status, .pending)
        XCTAssertEqual(connection?.requesterId, "alice")
        XCTAssertEqual(connection?.recipientId, "bob")
    }

    func testSendConnectionRequestToSelfReturnsNil() {
        let (_, messaging) = reposWithUsers("alice")

        XCTAssertNil(messaging.sendConnectionRequest(requesterId: "alice", recipientId: "alice"))
    }

    func testSendConnectionRequestWhenConnectionAlreadyExistsReturnsNil() {
        // Duplicate and reverse-direction requests are both rejected.
        let (_, messaging) = reposWithUsers("alice", "bob")
        messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")

        XCTAssertNil(messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob"))
        XCTAssertNil(messaging.sendConnectionRequest(requesterId: "bob", recipientId: "alice"))
    }

    // MARK: - acceptConnectionRequest

    func testAcceptConnectionRequestByRecipientMovesConnectionToAccepted() {
        let (_, messaging) = reposWithUsers("alice", "bob")
        let connection = messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")!

        XCTAssertTrue(messaging.acceptConnectionRequest(connectionId: connection.id, acceptorId: "bob"))
        XCTAssertTrue(messaging.areConnected(userId1: "alice", userId2: "bob"))
    }

    func testAcceptConnectionRequestByRequesterInsteadOfRecipientReturnsFalse() {
        // Only the intended recipient may accept; the requester may not accept
        // their own outgoing request.
        let (_, messaging) = reposWithUsers("alice", "bob")
        let connection = messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")!

        XCTAssertFalse(messaging.acceptConnectionRequest(connectionId: connection.id, acceptorId: "alice"))
        XCTAssertFalse(messaging.areConnected(userId1: "alice", userId2: "bob"))
    }

    func testAcceptConnectionRequestForUnknownConnectionIdReturnsFalse() {
        let (_, messaging) = reposWithUsers("alice", "bob")

        XCTAssertFalse(messaging.acceptConnectionRequest(connectionId: "no-such-id", acceptorId: "bob"))
    }

    func testAcceptConnectionRequestOnAlreadyAcceptedConnectionReturnsFalse() {
        // AC#6: a second acceptance attempt does not change state and returns false.
        let (_, messaging) = reposWithUsers("alice", "bob")
        let connection = messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")!
        messaging.acceptConnectionRequest(connectionId: connection.id, acceptorId: "bob")

        XCTAssertFalse(messaging.acceptConnectionRequest(connectionId: connection.id, acceptorId: "bob"))
    }

    // MARK: - AC#7: blocking integration

    func testSendConnectionRequestIsRejectedWhenRecipientHasBlockedRequester() {
        // AC#7 / P5: a blocked user cannot initiate contact.
        let (profiles, messaging) = reposWithUsers("alice", "bob")
        profiles.blockUser(blockerId: "bob", blockedId: "alice")

        XCTAssertNil(messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob"))
    }

    func testSendConnectionRequestIsRejectedWhenRequesterHasBlockedRecipient() {
        // A user who has blocked someone cannot reach out to them either.
        let (profiles, messaging) = reposWithUsers("alice", "bob")
        profiles.blockUser(blockerId: "alice", blockedId: "bob")

        XCTAssertNil(messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob"))
    }

    func testSendMessageIsRejectedWhenRecipientHasBlockedSender() {
        // AC#7 / P5: even an accepted connection does not override a block.
        let (profiles, messaging) = reposWithUsers("alice", "bob")
        let connection = messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")!
        messaging.acceptConnectionRequest(connectionId: connection.id, acceptorId: "bob")
        // Bob blocks Alice after the connection is established.
        profiles.blockUser(blockerId: "bob", blockedId: "alice")

        XCTAssertNil(messaging.sendMessage(senderId: "alice", recipientId: "bob", body: "Hello"))
    }

    // MARK: - Message body validation

    func testSendMessageWithBlankBodyReturnsNil() {
        let (_, messaging) = reposWithUsers("alice", "bob")
        let connection = messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")!
        messaging.acceptConnectionRequest(connectionId: connection.id, acceptorId: "bob")

        XCTAssertNil(messaging.sendMessage(senderId: "alice", recipientId: "bob", body: "   "))
    }

    func testSendMessageWithBodyAtMaximumLengthIsAccepted() {
        let (_, messaging) = reposWithUsers("alice", "bob")
        let connection = messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")!
        messaging.acceptConnectionRequest(connectionId: connection.id, acceptorId: "bob")
        let maxBody = String(repeating: "a", count: MessagingRepository.maxMessageLength)

        XCTAssertNotNil(messaging.sendMessage(senderId: "alice", recipientId: "bob", body: maxBody))
    }

    func testSendMessageWithBodyOneCharacterOverMaximumLengthReturnsNil() {
        let (_, messaging) = reposWithUsers("alice", "bob")
        let connection = messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")!
        messaging.acceptConnectionRequest(connectionId: connection.id, acceptorId: "bob")
        let tooLong = String(repeating: "a", count: MessagingRepository.maxMessageLength + 1)

        XCTAssertNil(messaging.sendMessage(senderId: "alice", recipientId: "bob", body: tooLong))
    }

    // MARK: - getMessages

    func testGetMessagesReturnsEmptyArrayBeforeAnyMessagesAreSent() {
        let (_, messaging) = reposWithUsers("alice", "bob")
        let connection = messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")!
        messaging.acceptConnectionRequest(connectionId: connection.id, acceptorId: "bob")

        XCTAssertTrue(messaging.getMessages(userId1: "alice", userId2: "bob").isEmpty)
    }

    func testGetMessagesReturnsAllMessagesBetweenTwoUsersInChronologicalOrder() {
        let (_, messaging) = reposWithUsers("alice", "bob")
        let connection = messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")!
        messaging.acceptConnectionRequest(connectionId: connection.id, acceptorId: "bob")
        messaging.sendMessage(senderId: "alice", recipientId: "bob", body: "Hello")
        messaging.sendMessage(senderId: "bob", recipientId: "alice", body: "Hi")

        let messages = messaging.getMessages(userId1: "alice", userId2: "bob")

        XCTAssertEqual(messages.count, 2)
        XCTAssertEqual(messages[0].body, "Hello")
        XCTAssertEqual(messages[1].body, "Hi")
    }

    func testGetMessagesIsSymmetricSwappingArgumentOrderReturnsSameList() {
        let (_, messaging) = reposWithUsers("alice", "bob")
        let connection = messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")!
        messaging.acceptConnectionRequest(connectionId: connection.id, acceptorId: "bob")
        messaging.sendMessage(senderId: "alice", recipientId: "bob", body: "Hello")

        let ab = messaging.getMessages(userId1: "alice", userId2: "bob")
        let ba = messaging.getMessages(userId1: "bob", userId2: "alice")

        XCTAssertEqual(ab, ba)
    }

    func testGetMessagesDoesNotIncludeMessagesFromADifferentPair() {
        let (_, messaging) = reposWithUsers("alice", "bob", "carol")
        let ab = messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")!
        messaging.acceptConnectionRequest(connectionId: ab.id, acceptorId: "bob")
        let ac = messaging.sendConnectionRequest(requesterId: "alice", recipientId: "carol")!
        messaging.acceptConnectionRequest(connectionId: ac.id, acceptorId: "carol")

        messaging.sendMessage(senderId: "alice", recipientId: "bob", body: "Hello Bob")
        messaging.sendMessage(senderId: "alice", recipientId: "carol", body: "Hello Carol")

        let abMessages = messaging.getMessages(userId1: "alice", userId2: "bob")
        XCTAssertEqual(abMessages.count, 1)
        XCTAssertEqual(abMessages[0].body, "Hello Bob")

        let acMessages = messaging.getMessages(userId1: "alice", userId2: "carol")
        XCTAssertEqual(acMessages.count, 1)
        XCTAssertEqual(acMessages[0].body, "Hello Carol")
    }

    // MARK: - AC#5: connection request rate limiting

    func testSendConnectionRequestSucceedsForEachRequestUpToTheDailyLimit() {
        // AC#5: exactly maxConnectionRequestsPerDay new requests must succeed.
        let profileRepo = ProfileRepository()
        try! profileRepo.save(Profile(id: "alice", displayName: "Alice", photo: validPhoto()))
        for i in 1...MessagingRepository.maxConnectionRequestsPerDay {
            try! profileRepo.save(Profile(id: "user-\(i)", displayName: "User \(i)", photo: validPhoto()))
        }
        let messaging = MessagingRepository(profileRepository: profileRepo)

        for i in 1...MessagingRepository.maxConnectionRequestsPerDay {
            XCTAssertNotNil(
                messaging.sendConnectionRequest(requesterId: "alice", recipientId: "user-\(i)"),
                "request \(i) should succeed"
            )
        }
    }

    func testSendConnectionRequestIsRejectedOnceDailyLimitIsReached() {
        // AC#5: the request immediately after the limit is returned as nil.
        let profileRepo = ProfileRepository()
        try! profileRepo.save(Profile(id: "alice", displayName: "Alice", photo: validPhoto()))
        for i in 1...(MessagingRepository.maxConnectionRequestsPerDay + 1) {
            try! profileRepo.save(Profile(id: "user-\(i)", displayName: "User \(i)", photo: validPhoto()))
        }
        let messaging = MessagingRepository(profileRepository: profileRepo)

        // Exhaust the daily limit.
        for i in 1...MessagingRepository.maxConnectionRequestsPerDay {
            messaging.sendConnectionRequest(requesterId: "alice", recipientId: "user-\(i)")
        }

        // The next new request exceeds the limit and is rejected.
        XCTAssertNil(
            messaging.sendConnectionRequest(
                requesterId: "alice",
                recipientId: "user-\(MessagingRepository.maxConnectionRequestsPerDay + 1)"
            )
        )
    }

    func testConnectionRequestLimitsArePerRequesterAndDoNotAffectOtherRequesters() {
        // AC#5: each requester has an independent counter; exhausting alice's
        // limit does not prevent bob from sending requests.
        let profileRepo = ProfileRepository()
        try! profileRepo.save(Profile(id: "alice", displayName: "Alice", photo: validPhoto()))
        try! profileRepo.save(Profile(id: "bob", displayName: "Bob", photo: validPhoto()))
        for i in 1...(MessagingRepository.maxConnectionRequestsPerDay + 1) {
            try! profileRepo.save(Profile(id: "user-\(i)", displayName: "User \(i)", photo: validPhoto()))
        }
        let messaging = MessagingRepository(profileRepository: profileRepo)

        // Alice exhausts her daily limit.
        for i in 1...MessagingRepository.maxConnectionRequestsPerDay {
            messaging.sendConnectionRequest(requesterId: "alice", recipientId: "user-\(i)")
        }

        // Bob is not affected — his limit is separate.
        XCTAssertNotNil(
            messaging.sendConnectionRequest(
                requesterId: "bob",
                recipientId: "user-\(MessagingRepository.maxConnectionRequestsPerDay + 1)"
            )
        )
    }

    // MARK: - C14: sendConnectionRequestResult — typed refusal reasons

    func testSendConnectionRequestResultReturnsAllowedWithConnectionOnSuccess() {
        let (_, messaging) = reposWithUsers("alice", "bob")

        let result = messaging.sendConnectionRequestResult(requesterId: "alice", recipientId: "bob")

        guard case .allowed(let connection) = result else {
            return XCTFail("Expected .allowed, got \(result)")
        }
        XCTAssertEqual(connection.status, .pending)
        XCTAssertEqual(connection.requesterId, "alice")
        XCTAssertEqual(connection.recipientId, "bob")
    }

    func testSendConnectionRequestResultReturnsBlankIdWhenRequesterIdIsBlank() {
        let (_, messaging) = reposWithUsers("alice")

        let result = messaging.sendConnectionRequestResult(requesterId: " ", recipientId: "alice")

        guard case .refused(let reason) = result else {
            return XCTFail("Expected .refused, got \(result)")
        }
        XCTAssertEqual(reason, .blankId)
    }

    func testSendConnectionRequestResultReturnsBlankIdWhenRecipientIdIsEmpty() {
        let (_, messaging) = reposWithUsers("alice")

        let result = messaging.sendConnectionRequestResult(requesterId: "alice", recipientId: "")

        guard case .refused(let reason) = result else {
            return XCTFail("Expected .refused, got \(result)")
        }
        XCTAssertEqual(reason, .blankId)
    }

    func testSendConnectionRequestResultReturnsSelfRequestWhenIdsAreEqual() {
        let (_, messaging) = reposWithUsers("alice")

        let result = messaging.sendConnectionRequestResult(requesterId: "alice", recipientId: "alice")

        guard case .refused(let reason) = result else {
            return XCTFail("Expected .refused, got \(result)")
        }
        XCTAssertEqual(reason, .selfRequest)
    }

    func testSendConnectionRequestResultReturnsBlockedWhenRecipientBlockedRequester() {
        let (profiles, messaging) = reposWithUsers("alice", "bob")
        profiles.blockUser(blockerId: "bob", blockedId: "alice")

        let result = messaging.sendConnectionRequestResult(requesterId: "alice", recipientId: "bob")

        guard case .refused(let reason) = result else {
            return XCTFail("Expected .refused, got \(result)")
        }
        XCTAssertEqual(reason, .blocked)
    }

    func testSendConnectionRequestResultReturnsBlockedWhenRequesterBlockedRecipient() {
        let (profiles, messaging) = reposWithUsers("alice", "bob")
        profiles.blockUser(blockerId: "alice", blockedId: "bob")

        let result = messaging.sendConnectionRequestResult(requesterId: "alice", recipientId: "bob")

        guard case .refused(let reason) = result else {
            return XCTFail("Expected .refused, got \(result)")
        }
        XCTAssertEqual(reason, .blocked)
    }

    func testSendConnectionRequestResultReturnsAlreadyExistsOnDuplicateRequest() {
        let (_, messaging) = reposWithUsers("alice", "bob")
        messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")

        let result = messaging.sendConnectionRequestResult(requesterId: "alice", recipientId: "bob")

        guard case .refused(let reason) = result else {
            return XCTFail("Expected .refused, got \(result)")
        }
        XCTAssertEqual(reason, .alreadyExists)
    }

    func testSendConnectionRequestResultReturnsRateLimitExceededAfterDailyLimit() {
        let profileRepo = ProfileRepository()
        try! profileRepo.save(Profile(id: "alice", displayName: "Alice", photo: validPhoto()))
        for i in 1...(MessagingRepository.maxConnectionRequestsPerDay + 1) {
            try! profileRepo.save(Profile(id: "user-\(i)", displayName: "User \(i)", photo: validPhoto()))
        }
        let messaging = MessagingRepository(profileRepository: profileRepo)
        for i in 1...MessagingRepository.maxConnectionRequestsPerDay {
            messaging.sendConnectionRequest(requesterId: "alice", recipientId: "user-\(i)")
        }

        let result = messaging.sendConnectionRequestResult(
            requesterId: "alice",
            recipientId: "user-\(MessagingRepository.maxConnectionRequestsPerDay + 1)"
        )

        guard case .refused(let reason) = result else {
            return XCTFail("Expected .refused, got \(result)")
        }
        XCTAssertEqual(reason, .rateLimitExceeded)
    }

    // MARK: - C14: sendMessageResult — typed refusal reasons

    func testSendMessageResultReturnsAllowedWithMessageOnSuccess() {
        let (_, messaging) = reposWithUsers("alice", "bob")
        let connection = messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")!
        messaging.acceptConnectionRequest(connectionId: connection.id, acceptorId: "bob")

        let result = messaging.sendMessageResult(senderId: "alice", recipientId: "bob", body: "Hello")

        guard case .allowed(let message) = result else {
            return XCTFail("Expected .allowed, got \(result)")
        }
        XCTAssertEqual(message.senderId, "alice")
        XCTAssertEqual(message.recipientId, "bob")
        XCTAssertEqual(message.body, "Hello")
    }

    func testSendMessageResultReturnsNotConnectedWhenNoConnectionExists() {
        let (_, messaging) = reposWithUsers("alice", "bob")

        let result = messaging.sendMessageResult(senderId: "alice", recipientId: "bob", body: "Hello")

        guard case .refused(let reason) = result else {
            return XCTFail("Expected .refused, got \(result)")
        }
        XCTAssertEqual(reason, .notConnected)
    }

    func testSendMessageResultReturnsNotConnectedWhenConnectionIsPending() {
        let (_, messaging) = reposWithUsers("alice", "bob")
        messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")

        let result = messaging.sendMessageResult(senderId: "alice", recipientId: "bob", body: "Hello")

        guard case .refused(let reason) = result else {
            return XCTFail("Expected .refused, got \(result)")
        }
        XCTAssertEqual(reason, .notConnected)
    }

    func testSendMessageResultReturnsBlockedWhenRecipientHasBlockedSender() {
        let (profiles, messaging) = reposWithUsers("alice", "bob")
        let connection = messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")!
        messaging.acceptConnectionRequest(connectionId: connection.id, acceptorId: "bob")
        profiles.blockUser(blockerId: "bob", blockedId: "alice")

        let result = messaging.sendMessageResult(senderId: "alice", recipientId: "bob", body: "Hello")

        guard case .refused(let reason) = result else {
            return XCTFail("Expected .refused, got \(result)")
        }
        XCTAssertEqual(reason, .blocked)
    }

    func testSendMessageResultReturnsBlankBodyWhenBodyIsBlank() {
        let (_, messaging) = reposWithUsers("alice", "bob")
        let connection = messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")!
        messaging.acceptConnectionRequest(connectionId: connection.id, acceptorId: "bob")

        let result = messaging.sendMessageResult(senderId: "alice", recipientId: "bob", body: "   ")

        guard case .refused(let reason) = result else {
            return XCTFail("Expected .refused, got \(result)")
        }
        XCTAssertEqual(reason, .blankBody)
    }

    func testSendMessageResultReturnsBodyTooLongWhenBodyExceedsLimit() {
        let (_, messaging) = reposWithUsers("alice", "bob")
        let connection = messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")!
        messaging.acceptConnectionRequest(connectionId: connection.id, acceptorId: "bob")
        let tooLong = String(repeating: "a", count: MessagingRepository.maxMessageLength + 1)

        let result = messaging.sendMessageResult(senderId: "alice", recipientId: "bob", body: tooLong)

        guard case .refused(let reason) = result else {
            return XCTFail("Expected .refused, got \(result)")
        }
        XCTAssertEqual(reason, .bodyTooLong)
    }

    func testSendMessageResultReturnsAllowedForBodyAtMaximumLength() {
        let (_, messaging) = reposWithUsers("alice", "bob")
        let connection = messaging.sendConnectionRequest(requesterId: "alice", recipientId: "bob")!
        messaging.acceptConnectionRequest(connectionId: connection.id, acceptorId: "bob")
        let maxBody = String(repeating: "a", count: MessagingRepository.maxMessageLength)

        let result = messaging.sendMessageResult(senderId: "alice", recipientId: "bob", body: maxBody)

        if case .refused = result {
            XCTFail("Expected .allowed for body at max length, got .refused")
        }
    }
}
