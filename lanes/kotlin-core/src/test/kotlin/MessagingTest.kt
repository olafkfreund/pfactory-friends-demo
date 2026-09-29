import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class MessagingTest {

    // ── Helpers ──────────────────────────────────────────────────────────────

    private fun validPhoto(): ProfilePhoto = ProfilePhoto(bytes = byteArrayOf(1, 2, 3), format = "png")

    /**
     * Creates a [ProfileRepository] pre-populated with profiles whose ids are
     * [ids], then wraps it in a [MessagingRepository].
     */
    private fun repoWithUsers(vararg ids: String): Pair<ProfileRepository, MessagingRepository> {
        val profileRepo = ProfileRepository()
        for (id in ids) {
            profileRepo.save(Profile(id = id, displayName = "User $id", photo = validPhoto()))
        }
        return Pair(profileRepo, MessagingRepository(profileRepo))
    }

    // ── AC#6: connection-state gate on sendMessage ────────────────────────

    @Test
    fun `sendMessage without any connection returns null`() {
        val (_, messaging) = repoWithUsers("alice", "bob")

        assertNull(messaging.sendMessage(senderId = "alice", recipientId = "bob", body = "Hello"))
    }

    @Test
    fun `sendMessage with a pending connection returns null`() {
        // AC#6: a PENDING connection is not enough — the recipient must accept first.
        val (_, messaging) = repoWithUsers("alice", "bob")
        messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")

        assertNull(messaging.sendMessage(senderId = "alice", recipientId = "bob", body = "Hello"))
    }

    @Test
    fun `sendMessage after accepted connection returns the persisted message`() {
        val (_, messaging) = repoWithUsers("alice", "bob")
        val connection = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")!!
        messaging.acceptConnectionRequest(connectionId = connection.id, acceptorId = "bob")

        val message = messaging.sendMessage(senderId = "alice", recipientId = "bob", body = "Hello")

        assertNotNull(message)
        assertEquals("alice", message.senderId)
        assertEquals("bob", message.recipientId)
        assertEquals("Hello", message.body)
    }

    @Test
    fun `sendMessage works in both directions after acceptance`() {
        // AC#6: the connection is mutual — either party can initiate once connected.
        val (_, messaging) = repoWithUsers("alice", "bob")
        val connection = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")!!
        messaging.acceptConnectionRequest(connectionId = connection.id, acceptorId = "bob")

        assertNotNull(messaging.sendMessage(senderId = "alice", recipientId = "bob", body = "Hi Bob"))
        assertNotNull(messaging.sendMessage(senderId = "bob", recipientId = "alice", body = "Hi Alice"))
    }

    // ── areConnected ─────────────────────────────────────────────────────────

    @Test
    fun `areConnected returns false before any connection request`() {
        val (_, messaging) = repoWithUsers("alice", "bob")

        assertFalse(messaging.areConnected("alice", "bob"))
    }

    @Test
    fun `areConnected returns false when the connection is pending`() {
        val (_, messaging) = repoWithUsers("alice", "bob")
        messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")

        assertFalse(messaging.areConnected("alice", "bob"))
    }

    @Test
    fun `areConnected returns true after acceptance and the check is symmetric`() {
        val (_, messaging) = repoWithUsers("alice", "bob")
        val connection = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")!!
        messaging.acceptConnectionRequest(connectionId = connection.id, acceptorId = "bob")

        assertTrue(messaging.areConnected("alice", "bob"))
        // Symmetric: swapping the arguments gives the same result.
        assertTrue(messaging.areConnected("bob", "alice"))
    }

    // ── sendConnectionRequest ─────────────────────────────────────────────

    @Test
    fun `sendConnectionRequest creates a pending connection`() {
        val (_, messaging) = repoWithUsers("alice", "bob")

        val connection = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")

        assertNotNull(connection)
        assertEquals(ConnectionStatus.PENDING, connection.status)
        assertEquals("alice", connection.requesterId)
        assertEquals("bob", connection.recipientId)
    }

    @Test
    fun `sendConnectionRequest to self returns null`() {
        val (_, messaging) = repoWithUsers("alice")

        assertNull(messaging.sendConnectionRequest(requesterId = "alice", recipientId = "alice"))
    }

    @Test
    fun `sendConnectionRequest when a connection already exists returns null`() {
        // Duplicate and reverse-direction requests are both rejected.
        val (_, messaging) = repoWithUsers("alice", "bob")
        messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")

        assertNull(messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob"))
        assertNull(messaging.sendConnectionRequest(requesterId = "bob", recipientId = "alice"))
    }

    // ── acceptConnectionRequest ───────────────────────────────────────────

    @Test
    fun `acceptConnectionRequest by the recipient moves the connection to accepted`() {
        val (_, messaging) = repoWithUsers("alice", "bob")
        val connection = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")!!

        assertTrue(messaging.acceptConnectionRequest(connectionId = connection.id, acceptorId = "bob"))
        assertTrue(messaging.areConnected("alice", "bob"))
    }

    @Test
    fun `acceptConnectionRequest by the requester instead of the recipient returns false`() {
        // Only the intended recipient may accept; the requester may not accept
        // their own outgoing request.
        val (_, messaging) = repoWithUsers("alice", "bob")
        val connection = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")!!

        assertFalse(messaging.acceptConnectionRequest(connectionId = connection.id, acceptorId = "alice"))
        assertFalse(messaging.areConnected("alice", "bob"))
    }

    @Test
    fun `acceptConnectionRequest for an unknown connection id returns false`() {
        val (_, messaging) = repoWithUsers("alice", "bob")

        assertFalse(messaging.acceptConnectionRequest(connectionId = "no-such-id", acceptorId = "bob"))
    }

    @Test
    fun `acceptConnectionRequest on an already-accepted connection returns false`() {
        // AC#6: a second acceptance attempt does not change state and returns false.
        val (_, messaging) = repoWithUsers("alice", "bob")
        val connection = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")!!
        messaging.acceptConnectionRequest(connectionId = connection.id, acceptorId = "bob")

        assertFalse(messaging.acceptConnectionRequest(connectionId = connection.id, acceptorId = "bob"))
    }

    // ── AC#7: blocking integration ────────────────────────────────────────

    @Test
    fun `sendConnectionRequest is rejected when the recipient has blocked the requester`() {
        // AC#7 / P5: a blocked user cannot initiate contact.
        val (profiles, messaging) = repoWithUsers("alice", "bob")
        profiles.blockUser(blockerId = "bob", blockedId = "alice")

        assertNull(messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob"))
    }

    @Test
    fun `sendConnectionRequest is rejected when the requester has blocked the recipient`() {
        // A user who has blocked someone cannot reach out to them either.
        val (profiles, messaging) = repoWithUsers("alice", "bob")
        profiles.blockUser(blockerId = "alice", blockedId = "bob")

        assertNull(messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob"))
    }

    @Test
    fun `sendMessage is rejected when the recipient has blocked the sender`() {
        // AC#7 / P5: even an accepted connection does not override a block.
        val (profiles, messaging) = repoWithUsers("alice", "bob")
        val connection = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")!!
        messaging.acceptConnectionRequest(connectionId = connection.id, acceptorId = "bob")
        // Bob blocks Alice after the connection is established.
        profiles.blockUser(blockerId = "bob", blockedId = "alice")

        assertNull(messaging.sendMessage(senderId = "alice", recipientId = "bob", body = "Hello"))
    }

    // ── Message body validation ───────────────────────────────────────────

    @Test
    fun `sendMessage with a blank body returns null`() {
        val (_, messaging) = repoWithUsers("alice", "bob")
        val connection = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")!!
        messaging.acceptConnectionRequest(connectionId = connection.id, acceptorId = "bob")

        assertNull(messaging.sendMessage(senderId = "alice", recipientId = "bob", body = "   "))
    }

    @Test
    fun `sendMessage with a body exactly at the maximum length is accepted`() {
        val (_, messaging) = repoWithUsers("alice", "bob")
        val connection = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")!!
        messaging.acceptConnectionRequest(connectionId = connection.id, acceptorId = "bob")
        val maxBody = "a".repeat(MessagingRepository.MAX_MESSAGE_LENGTH)

        assertNotNull(messaging.sendMessage(senderId = "alice", recipientId = "bob", body = maxBody))
    }

    @Test
    fun `sendMessage with a body one character over the maximum length returns null`() {
        val (_, messaging) = repoWithUsers("alice", "bob")
        val connection = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")!!
        messaging.acceptConnectionRequest(connectionId = connection.id, acceptorId = "bob")
        val tooLong = "a".repeat(MessagingRepository.MAX_MESSAGE_LENGTH + 1)

        assertNull(messaging.sendMessage(senderId = "alice", recipientId = "bob", body = tooLong))
    }

    // ── getMessages ───────────────────────────────────────────────────────

    @Test
    fun `getMessages returns an empty list before any messages are sent`() {
        val (_, messaging) = repoWithUsers("alice", "bob")
        val connection = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")!!
        messaging.acceptConnectionRequest(connectionId = connection.id, acceptorId = "bob")

        assertEquals(emptyList(), messaging.getMessages("alice", "bob"))
    }

    @Test
    fun `getMessages returns all messages between two users in chronological order`() {
        val (_, messaging) = repoWithUsers("alice", "bob")
        val connection = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")!!
        messaging.acceptConnectionRequest(connectionId = connection.id, acceptorId = "bob")
        messaging.sendMessage(senderId = "alice", recipientId = "bob", body = "Hello")
        messaging.sendMessage(senderId = "bob", recipientId = "alice", body = "Hi")

        val messages = messaging.getMessages("alice", "bob")

        assertEquals(2, messages.size)
        assertEquals("Hello", messages[0].body)
        assertEquals("Hi", messages[1].body)
    }

    @Test
    fun `getMessages is symmetric — swapping the argument order returns the same list`() {
        val (_, messaging) = repoWithUsers("alice", "bob")
        val connection = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")!!
        messaging.acceptConnectionRequest(connectionId = connection.id, acceptorId = "bob")
        messaging.sendMessage(senderId = "alice", recipientId = "bob", body = "Hello")

        val ab = messaging.getMessages("alice", "bob")
        val ba = messaging.getMessages("bob", "alice")

        assertEquals(ab, ba)
    }

    @Test
    fun `getMessages does not include messages from a different pair`() {
        val (_, messaging) = repoWithUsers("alice", "bob", "carol")
        val ab = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")!!
        messaging.acceptConnectionRequest(connectionId = ab.id, acceptorId = "bob")
        val ac = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "carol")!!
        messaging.acceptConnectionRequest(connectionId = ac.id, acceptorId = "carol")

        messaging.sendMessage(senderId = "alice", recipientId = "bob", body = "Hello Bob")
        messaging.sendMessage(senderId = "alice", recipientId = "carol", body = "Hello Carol")

        val abMessages = messaging.getMessages("alice", "bob")
        assertEquals(1, abMessages.size)
        assertEquals("Hello Bob", abMessages[0].body)

        val acMessages = messaging.getMessages("alice", "carol")
        assertEquals(1, acMessages.size)
        assertEquals("Hello Carol", acMessages[0].body)
    }
}
