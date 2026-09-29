import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Tests for [OfflineCache] — AC#9: the app shows the person's own profile and
 * their existing accepted connections and previously loaded messages when there
 * is no network connection.
 */
class OfflineCacheTest {

    private fun validProfile(id: String = "alice") = Profile(
        id = id,
        displayName = "Alice",
    )

    private fun acceptedConnection(id: String, requesterId: String, recipientId: String) =
        Connection(
            id = id,
            requesterId = requesterId,
            recipientId = recipientId,
            status = ConnectionStatus.ACCEPTED,
        )

    private fun pendingConnection(id: String, requesterId: String, recipientId: String) =
        Connection(
            id = id,
            requesterId = requesterId,
            recipientId = recipientId,
            status = ConnectionStatus.PENDING,
        )

    private fun message(id: String, from: String, to: String, body: String = "hello") =
        Message(id = id, senderId = from, recipientId = to, body = body)

    // ── cacheProfile ──────────────────────────────────────────────────────

    @Test
    fun `cacheProfile stores a profile and getCachedProfile returns it`() {
        val cache = OfflineCache()
        val profile = validProfile("alice")

        assertTrue(cache.cacheProfile(profile))

        assertEquals(profile, cache.getCachedProfile("alice"))
    }

    @Test
    fun `getCachedProfile returns null when no snapshot is stored for that id`() {
        val cache = OfflineCache()

        assertNull(cache.getCachedProfile("alice"))
    }

    @Test
    fun `cacheProfile replaces an existing snapshot for the same id`() {
        val cache = OfflineCache()
        val first = Profile(id = "alice", displayName = "Alice")
        val second = Profile(id = "alice", displayName = "Alice Updated")

        cache.cacheProfile(first)
        cache.cacheProfile(second)

        assertEquals("Alice Updated", cache.getCachedProfile("alice")?.displayName)
    }

    @Test
    fun `cacheProfile with a blank id returns false and stores nothing`() {
        val cache = OfflineCache()
        val profile = Profile(id = "   ", displayName = "Blank")

        assertFalse(cache.cacheProfile(profile))
        assertNull(cache.getCachedProfile("   "))
    }

    // ── cacheConnections ──────────────────────────────────────────────────

    @Test
    fun `cacheConnections stores accepted connections and getCachedConnections returns them`() {
        val cache = OfflineCache()
        val conn = acceptedConnection("c1", "alice", "bob")

        assertTrue(cache.cacheConnections("alice", listOf(conn)))

        assertEquals(listOf(conn), cache.getCachedConnections("alice"))
    }

    @Test
    fun `getCachedConnections returns an empty list when no snapshot is stored`() {
        val cache = OfflineCache()

        assertTrue(cache.getCachedConnections("alice").isEmpty())
    }

    @Test
    fun `cacheConnections drops pending connections — AC9 offline shows only accepted`() {
        val cache = OfflineCache()
        val accepted = acceptedConnection("c1", "alice", "bob")
        val pending = pendingConnection("c2", "alice", "carol")

        cache.cacheConnections("alice", listOf(accepted, pending))

        val stored = cache.getCachedConnections("alice")
        assertEquals(1, stored.size)
        assertEquals("c1", stored[0].id)
    }

    @Test
    fun `cacheConnections with a blank userId returns false and stores nothing`() {
        val cache = OfflineCache()

        assertFalse(
            cache.cacheConnections("  ", listOf(acceptedConnection("c1", "alice", "bob")))
        )
        assertTrue(cache.getCachedConnections("  ").isEmpty())
    }

    @Test
    fun `cacheConnections replaces an existing snapshot for the same userId`() {
        val cache = OfflineCache()
        val first = listOf(acceptedConnection("c1", "alice", "bob"))
        val second = listOf(acceptedConnection("c2", "alice", "carol"))

        cache.cacheConnections("alice", first)
        cache.cacheConnections("alice", second)

        val stored = cache.getCachedConnections("alice")
        assertEquals(1, stored.size)
        assertEquals("c2", stored[0].id)
    }

    // ── cacheMessages ─────────────────────────────────────────────────────

    @Test
    fun `cacheMessages stores messages and getCachedMessages returns them`() {
        val cache = OfflineCache()
        val msgs = listOf(message("m1", "alice", "bob"))

        assertTrue(cache.cacheMessages("alice", "bob", msgs))

        assertEquals(msgs, cache.getCachedMessages("alice", "bob"))
    }

    @Test
    fun `getCachedMessages returns an empty list when no snapshot is stored for that pair`() {
        val cache = OfflineCache()

        assertTrue(cache.getCachedMessages("alice", "bob").isEmpty())
    }

    @Test
    fun `getCachedMessages is symmetric — swapping userId and peerId returns the same list`() {
        val cache = OfflineCache()
        val msgs = listOf(message("m1", "alice", "bob"), message("m2", "bob", "alice"))

        cache.cacheMessages("alice", "bob", msgs)

        assertEquals(msgs, cache.getCachedMessages("bob", "alice"))
    }

    @Test
    fun `cacheMessages with a blank userId returns false and stores nothing`() {
        val cache = OfflineCache()

        assertFalse(
            cache.cacheMessages("  ", "bob", listOf(message("m1", "alice", "bob")))
        )
        assertTrue(cache.getCachedMessages("  ", "bob").isEmpty())
    }

    @Test
    fun `cacheMessages with a blank peerId returns false and stores nothing`() {
        val cache = OfflineCache()

        assertFalse(
            cache.cacheMessages("alice", "  ", listOf(message("m1", "alice", "bob")))
        )
        assertTrue(cache.getCachedMessages("alice", "  ").isEmpty())
    }

    @Test
    fun `cacheMessages replaces an existing snapshot for the same pair`() {
        val cache = OfflineCache()
        val first = listOf(message("m1", "alice", "bob"))
        val second = listOf(message("m2", "alice", "bob"), message("m3", "bob", "alice"))

        cache.cacheMessages("alice", "bob", first)
        cache.cacheMessages("alice", "bob", second)

        assertEquals(2, cache.getCachedMessages("alice", "bob").size)
    }

    // ── clearForUser ──────────────────────────────────────────────────────

    @Test
    fun `clearForUser removes the cached profile for that user`() {
        val cache = OfflineCache()
        cache.cacheProfile(validProfile("alice"))

        cache.clearForUser("alice")

        assertNull(cache.getCachedProfile("alice"))
    }

    @Test
    fun `clearForUser removes the cached connections for that user`() {
        val cache = OfflineCache()
        cache.cacheConnections("alice", listOf(acceptedConnection("c1", "alice", "bob")))

        cache.clearForUser("alice")

        assertTrue(cache.getCachedConnections("alice").isEmpty())
    }

    @Test
    fun `clearForUser removes cached messages where the user is a participant`() {
        val cache = OfflineCache()
        cache.cacheMessages("alice", "bob", listOf(message("m1", "alice", "bob")))

        cache.clearForUser("alice")

        assertTrue(cache.getCachedMessages("alice", "bob").isEmpty())
    }

    @Test
    fun `clearForUser does not remove data for other users`() {
        val cache = OfflineCache()
        cache.cacheProfile(validProfile("alice"))
        cache.cacheProfile(validProfile("carol"))
        cache.cacheConnections("carol", listOf(acceptedConnection("c2", "carol", "dave")))
        cache.cacheMessages("carol", "dave", listOf(message("m2", "carol", "dave")))

        cache.clearForUser("alice")

        assertNotNull(cache.getCachedProfile("carol"))
        assertEquals(1, cache.getCachedConnections("carol").size)
        assertEquals(1, cache.getCachedMessages("carol", "dave").size)
    }
}
