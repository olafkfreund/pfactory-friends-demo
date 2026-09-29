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
}
