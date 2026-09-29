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

    // ── AC#5: connection request rate limiting ────────────────────────────

    @Test
    fun `sendConnectionRequest succeeds for each request up to the daily limit`() {
        // AC#5: exactly MAX_CONNECTION_REQUESTS_PER_DAY new requests must succeed.
        val profileRepo = ProfileRepository()
        profileRepo.save(Profile(id = "alice", displayName = "Alice", photo = validPhoto()))
        for (i in 1..MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY) {
            profileRepo.save(Profile(id = "user-$i", displayName = "User $i", photo = validPhoto()))
        }
        val messaging = MessagingRepository(profileRepo)

        for (i in 1..MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY) {
            assertNotNull(
                messaging.sendConnectionRequest(requesterId = "alice", recipientId = "user-$i"),
                "request $i should succeed",
            )
        }
    }

    @Test
    fun `sendConnectionRequest is rejected once the daily limit is reached`() {
        // AC#5: the request immediately after the limit is returned as null.
        val profileRepo = ProfileRepository()
        profileRepo.save(Profile(id = "alice", displayName = "Alice", photo = validPhoto()))
        for (i in 1..(MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY + 1)) {
            profileRepo.save(Profile(id = "user-$i", displayName = "User $i", photo = validPhoto()))
        }
        val messaging = MessagingRepository(profileRepo)

        // Exhaust the daily limit.
        for (i in 1..MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY) {
            messaging.sendConnectionRequest(requesterId = "alice", recipientId = "user-$i")
        }

        // The next new request exceeds the limit and is rejected.
        assertNull(
            messaging.sendConnectionRequest(
                requesterId = "alice",
                recipientId = "user-${MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY + 1}",
            ),
        )
    }

    @Test
    fun `connection request limits are per requester and do not affect other users`() {
        // AC#5: each requester has an independent counter; exhausting alice's
        // limit does not prevent bob from sending requests.
        val profileRepo = ProfileRepository()
        profileRepo.save(Profile(id = "alice", displayName = "Alice", photo = validPhoto()))
        profileRepo.save(Profile(id = "bob", displayName = "Bob", photo = validPhoto()))
        for (i in 1..(MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY + 1)) {
            profileRepo.save(Profile(id = "user-$i", displayName = "User $i", photo = validPhoto()))
        }
        val messaging = MessagingRepository(profileRepo)

        // Alice exhausts her daily limit.
        for (i in 1..MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY) {
            messaging.sendConnectionRequest(requesterId = "alice", recipientId = "user-$i")
        }

        // Bob is not affected — his limit is separate.
        assertNotNull(
            messaging.sendConnectionRequest(
                requesterId = "bob",
                recipientId = "user-${MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY + 1}",
            ),
        )
    }

    // ── C14: sendConnectionRequestResult — typed refusal reasons ─────────

    @Test
    fun `sendConnectionRequestResult returns Allowed with the connection on success`() {
        val (_, messaging) = repoWithUsers("alice", "bob")

        val result = messaging.sendConnectionRequestResult(requesterId = "alice", recipientId = "bob")

        assertTrue(result is ConnectionRequestResult.Allowed)
        assertEquals(ConnectionStatus.PENDING, result.connection.status)
        assertEquals("alice", result.connection.requesterId)
        assertEquals("bob", result.connection.recipientId)
    }

    @Test
    fun `sendConnectionRequestResult returns Refused with BLANK_ID when requester id is blank`() {
        val (_, messaging) = repoWithUsers("alice")

        val result = messaging.sendConnectionRequestResult(requesterId = " ", recipientId = "alice")

        assertTrue(result is ConnectionRequestResult.Refused)
        assertEquals(ConnectionRequestRefusal.BLANK_ID, result.reason)
    }

    @Test
    fun `sendConnectionRequestResult returns Refused with BLANK_ID when recipient id is blank`() {
        val (_, messaging) = repoWithUsers("alice")

        val result = messaging.sendConnectionRequestResult(requesterId = "alice", recipientId = "")

        assertTrue(result is ConnectionRequestResult.Refused)
        assertEquals(ConnectionRequestRefusal.BLANK_ID, result.reason)
    }

    @Test
    fun `sendConnectionRequestResult returns Refused with SELF_REQUEST when ids are equal`() {
        val (_, messaging) = repoWithUsers("alice")

        val result = messaging.sendConnectionRequestResult(requesterId = "alice", recipientId = "alice")

        assertTrue(result is ConnectionRequestResult.Refused)
        assertEquals(ConnectionRequestRefusal.SELF_REQUEST, result.reason)
    }

    @Test
    fun `sendConnectionRequestResult returns Refused with BLOCKED when recipient blocked requester`() {
        val (profiles, messaging) = repoWithUsers("alice", "bob")
        profiles.blockUser(blockerId = "bob", blockedId = "alice")

        val result = messaging.sendConnectionRequestResult(requesterId = "alice", recipientId = "bob")

        assertTrue(result is ConnectionRequestResult.Refused)
        assertEquals(ConnectionRequestRefusal.BLOCKED, result.reason)
    }

    @Test
    fun `sendConnectionRequestResult returns Refused with BLOCKED when requester blocked recipient`() {
        val (profiles, messaging) = repoWithUsers("alice", "bob")
        profiles.blockUser(blockerId = "alice", blockedId = "bob")

        val result = messaging.sendConnectionRequestResult(requesterId = "alice", recipientId = "bob")

        assertTrue(result is ConnectionRequestResult.Refused)
        assertEquals(ConnectionRequestRefusal.BLOCKED, result.reason)
    }

    @Test
    fun `sendConnectionRequestResult returns Refused with ALREADY_EXISTS on duplicate request`() {
        val (_, messaging) = repoWithUsers("alice", "bob")
        messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")

        val result = messaging.sendConnectionRequestResult(requesterId = "alice", recipientId = "bob")

        assertTrue(result is ConnectionRequestResult.Refused)
        assertEquals(ConnectionRequestRefusal.ALREADY_EXISTS, result.reason)
    }

    @Test
    fun `sendConnectionRequestResult returns Refused with RATE_LIMIT_EXCEEDED after daily limit`() {
        val profileRepo = ProfileRepository()
        profileRepo.save(Profile(id = "alice", displayName = "Alice", photo = validPhoto()))
        for (i in 1..(MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY + 1)) {
            profileRepo.save(Profile(id = "user-$i", displayName = "User $i", photo = validPhoto()))
        }
        val messaging = MessagingRepository(profileRepo)
        for (i in 1..MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY) {
            messaging.sendConnectionRequest(requesterId = "alice", recipientId = "user-$i")
        }

        val result = messaging.sendConnectionRequestResult(
            requesterId = "alice",
            recipientId = "user-${MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY + 1}",
        )

        assertTrue(result is ConnectionRequestResult.Refused)
        assertEquals(ConnectionRequestRefusal.RATE_LIMIT_EXCEEDED, result.reason)
    }

    // ── C14: sendMessageResult — typed refusal reasons ────────────────────

    @Test
    fun `sendMessageResult returns Allowed with the message on success`() {
        val (_, messaging) = repoWithUsers("alice", "bob")
        val connection = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")!!
        messaging.acceptConnectionRequest(connectionId = connection.id, acceptorId = "bob")

        val result = messaging.sendMessageResult(senderId = "alice", recipientId = "bob", body = "Hello")

        assertTrue(result is MessageResult.Allowed)
        assertEquals("alice", result.message.senderId)
        assertEquals("bob", result.message.recipientId)
        assertEquals("Hello", result.message.body)
    }

    @Test
    fun `sendMessageResult returns Refused with NOT_CONNECTED when no connection exists`() {
        val (_, messaging) = repoWithUsers("alice", "bob")

        val result = messaging.sendMessageResult(senderId = "alice", recipientId = "bob", body = "Hello")

        assertTrue(result is MessageResult.Refused)
        assertEquals(MessageRefusal.NOT_CONNECTED, result.reason)
    }

    @Test
    fun `sendMessageResult returns Refused with NOT_CONNECTED when connection is still pending`() {
        val (_, messaging) = repoWithUsers("alice", "bob")
        messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")

        val result = messaging.sendMessageResult(senderId = "alice", recipientId = "bob", body = "Hello")

        assertTrue(result is MessageResult.Refused)
        assertEquals(MessageRefusal.NOT_CONNECTED, result.reason)
    }

    @Test
    fun `sendMessageResult returns Refused with BLOCKED when recipient blocked sender`() {
        val (profiles, messaging) = repoWithUsers("alice", "bob")
        val connection = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")!!
        messaging.acceptConnectionRequest(connectionId = connection.id, acceptorId = "bob")
        profiles.blockUser(blockerId = "bob", blockedId = "alice")

        val result = messaging.sendMessageResult(senderId = "alice", recipientId = "bob", body = "Hello")

        assertTrue(result is MessageResult.Refused)
        assertEquals(MessageRefusal.BLOCKED, result.reason)
    }

    @Test
    fun `sendMessageResult returns Refused with BLANK_BODY when body is blank`() {
        val (_, messaging) = repoWithUsers("alice", "bob")
        val connection = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")!!
        messaging.acceptConnectionRequest(connectionId = connection.id, acceptorId = "bob")

        val result = messaging.sendMessageResult(senderId = "alice", recipientId = "bob", body = "   ")

        assertTrue(result is MessageResult.Refused)
        assertEquals(MessageRefusal.BLANK_BODY, result.reason)
    }

    @Test
    fun `sendMessageResult returns Refused with BODY_TOO_LONG when body exceeds limit`() {
        val (_, messaging) = repoWithUsers("alice", "bob")
        val connection = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")!!
        messaging.acceptConnectionRequest(connectionId = connection.id, acceptorId = "bob")
        val tooLong = "a".repeat(MessagingRepository.MAX_MESSAGE_LENGTH + 1)

        val result = messaging.sendMessageResult(senderId = "alice", recipientId = "bob", body = tooLong)

        assertTrue(result is MessageResult.Refused)
        assertEquals(MessageRefusal.BODY_TOO_LONG, result.reason)
    }

    @Test
    fun `sendMessageResult returns Allowed for a body exactly at the maximum length`() {
        val (_, messaging) = repoWithUsers("alice", "bob")
        val connection = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")!!
        messaging.acceptConnectionRequest(connectionId = connection.id, acceptorId = "bob")
        val maxBody = "a".repeat(MessagingRepository.MAX_MESSAGE_LENGTH)

        val result = messaging.sendMessageResult(senderId = "alice", recipientId = "bob", body = maxBody)

        assertTrue(result is MessageResult.Allowed)
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
