/// Domain-layer offline snapshot store.
///
/// AC#9: the app must work with no network connection to the extent of
/// showing the person's own profile and their existing accepted connections
/// and previously loaded messages. This class is the domain-level record of
/// those three snapshots; persistence to disk is a platform concern outside
/// the scope of this module.
///
/// P1 (constitution, enforceable): the only data stored here is the most
/// recently cached copy of the user's own profile, their accepted
/// connections, and their previously loaded messages. All three are kept for
/// as long as the local cache exists and are removed in full when
/// `clearForUser(_:)` is called — which the calling layer must do on account
/// deletion to satisfy P2.
///
/// P2 (constitution, enforceable): `clearForUser(_:)` is the in-process
/// deletion path for cached offline data, shipped in the same phase rather
/// than deferred.
///
/// P9 (constitution): the same logic exists verbatim in the Kotlin lane
/// (OfflineCache.kt) so that both platforms share one set of rules.
public final class OfflineCache {

    // Profile snapshot keyed by user id.
    private var profileSnapshots: [String: Profile] = [:]

    // Accepted-connection snapshots keyed by user id.
    private var connectionSnapshots: [String: [Connection]] = [:]

    // Message snapshots keyed by a canonical pair key.
    private var messageSnapshots: [String: [Message]] = [:]

    public init() {}

    // MARK: - Profile

    /// Stores `profile` as the offline snapshot for `profile.id`, replacing
    /// any previously cached snapshot for that id.
    ///
    /// Returns `false` and stores nothing when `profile.id` is blank or
    /// whitespace-only.
    @discardableResult
    public func cacheProfile(_ profile: Profile) -> Bool {
        guard !profile.id.trimmingCharacters(in: .whitespaces).isEmpty else { return false }
        profileSnapshots[profile.id] = profile
        return true
    }

    /// Returns the most recently cached profile snapshot for `userId`, or
    /// `nil` when no snapshot has been stored for that id.
    public func getCachedProfile(userId: String) -> Profile? {
        return profileSnapshots[userId]
    }

    // MARK: - Connections

    /// Stores `connections` as the accepted-connection snapshot for `userId`,
    /// replacing any previously cached snapshot for that id.
    ///
    /// Only `.accepted` connections are stored; pending connections are
    /// dropped because they carry no message history and are not shown in
    /// the offline view (AC#9).
    ///
    /// Returns `false` and stores nothing when `userId` is blank or
    /// whitespace-only.
    @discardableResult
    public func cacheConnections(userId: String, connections: [Connection]) -> Bool {
        guard !userId.trimmingCharacters(in: .whitespaces).isEmpty else { return false }
        connectionSnapshots[userId] = connections.filter { $0.status == .accepted }
        return true
    }

    /// Returns the cached accepted-connection list for `userId`, or an empty
    /// array when no snapshot has been stored for that id.
    public func getCachedConnections(userId: String) -> [Connection] {
        return connectionSnapshots[userId] ?? []
    }

    // MARK: - Messages

    /// Stores `messages` as the snapshot for the conversation between
    /// `userId` and `peerId`, replacing any previously cached snapshot.
    ///
    /// Returns `false` and stores nothing when `userId` or `peerId` is blank
    /// or whitespace-only.
    @discardableResult
    public func cacheMessages(userId: String, peerId: String, messages: [Message]) -> Bool {
        guard !userId.trimmingCharacters(in: .whitespaces).isEmpty,
              !peerId.trimmingCharacters(in: .whitespaces).isEmpty else { return false }
        messageSnapshots[pairKey(userId, peerId)] = messages
        return true
    }

    /// Returns the cached message list for the conversation between `userId`
    /// and `peerId`, or an empty array when no snapshot has been stored for
    /// that pair.
    ///
    /// The lookup is symmetric: `getCachedMessages(userId:peerId:)` returns
    /// the same list regardless of argument order.
    public func getCachedMessages(userId: String, peerId: String) -> [Message] {
        return messageSnapshots[pairKey(userId, peerId)] ?? []
    }

    // MARK: - Account deletion

    /// Removes all cached data for `userId`: their profile snapshot, their
    /// connection snapshot, and every message snapshot in which `userId`
    /// appears as a participant.
    ///
    /// Called on account deletion to satisfy constitution P2 (account
    /// deletion is a feature that ships in the same phase as the feature that
    /// creates the data).
    public func clearForUser(_ userId: String) {
        profileSnapshots.removeValue(forKey: userId)
        connectionSnapshots.removeValue(forKey: userId)
        let keysToRemove = messageSnapshots.keys.filter { key in
            key.hasPrefix("\(userId)|") || key.hasSuffix("|\(userId)")
        }
        for key in keysToRemove {
            messageSnapshots.removeValue(forKey: key)
        }
    }

    // MARK: - Private helpers

    /// Returns a canonical key for the (a, b) pair that is the same
    /// whichever order the arguments are supplied.
    ///
    /// Both ids are sorted lexicographically so that
    /// `pairKey("a", "b") == pairKey("b", "a")`.
    private func pairKey(_ a: String, _ b: String) -> String {
        let (first, second) = a <= b ? (a, b) : (b, a)
        return "\(first)|\(second)"
    }
}
