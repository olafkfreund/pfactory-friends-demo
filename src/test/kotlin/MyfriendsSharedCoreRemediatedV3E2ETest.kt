import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * End-to-end test suite for MyFriends shared core (remediated v3).
 *
 * Tests in this file simulate realistic, multi-step user journeys that span
 * the full set of acceptance criteria. Each test models a named scenario
 * (e.g. "new user joins and connects with another user") and verifies that
 * the core enforces every relevant rule across the entire flow.
 *
 * The domain is entirely in-memory: no network, no I/O, no background
 * threads (AC#19). All assertions are synchronous.
 */
class MyfriendsSharedCoreRemediatedV3E2ETest {

    // ── helpers ──────────────────────────────────────────────────────────────

    private fun photo() = ProfilePhoto(bytes = byteArrayOf(9, 8, 7), format = "jpeg")

    /** Creates and saves a profile with the given attributes. */
    private fun saveProfile(
        profileRepo: ProfileRepository,
        id: String,
        age: Int = 25,
        openToFriends: Boolean = false,
        interests: List<String> = emptyList(),
        activities: List<String> = emptyList(),
        location: GeoLocation? = null,
    ): Profile {
        val profile = Profile(
            id = id,
            displayName = "User $id",
            photo = photo(),
            age = age,
            openToFriends = openToFriends,
            interests = interests,
            activities = activities,
            location = location,
        )
        profileRepo.save(profile)
        return profile
    }

    /** Sends and accepts a connection request, returning the accepted connection. */
    private fun fullyConnect(
        messaging: MessagingRepository,
        requesterId: String,
        recipientId: String,
    ): Connection {
        val conn = messaging.sendConnectionRequest(requesterId = requesterId, recipientId = recipientId)!!
        messaging.acceptConnectionRequest(connectionId = conn.id, acceptorId = recipientId)
        return conn
    }

    // ── Scenario 1: new user onboarding and friend discovery ─────────────────

    /**
     * Two adult users create profiles, enable discovery, and appear in each
     * other's results scored by shared interests. Covers AC#1, AC#2, AC#5.
     */
    @Test
    fun `scenario new adult user creates profile and is discovered with correct match score`() {
        val profileRepo = ProfileRepository()

        // Two users create profiles.
        saveProfile(profileRepo, "alice", interests = listOf("jazz", "hiking"), activities = listOf("weekends"))
        saveProfile(profileRepo, "bob",
            openToFriends = true,
            interests = listOf("jazz", "climbing"),
            activities = listOf("weekends"))

        // Alice searches for friends.
        val aliceProfile = profileRepo.find("alice")!!
        val results = profileRepo.discover(aliceProfile)

        assertEquals(1, results.size)
        assertEquals("bob", results[0].profile.id)
        // Interests: {jazz,hiking} ∩ {jazz,climbing} = {jazz} → 1/2 = 0.5
        // Availability: {weekends} ∩ {weekends} = {weekends} → 1/1 = 1.0
        // Combined = (0.5 + 1.0) / 2 = 0.75
        assertEquals(0.75, results[0].score)
        assertEquals(listOf("jazz"), results[0].sharedInterests)
        assertEquals(listOf("weekends"), results[0].sharedActivities)
    }

    /**
     * A user under 16 cannot create an account (AC#4). A user aged 16 or 17
     * can create an account but is isolated from adults in discovery (AC#3).
     */
    @Test
    fun `scenario age gating at profile creation and in discovery`() {
        val profileRepo = ProfileRepository()

        // A user aged 15 tries to sign up — refused (AC#4).
        val error = assertFailsWith<IllegalArgumentException> {
            saveProfile(profileRepo, "too-young", age = 15)
        }
        assertTrue(
            error.message?.contains(ProfileRepository.MIN_AGE.toString()) == true ||
                error.message?.contains("age") == true,
            "refusal must name age as the reason",
        )

        // A 16-year-old successfully creates a profile (AC#4 minimum is 16).
        saveProfile(profileRepo, "teenager-16", age = 16, openToFriends = true, interests = listOf("gaming"))
        assertNotNull(profileRepo.find("teenager-16"))

        // An adult creates a profile.
        saveProfile(profileRepo, "adult-25", age = 25, interests = listOf("gaming"))

        // Adult searcher: cannot see the teenager (AC#3).
        val adultProfile = profileRepo.find("adult-25")!!
        val adultResults = profileRepo.discover(adultProfile)
        assertTrue(adultResults.none { it.profile.id == "teenager-16" })

        // Minor searcher: cannot see the adult (AC#3).
        val teenProfile = Profile(id = "searcher-17", displayName = "Searcher 17", photo = photo(), age = 17)
        val teenResults = profileRepo.discover(teenProfile)
        assertTrue(teenResults.none { it.profile.id == "adult-25" })

        // Minor searcher can see the other minor (AC#3 — same bracket).
        assertEquals(1, teenResults.size)
        assertEquals("teenager-16", teenResults[0].profile.id)
    }

    // ── Scenario 2: connection request and accepted messaging ─────────────────

    /**
     * Alice sends a connection request, Bob accepts, and they exchange messages.
     * Covers AC#7, AC#8.
     */
    @Test
    fun `scenario connection request accepted and messaging enabled`() {
        val profileRepo = ProfileRepository()
        saveProfile(profileRepo, "alice")
        saveProfile(profileRepo, "bob")
        val messaging = MessagingRepository(profileRepo)

        // Alice sends a request.
        val conn = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")
        assertNotNull(conn)
        assertEquals(ConnectionStatus.PENDING, conn.status)

        // Messaging is not yet allowed (AC#7).
        val before = messaging.sendMessageResult(senderId = "alice", recipientId = "bob", body = "Hi!")
        assertTrue(before is MessageResult.Refused)
        assertEquals(MessageRefusal.NOT_CONNECTED, before.reason)

        // Bob accepts.
        messaging.acceptConnectionRequest(connectionId = conn.id, acceptorId = "bob")

        // Messaging is now allowed (AC#7).
        val afterAlice = messaging.sendMessageResult(senderId = "alice", recipientId = "bob", body = "Hello Bob!")
        assertTrue(afterAlice is MessageResult.Allowed)

        val afterBob = messaging.sendMessageResult(senderId = "bob", recipientId = "alice", body = "Hello Alice!")
        assertTrue(afterBob is MessageResult.Allowed)

        val messages = messaging.getMessages("alice", "bob")
        assertEquals(2, messages.size)
        assertEquals("Hello Bob!", messages[0].body)
        assertEquals("Hello Alice!", messages[1].body)
    }

    /**
     * A user exhausts their daily connection-request quota.
     * Covers AC#8.
     */
    @Test
    fun `scenario daily connection request rate limit enforced at 20`() {
        val profileRepo = ProfileRepository()
        profileRepo.save(Profile(id = "requester", displayName = "Requester", photo = photo()))
        for (i in 1..(MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY + 1)) {
            profileRepo.save(Profile(id = "recipient-$i", displayName = "Recipient $i", photo = photo()))
        }
        val messaging = MessagingRepository(profileRepo)

        // Send exactly MAX requests — all succeed.
        for (i in 1..MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY) {
            val result = messaging.sendConnectionRequestResult(
                requesterId = "requester",
                recipientId = "recipient-$i",
            )
            assertTrue(
                result is ConnectionRequestResult.Allowed,
                "request $i of ${MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY} must succeed",
            )
        }

        // The next request — one over the limit — is refused.
        val overLimit = messaging.sendConnectionRequestResult(
            requesterId = "requester",
            recipientId = "recipient-${MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY + 1}",
        )
        assertTrue(overLimit is ConnectionRequestResult.Refused)
        assertEquals(ConnectionRequestRefusal.RATE_LIMIT_EXCEEDED, overLimit.reason)
    }

    // ── Scenario 3: abuse report flow ─────────────────────────────────────────

    /**
     * A user reports another user. The report is accepted immediately and is
     * retrievable from the moderation queue. Covers AC#9, AC#15.
     */
    @Test
    fun `scenario user files a report which is accepted and queryable`() {
        val profileRepo = ProfileRepository()
        saveProfile(profileRepo, "alice")
        saveProfile(profileRepo, "bob")
        val reportRepo = ReportRepository()

        // Alice reports Bob for harassment.
        val report = reportRepo.submitReport(
            reporterId = "alice",
            targetId = "bob",
            targetKind = ReportTargetKind.USER,
            reason = ReportReason.HARASSMENT,
            additionalText = "Bob sent me threatening messages.",
        )

        assertNotNull(report)
        assertEquals("alice", report.reporterId)
        assertEquals("bob", report.targetId)
        assertEquals(ReportReason.HARASSMENT, report.reason)
        assertFalse(report.additionalText.isBlank())

        // The report appears in the moderation queue.
        val queue = reportRepo.getReportsAgainst("bob")
        assertEquals(1, queue.size)
        assertEquals(report.id, queue[0].id)
    }

    /**
     * A user reports a specific message by id. Covers AC#9.
     */
    @Test
    fun `scenario user reports an offensive message`() {
        val reportRepo = ReportRepository()

        val report = reportRepo.submitReport(
            reporterId = "alice",
            targetId = "msg-777",
            targetKind = ReportTargetKind.MESSAGE,
            reason = ReportReason.INAPPROPRIATE_CONTENT,
        )

        assertNotNull(report)
        assertEquals(ReportTargetKind.MESSAGE, report.targetKind)
        assertEquals("msg-777", report.targetId)
    }

    // ── Scenario 4: block flow ────────────────────────────────────────────────

    /**
     * Alice blocks Bob. Bob is removed from discovery, cannot send connection
     * requests to Alice, and cannot message Alice. Covers AC#6, AC#10.
     */
    @Test
    fun `scenario block prevents all contact and moderation is unaffected`() {
        val profileRepo = ProfileRepository()
        saveProfile(profileRepo, "alice")
        saveProfile(profileRepo, "bob", openToFriends = true)
        profileRepo.blockUser(blockerId = "alice", blockedId = "bob")

        val aliceProfile = profileRepo.find("alice")!!
        val messaging = MessagingRepository(profileRepo)

        // Bob does not appear in Alice's discovery results (AC#6).
        val discovery = profileRepo.discover(aliceProfile)
        assertTrue(discovery.none { it.profile.id == "bob" })

        // Bob cannot send a connection request to Alice (AC#6).
        val connResult = messaging.sendConnectionRequestResult(requesterId = "bob", recipientId = "alice")
        assertTrue(connResult is ConnectionRequestResult.Refused)
        assertEquals(ConnectionRequestRefusal.BLOCKED, connResult.reason)

        // Alice can still report Bob (AC#10: moderation is independent of blocks).
        val reportRepo = ReportRepository()
        val report = reportRepo.submitReport(
            reporterId = "alice",
            targetId = "bob",
            targetKind = ReportTargetKind.USER,
            reason = ReportReason.SPAM,
        )
        assertNotNull(report)
    }

    /**
     * The block survives account deletion and re-registration within the
     * retention window. Covers AC#6.
     */
    @Test
    fun `scenario block survives blocked person deleting and re-registering`() {
        val profileRepo = ProfileRepository()
        saveProfile(profileRepo, "alice")
        saveProfile(profileRepo, "bob")
        profileRepo.blockUser(blockerId = "alice", blockedId = "bob")
        val messaging = MessagingRepository(profileRepo)

        // Bob deletes his account.
        profileRepo.deleteAccount("bob")

        // The block persists.
        assertTrue(profileRepo.isBlocked(blockerId = "alice", blockedId = "bob"))

        // Bob re-registers with the same id.
        saveProfile(profileRepo, "bob")

        // Alice's block still prevents Bob from reaching her.
        val result = messaging.sendConnectionRequestResult(requesterId = "bob", recipientId = "alice")
        assertTrue(result is ConnectionRequestResult.Refused)
        assertEquals(ConnectionRequestRefusal.BLOCKED, result.reason)
    }

    // ── Scenario 5: account deletion ─────────────────────────────────────────

    /**
     * Deleting an account removes the profile, photo, interests, and tags;
     * blocks and reports against the account are retained. Covers AC#11.
     */
    @Test
    fun `scenario account deletion removes personal data and retains safety records`() {
        val profileRepo = ProfileRepository()
        saveProfile(
            profileRepo,
            id = "deleted-user",
            interests = listOf("jazz", "hiking"),
            activities = listOf("weekends"),
            openToFriends = true,
        )
        saveProfile(profileRepo, "reporter")
        profileRepo.blockUser(blockerId = "reporter", blockedId = "deleted-user")
        val reportRepo = ReportRepository()
        reportRepo.submitReport("reporter", "deleted-user", ReportTargetKind.USER, ReportReason.SPAM)

        // Delete the account.
        val deleted = profileRepo.deleteAccount("deleted-user")
        assertTrue(deleted)

        // Profile is gone.
        assertNull(profileRepo.find("deleted-user"))
        assertTrue(profileRepo.findOpen().none { it.id == "deleted-user" })

        // Block against the account is retained.
        assertTrue(
            profileRepo.isBlocked(blockerId = "reporter", blockedId = "deleted-user"),
            "block must be retained after account deletion",
        )

        // Reports against the account are retained.
        val reports = reportRepo.getReportsAgainst("deleted-user")
        assertEquals(1, reports.size, "report must be retained after account deletion")
    }

    // ── Scenario 6: coarse location privacy ──────────────────────────────────

    /**
     * The searcher's coarse location used for a proximity query is never
     * persisted to storage. Covers AC#12.
     */
    @Test
    fun `scenario searcher location is not persisted after a radius discovery`() {
        val profileRepo = ProfileRepository()
        val searcher = Profile(id = "searcher", displayName = "Searcher", photo = photo(), age = 25)
        profileRepo.save(searcher)
        val searcherLocation = GeoLocation(lat = 51.500, lon = -0.100)
        profileRepo.save(
            Profile(
                id = "nearby",
                displayName = "Nearby",
                photo = photo(),
                age = 25,
                openToFriends = true,
                location = GeoLocation(lat = 51.501, lon = -0.100),
            ),
        )

        // Run the discovery with the ephemeral location.
        val results = profileRepo.discover(searcher, searcherLocation, SearchRadius.FIVE)

        assertEquals(1, results.size)
        // The searcher's profile has no stored location — it was not persisted.
        assertNull(profileRepo.find("searcher")?.location)
        // The result does not carry the searcher's location.
        results.forEach { result ->
            assertTrue(
                result.profile.location == null || result.profile.location != searcherLocation,
                "no result profile may carry the searcher's search location",
            )
        }
    }

    // ── Scenario 7: machine-readable decisions end-to-end ────────────────────

    /**
     * Every refusal in the happy path is paired with a machine-readable reason
     * so clients can show the exact reason. Covers AC#14.
     */
    @Test
    fun `scenario every refusal in a connection flow carries a machine-readable reason`() {
        val profileRepo = ProfileRepository()
        profileRepo.save(Profile(id = "alice", displayName = "Alice", photo = photo()))
        profileRepo.save(Profile(id = "bob", displayName = "Bob", photo = photo()))
        val messaging = MessagingRepository(profileRepo)

        // 1. Self-request is refused with SELF_REQUEST.
        val selfRequest = messaging.sendConnectionRequestResult("alice", "alice")
        assertEquals(ConnectionRequestRefusal.SELF_REQUEST, (selfRequest as ConnectionRequestResult.Refused).reason)

        // 2. Blank id is refused with BLANK_ID.
        val blankId = messaging.sendConnectionRequestResult("alice", "")
        assertEquals(ConnectionRequestRefusal.BLANK_ID, (blankId as ConnectionRequestResult.Refused).reason)

        // 3. Messaging before connection is refused with NOT_CONNECTED.
        val msgBefore = messaging.sendMessageResult("alice", "bob", "Hi")
        assertEquals(MessageRefusal.NOT_CONNECTED, (msgBefore as MessageResult.Refused).reason)

        // 4. After acceptance, blank body is refused with BLANK_BODY.
        fullyConnect(messaging, "alice", "bob")
        val blankBody = messaging.sendMessageResult("alice", "bob", "  ")
        assertEquals(MessageRefusal.BLANK_BODY, (blankBody as MessageResult.Refused).reason)

        // 5. Body too long is refused with BODY_TOO_LONG.
        val tooLong = messaging.sendMessageResult("alice", "bob", "x".repeat(MessagingRepository.MAX_MESSAGE_LENGTH + 1))
        assertEquals(MessageRefusal.BODY_TOO_LONG, (tooLong as MessageResult.Refused).reason)
    }

    // ── Scenario 8: offline cache round-trip ─────────────────────────────────

    /**
     * Profile, connection, and message snapshots can be cached and retrieved
     * offline. Covers AC#19 (no network — all in-memory).
     */
    @Test
    fun `scenario offline cache stores and retrieves a user snapshot`() {
        val profileRepo = ProfileRepository()
        val aliceProfile = saveProfile(profileRepo, "alice", interests = listOf("jazz"))
        val bobProfile = saveProfile(profileRepo, "bob")
        val messaging = MessagingRepository(profileRepo)
        fullyConnect(messaging, "alice", "bob")
        val conn = Connection(
            id = "alice::bob",
            requesterId = "alice",
            recipientId = "bob",
            status = ConnectionStatus.ACCEPTED,
        )
        messaging.sendMessage("alice", "bob", "Hey!")

        val cache = OfflineCache()
        cache.cacheProfile(aliceProfile)
        cache.cacheConnections("alice", listOf(conn))
        cache.cacheMessages(
            "alice",
            "bob",
            messaging.getMessages("alice", "bob"),
        )

        // Offline reads return the cached snapshots.
        assertEquals("alice", cache.getCachedProfile("alice")?.id)
        assertEquals(1, cache.getCachedConnections("alice").size)
        assertEquals(ConnectionStatus.ACCEPTED, cache.getCachedConnections("alice")[0].status)
        assertEquals(1, cache.getCachedMessages("alice", "bob").size)
        assertEquals("Hey!", cache.getCachedMessages("alice", "bob")[0].body)
    }

    // ── Scenario 9: comprehensive compliance flow ─────────────────────────────

    /**
     * Full compliance scenario: two users meet, connect, one blocks and reports
     * the other, and account deletion leaves safety records intact.
     * Covers AC#1, AC#2, AC#6, AC#7, AC#9, AC#10, AC#11, AC#14.
     */
    @Test
    fun `scenario full compliance journey from discovery to report and deletion`() {
        val profileRepo = ProfileRepository()
        val messaging = MessagingRepository(profileRepo)
        val reportRepo = ReportRepository()

        // 1. Alice and Bob create profiles.
        saveProfile(profileRepo, "alice", interests = listOf("cycling"))
        saveProfile(profileRepo, "bob", openToFriends = true, interests = listOf("cycling"))

        // 2. Alice discovers Bob via shared interests (AC#1, AC#2).
        val aliceProfile = profileRepo.find("alice")!!
        val discovery = profileRepo.discover(aliceProfile)
        assertEquals(1, discovery.size)
        assertEquals("bob", discovery[0].profile.id)
        assertEquals(listOf("cycling"), discovery[0].sharedInterests)

        // 3. Alice sends a connection request; Bob accepts (AC#7).
        val conn = messaging.sendConnectionRequest("alice", "bob")!!
        assertEquals(ConnectionStatus.PENDING, conn.status)
        messaging.acceptConnectionRequest(conn.id, "bob")
        assertTrue(messaging.areConnected("alice", "bob"))

        // 4. They exchange messages (AC#7).
        val msg = messaging.sendMessageResult("alice", "bob", "Hello!")
        assertTrue(msg is MessageResult.Allowed)

        // 5. Alice receives harassment; she blocks Bob (AC#6).
        profileRepo.blockUser(blockerId = "alice", blockedId = "bob")
        assertTrue(profileRepo.isBlocked(blockerId = "alice", blockedId = "bob"))

        // Bob can no longer message Alice after the block (AC#6).
        val blockedMsg = messaging.sendMessageResult("bob", "alice", "Hey")
        assertTrue(blockedMsg is MessageResult.Refused)
        assertEquals(MessageRefusal.BLOCKED, blockedMsg.reason)

        // 6. Alice reports Bob (AC#9, AC#10).
        val report = reportRepo.submitReport(
            reporterId = "alice",
            targetId = "bob",
            targetKind = ReportTargetKind.USER,
            reason = ReportReason.HARASSMENT,
            additionalText = "He sent harassing messages.",
        )
        assertNotNull(report)

        // 7. Bob deletes his account (AC#11).
        profileRepo.deleteAccount("bob")
        assertNull(profileRepo.find("bob"))

        // Block record is retained (AC#11).
        assertTrue(profileRepo.isBlocked(blockerId = "alice", blockedId = "bob"))

        // Report is retained (AC#11).
        val retainedReports = reportRepo.getReportsAgainst("bob")
        assertEquals(1, retainedReports.size)
    }

}
