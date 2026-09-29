import XCTest
@testable import MyFriendsCore

/// Tests for `OfflineCache` — AC#9: the app shows the person's own profile and
/// their existing accepted connections and previously loaded messages when there
/// is no network connection.
final class OfflineCacheTests: XCTestCase {

    private func validProfile(id: String = "alice") -> Profile {
        return Profile(id: id, displayName: "Alice")
    }

    private func acceptedConnection(id: String, requesterId: String, recipientId: String) -> Connection {
        return Connection(id: id, requesterId: requesterId, recipientId: recipientId, status: .accepted)
    }

    private func pendingConnection(id: String, requesterId: String, recipientId: String) -> Connection {
        return Connection(id: id, requesterId: requesterId, recipientId: recipientId, status: .pending)
    }

    private func message(id: String, from senderId: String, to recipientId: String, body: String = "hello") -> Message {
        return Message(id: id, senderId: senderId, recipientId: recipientId, body: body)
    }

    // MARK: - cacheProfile

    func testCacheProfileStoresAProfileAndGetCachedProfileReturnsIt() {
        let cache = OfflineCache()
        let profile = validProfile()

        XCTAssertTrue(cache.cacheProfile(profile))
        XCTAssertEqual(cache.getCachedProfile(userId: "alice")?.id, "alice")
        XCTAssertEqual(cache.getCachedProfile(userId: "alice")?.displayName, "Alice")
    }

    func testGetCachedProfileReturnsNilWhenNoSnapshotIsStored() {
        let cache = OfflineCache()

        XCTAssertNil(cache.getCachedProfile(userId: "alice"))
    }

    func testCacheProfileReplacesAnExistingSnapshotForTheSameId() {
        let cache = OfflineCache()
        let first = Profile(id: "alice", displayName: "Alice")
        let second = Profile(id: "alice", displayName: "Alice Updated")

        cache.cacheProfile(first)
        cache.cacheProfile(second)

        XCTAssertEqual(cache.getCachedProfile(userId: "alice")?.displayName, "Alice Updated")
    }

    func testCacheProfileWithABlankIdReturnsFalseAndStoresNothing() {
        let cache = OfflineCache()
        let profile = Profile(id: "   ", displayName: "Blank")

        XCTAssertFalse(cache.cacheProfile(profile))
        XCTAssertNil(cache.getCachedProfile(userId: "   "))
    }

    // MARK: - cacheConnections

    func testCacheConnectionsStoresAcceptedConnectionsAndGetCachedConnectionsReturnsThem() {
        let cache = OfflineCache()
        let conn = acceptedConnection(id: "c1", requesterId: "alice", recipientId: "bob")

        XCTAssertTrue(cache.cacheConnections(userId: "alice", connections: [conn]))

        let stored = cache.getCachedConnections(userId: "alice")
        XCTAssertEqual(stored.count, 1)
        XCTAssertEqual(stored.first?.id, "c1")
    }

    func testGetCachedConnectionsReturnsAnEmptyArrayWhenNoSnapshotIsStored() {
        let cache = OfflineCache()

        XCTAssertTrue(cache.getCachedConnections(userId: "alice").isEmpty)
    }

    func testCacheConnectionsDropsPendingConnectionsAC9OfflineShowsOnlyAccepted() {
        let cache = OfflineCache()
        let accepted = acceptedConnection(id: "c1", requesterId: "alice", recipientId: "bob")
        let pending = pendingConnection(id: "c2", requesterId: "alice", recipientId: "carol")

        cache.cacheConnections(userId: "alice", connections: [accepted, pending])

        let stored = cache.getCachedConnections(userId: "alice")
        XCTAssertEqual(stored.count, 1)
        XCTAssertEqual(stored.first?.id, "c1")
    }

    func testCacheConnectionsWithABlankUserIdReturnsFalseAndStoresNothing() {
        let cache = OfflineCache()

        XCTAssertFalse(
            cache.cacheConnections(
                userId: "  ",
                connections: [acceptedConnection(id: "c1", requesterId: "alice", recipientId: "bob")]
            )
        )
        XCTAssertTrue(cache.getCachedConnections(userId: "  ").isEmpty)
    }

    func testCacheConnectionsReplacesAnExistingSnapshotForTheSameUserId() {
        let cache = OfflineCache()
        let first = [acceptedConnection(id: "c1", requesterId: "alice", recipientId: "bob")]
        let second = [acceptedConnection(id: "c2", requesterId: "alice", recipientId: "carol")]

        cache.cacheConnections(userId: "alice", connections: first)
        cache.cacheConnections(userId: "alice", connections: second)

        let stored = cache.getCachedConnections(userId: "alice")
        XCTAssertEqual(stored.count, 1)
        XCTAssertEqual(stored.first?.id, "c2")
    }

    // MARK: - cacheMessages

    func testCacheMessagesStoresMessagesAndGetCachedMessagesReturnsThem() {
        let cache = OfflineCache()
        let msgs = [message(id: "m1", from: "alice", to: "bob")]

        XCTAssertTrue(cache.cacheMessages(userId: "alice", peerId: "bob", messages: msgs))

        XCTAssertEqual(cache.getCachedMessages(userId: "alice", peerId: "bob").count, 1)
    }

    func testGetCachedMessagesReturnsAnEmptyArrayWhenNoSnapshotIsStoredForThatPair() {
        let cache = OfflineCache()

        XCTAssertTrue(cache.getCachedMessages(userId: "alice", peerId: "bob").isEmpty)
    }

    func testGetCachedMessagesIsSymmetricSwappingUserIdAndPeerIdReturnsTheSameList() {
        let cache = OfflineCache()
        let msgs = [
            message(id: "m1", from: "alice", to: "bob"),
            message(id: "m2", from: "bob", to: "alice"),
        ]

        cache.cacheMessages(userId: "alice", peerId: "bob", messages: msgs)

        XCTAssertEqual(cache.getCachedMessages(userId: "bob", peerId: "alice").count, 2)
    }

    func testCacheMessagesWithABlankUserIdReturnsFalseAndStoresNothing() {
        let cache = OfflineCache()

        XCTAssertFalse(
            cache.cacheMessages(
                userId: "  ",
                peerId: "bob",
                messages: [message(id: "m1", from: "alice", to: "bob")]
            )
        )
        XCTAssertTrue(cache.getCachedMessages(userId: "  ", peerId: "bob").isEmpty)
    }

    func testCacheMessagesWithABlankPeerIdReturnsFalseAndStoresNothing() {
        let cache = OfflineCache()

        XCTAssertFalse(
            cache.cacheMessages(
                userId: "alice",
                peerId: "  ",
                messages: [message(id: "m1", from: "alice", to: "bob")]
            )
        )
        XCTAssertTrue(cache.getCachedMessages(userId: "alice", peerId: "  ").isEmpty)
    }

    func testCacheMessagesReplacesAnExistingSnapshotForTheSamePair() {
        let cache = OfflineCache()
        let first = [message(id: "m1", from: "alice", to: "bob")]
        let second = [
            message(id: "m2", from: "alice", to: "bob"),
            message(id: "m3", from: "bob", to: "alice"),
        ]

        cache.cacheMessages(userId: "alice", peerId: "bob", messages: first)
        cache.cacheMessages(userId: "alice", peerId: "bob", messages: second)

        XCTAssertEqual(cache.getCachedMessages(userId: "alice", peerId: "bob").count, 2)
    }

    // MARK: - clearForUser

    func testClearForUserRemovesTheCachedProfileForThatUser() {
        let cache = OfflineCache()
        cache.cacheProfile(validProfile())

        cache.clearForUser("alice")

        XCTAssertNil(cache.getCachedProfile(userId: "alice"))
    }

    func testClearForUserRemovesTheCachedConnectionsForThatUser() {
        let cache = OfflineCache()
        cache.cacheConnections(
            userId: "alice",
            connections: [acceptedConnection(id: "c1", requesterId: "alice", recipientId: "bob")]
        )

        cache.clearForUser("alice")

        XCTAssertTrue(cache.getCachedConnections(userId: "alice").isEmpty)
    }

    func testClearForUserRemovesCachedMessagesWhereTheUserIsAParticipant() {
        let cache = OfflineCache()
        cache.cacheMessages(
            userId: "alice",
            peerId: "bob",
            messages: [message(id: "m1", from: "alice", to: "bob")]
        )

        cache.clearForUser("alice")

        XCTAssertTrue(cache.getCachedMessages(userId: "alice", peerId: "bob").isEmpty)
    }

    func testClearForUserDoesNotRemoveDataForOtherUsers() {
        let cache = OfflineCache()
        cache.cacheProfile(validProfile(id: "alice"))
        cache.cacheProfile(validProfile(id: "carol"))
        cache.cacheConnections(
            userId: "carol",
            connections: [acceptedConnection(id: "c2", requesterId: "carol", recipientId: "dave")]
        )
        cache.cacheMessages(
            userId: "carol",
            peerId: "dave",
            messages: [message(id: "m2", from: "carol", to: "dave")]
        )

        cache.clearForUser("alice")

        XCTAssertNotNil(cache.getCachedProfile(userId: "carol"))
        XCTAssertEqual(cache.getCachedConnections(userId: "carol").count, 1)
        XCTAssertEqual(cache.getCachedMessages(userId: "carol", peerId: "dave").count, 1)
    }
}
