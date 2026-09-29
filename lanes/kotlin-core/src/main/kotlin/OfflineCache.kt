/**
 * Domain-layer offline snapshot store.
 *
 * AC#9: the app must work with no network connection to the extent of
 * showing the person's own profile and their existing accepted connections
 * and previously loaded messages. This class is the domain-level record of
 * those three snapshots; persistence to disk is a platform concern outside
 * the scope of this module.
 *
 * P1 (constitution, enforceable): the only data stored here is the most
 * recently cached copy of the user's own profile, their accepted connections,
 * and their previously loaded messages. All three are kept for as long as the
 * local cache exists and are removed in full when [clearForUser] is called —
 * which the calling layer must do on account deletion to satisfy P2.
 *
 * P2 (constitution, enforceable): [clearForUser] is the in-process deletion
 * path for cached offline data, shipped in the same phase rather than
 * deferred.
 *
 * P9 (constitution): the same logic exists verbatim in the Swift lane
 * (OfflineCache.swift) so that both platforms share one set of rules.
 */
class OfflineCache {

    // Profile snapshot keyed by user id.
    private val profileSnapshots: MutableMap<String, Profile> = mutableMapOf()

    // Accepted-connection snapshots keyed by user id.
    private val connectionSnapshots: MutableMap<String, List<Connection>> = mutableMapOf()

    // Message snapshots keyed by a canonical pair key.
    private val messageSnapshots: MutableMap<String, List<Message>> = mutableMapOf()

    // ── Profile ───────────────────────────────────────────────────────────

    /**
     * Stores [profile] as the offline snapshot for `profile.id`, replacing
     * any previously cached snapshot for that id.
     *
     * Returns `false` and stores nothing when [profile].id is blank or
     * whitespace-only.
     */
    fun cacheProfile(profile: Profile): Boolean {
        if (profile.id.isBlank()) return false
        profileSnapshots[profile.id] = profile
        return true
    }

    /**
     * Returns the most recently cached profile snapshot for [userId], or
     * `null` when no snapshot has been stored for that id.
     */
    fun getCachedProfile(userId: String): Profile? =
        profileSnapshots[userId]

    // ── Connections ───────────────────────────────────────────────────────

    /**
     * Stores [connections] as the accepted-connection snapshot for [userId],
     * replacing any previously cached snapshot for that id.
     *
     * Only [ConnectionStatus.ACCEPTED] connections are stored; pending
     * connections are dropped because they carry no message history and are
     * not shown in the offline view (AC#9).
     *
     * Returns `false` and stores nothing when [userId] is blank or
     * whitespace-only.
     */
    fun cacheConnections(userId: String, connections: List<Connection>): Boolean {
        if (userId.isBlank()) return false
        connectionSnapshots[userId] = connections.filter { it.status == ConnectionStatus.ACCEPTED }
        return true
    }

    /**
     * Returns the cached accepted-connection list for [userId], or an empty
     * list when no snapshot has been stored for that id.
     */
    fun getCachedConnections(userId: String): List<Connection> =
        connectionSnapshots[userId] ?: emptyList()

    // ── Messages ──────────────────────────────────────────────────────────

    /**
     * Stores [messages] as the snapshot for the conversation between [userId]
     * and [peerId], replacing any previously cached snapshot.
     *
     * Returns `false` and stores nothing when [userId] or [peerId] is blank
     * or whitespace-only.
     */
    fun cacheMessages(userId: String, peerId: String, messages: List<Message>): Boolean {
        if (userId.isBlank() || peerId.isBlank()) return false
        messageSnapshots[pairKey(userId, peerId)] = messages
        return true
    }

    /**
     * Returns the cached message list for the conversation between [userId]
     * and [peerId], or an empty list when no snapshot has been stored for
     * that pair.
     *
     * The lookup is symmetric: `getCachedMessages("a", "b")` and
     * `getCachedMessages("b", "a")` return the same list.
     */
    fun getCachedMessages(userId: String, peerId: String): List<Message> =
        messageSnapshots[pairKey(userId, peerId)] ?: emptyList()

    // ── Account deletion ──────────────────────────────────────────────────

    /**
     * Removes all cached data for [userId]: their profile snapshot, their
     * connection snapshot, and every message snapshot in which [userId]
     * appears as a participant.
     *
     * Called on account deletion to satisfy constitution P2 (account
     * deletion is a feature that ships in the same phase as the feature that
     * creates the data).
     */
    fun clearForUser(userId: String) {
        profileSnapshots.remove(userId)
        connectionSnapshots.remove(userId)
        val keysToRemove = messageSnapshots.keys
            .filter { key -> key.startsWith("$userId|") || key.endsWith("|$userId") }
        keysToRemove.forEach { key -> messageSnapshots.remove(key) }
    }

    // ── Private helpers ───────────────────────────────────────────────────

    /**
     * Returns a canonical key for the (a, b) pair that is the same
     * whichever order the arguments are supplied.
     *
     * Both ids are sorted lexicographically so that
     * `pairKey("a", "b") == pairKey("b", "a")`.
     */
    private fun pairKey(a: String, b: String): String {
        val (first, second) = if (a <= b) Pair(a, b) else Pair(b, a)
        return "$first|$second"
    }
}
