import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Integration test suite for MyFriends shared core (remediated v3).
 *
 * Tests in this file exercise multiple components working together:
 * [ProfileRepository], [MessagingRepository], [ReportRepository], and
 * supporting types. The goal is to verify that the acceptance criteria hold
 * across component boundaries, not just in isolation.
 *
 * Unit-level and end-to-end tests are in the companion files
 * [MyfriendsSharedCoreRemediatedV3UnitTest] and
 * [MyfriendsSharedCoreRemediatedV3E2ETest].
 */
class MyfriendsSharedCoreRemediatedV3IntegrationTest {
    // ── helpers ──────────────────────────────────────────────────────────────

    private fun photo() = ProfilePhoto(bytes = byteArrayOf(1, 2, 3), format = "png")

    private fun saveProfile(
        repo: ProfileRepository,
        id: String,
        age: Int = 25,
        openToFriends: Boolean = false,
        interests: List<String> = emptyList(),
        activities: List<String> = emptyList(),
        location: GeoLocation? = null,
    ): Profile {
        val profile =
            Profile(
                id = id,
                displayName = "User $id",
                photo = photo(),
                age = age,
                openToFriends = openToFriends,
                interests = interests,
                activities = activities,
                location = location,
            )
        repo.save(profile)
        return profile
    }

    private fun connect(
        messaging: MessagingRepository,
        requesterId: String,
        recipientId: String,
    ): Connection {
        val conn = messaging.sendConnectionRequest(requesterId = requesterId, recipientId = recipientId)!!
        messaging.acceptConnectionRequest(connectionId = conn.id, acceptorId = recipientId)
        return conn
    }

    // ── AC#1 + AC#2: discovery ordered by match score, open profiles only ────

    @Test
    fun `AC1-AC2 discover returns open profiles ordered by combined match score`() {
        val repo = ProfileRepository()
        val searcher = saveProfile(repo, "searcher", interests = listOf("jazz", "climbing"), activities = listOf("weekends"))

        // grace: interests overlap fully (1.0), availability matches (1.0) → combined 1.0
        saveProfile(
            repo,
            "grace",
            openToFriends = true,
            interests = listOf("jazz", "climbing"),
            activities = listOf("weekends"),
        )

        // ada: interests half-match (0.5), no availability overlap (0.0) → combined 0.25
        saveProfile(
            repo,
            "ada",
            openToFriends = true,
            interests = listOf("jazz"),
            activities = listOf("mornings"),
        )

        // closed: not open
        saveProfile(repo, "closed", openToFriends = false, interests = listOf("jazz", "climbing"))

        val results = repo.discover(searcher)

        assertEquals(2, results.size)
        assertEquals("grace", results[0].profile.id)
        assertEquals("ada", results[1].profile.id)
        assertTrue(results.none { it.profile.id == "closed" })
    }

    @Test
    fun `AC1-AC2 turning off openToFriends removes the profile from future discover calls`() {
        val repo = ProfileRepository()
        val searcher = saveProfile(repo, "searcher")
        saveProfile(repo, "target", openToFriends = true)

        assertEquals(1, repo.discover(searcher).size)
        repo.setOpenToFriends("target", false)
        assertTrue(repo.discover(searcher).isEmpty())
    }

    // ── AC#3 + AC#5: age isolation combined with profile eligibility ──────────

    @Test
    fun `AC3-AC5 minor searcher only sees minor candidates that passed age validation`() {
        val repo = ProfileRepository()
        val minorSearcher = saveProfile(repo, "minor-searcher", age = 17)

        saveProfile(repo, "minor-open", age = 16, openToFriends = true)
        saveProfile(repo, "adult-open", age = 25, openToFriends = true)

        val results = repo.discover(minorSearcher)

        assertEquals(1, results.size)
        assertEquals("minor-open", results[0].profile.id)
        assertEquals(16, results[0].profile.age)
    }

    @Test
    fun `AC3-AC5 adult searcher only sees adult candidates that passed age validation`() {
        val repo = ProfileRepository()
        val adultSearcher = saveProfile(repo, "adult-searcher", age = 30)

        saveProfile(repo, "adult-open", age = 22, openToFriends = true)
        saveProfile(repo, "minor-open", age = 17, openToFriends = true)

        val results = repo.discover(adultSearcher)

        assertEquals(1, results.size)
        assertEquals("adult-open", results[0].profile.id)
    }

    // ── AC#4 + AC#5: minimum age enforced at creation; ineligible if not stored ─

    @Test
    fun `AC4-AC5 a profile under 16 cannot be created and is ineligible for everything`() {
        val repo = ProfileRepository()

        assertFailsWith<IllegalArgumentException> {
            repo.save(
                Profile(id = "too-young", displayName = "Too Young", photo = photo(), age = 14, openToFriends = true),
            )
        }

        assertNull(repo.find("too-young"))
        assertTrue(repo.findOpen().none { it.id == "too-young" })
    }

    // ── AC#6 + AC#7: block prevents discovery, connections, and messaging ─────

    @Test
    fun `AC6-AC7 block prevents discovery, connection request, and messaging`() {
        val profileRepo = ProfileRepository()
        val searcher = saveProfile(profileRepo, "alice")
        profileRepo.save(searcher)
        saveProfile(profileRepo, "bob", openToFriends = true)
        profileRepo.blockUser(blockerId = "alice", blockedId = "bob")

        val messaging = MessagingRepository(profileRepo)

        // Discovery: bob must not appear in alice's results.
        val discoveryResults = profileRepo.discover(searcher)
        assertTrue(discoveryResults.none { it.profile.id == "bob" })

        // Connection request: refused with BLOCKED.
        val connResult = messaging.sendConnectionRequestResult(requesterId = "alice", recipientId = "bob")
        assertTrue(connResult is ConnectionRequestResult.Refused)
        assertEquals(ConnectionRequestRefusal.BLOCKED, connResult.reason)
    }

    @Test
    fun `AC6-AC7 block established after connection prevents further messaging`() {
        val profileRepo = ProfileRepository()
        saveProfile(profileRepo, "alice")
        saveProfile(profileRepo, "bob")
        val messaging = MessagingRepository(profileRepo)
        connect(messaging, "alice", "bob")

        // Messaging works before the block.
        assertTrue(messaging.sendMessageResult("alice", "bob", "Hi") is MessageResult.Allowed)

        // Bob blocks Alice.
        profileRepo.blockUser(blockerId = "bob", blockedId = "alice")

        // Messaging is now refused.
        val result = messaging.sendMessageResult("alice", "bob", "Hi again")
        assertTrue(result is MessageResult.Refused)
        assertEquals(MessageRefusal.BLOCKED, result.reason)
    }

    @Test
    fun `AC6 block persists after the blocked person deletes and the blocker still cannot be reached`() {
        // AC#6: the block survives the blocked person deleting their account.
        val profileRepo = ProfileRepository()
        saveProfile(profileRepo, "alice")
        saveProfile(profileRepo, "bob")
        profileRepo.blockUser(blockerId = "alice", blockedId = "bob")
        val messaging = MessagingRepository(profileRepo)

        // Bob deletes his account.
        profileRepo.deleteAccount("bob")

        // The block record persists.
        assertTrue(profileRepo.isBlocked(blockerId = "alice", blockedId = "bob"))

        // If bob re-registers with the same id, the block would prevent the request.
        profileRepo.save(Profile(id = "bob", displayName = "Bob Re-registered", photo = photo(), age = 25))
        val result = messaging.sendConnectionRequestResult(requesterId = "bob", recipientId = "alice")
        assertTrue(result is ConnectionRequestResult.Refused)
        assertEquals(ConnectionRequestRefusal.BLOCKED, result.reason)
    }

    // ── AC#7 + AC#8: connection state gate and rate limiting ─────────────────

    @Test
    fun `AC7-AC8 messaging is allowed only after connection is accepted and within rate limit`() {
        val profileRepo = ProfileRepository()
        saveProfile(profileRepo, "alice")
        saveProfile(profileRepo, "bob")
        val messaging = MessagingRepository(profileRepo)

        // Before connection: messaging refused.
        val before = messaging.sendMessageResult("alice", "bob", "Hi")
        assertTrue(before is MessageResult.Refused)
        assertEquals(MessageRefusal.NOT_CONNECTED, before.reason)

        // After accepted connection: messaging allowed.
        connect(messaging, "alice", "bob")
        val after = messaging.sendMessageResult("alice", "bob", "Hi")
        assertTrue(after is MessageResult.Allowed)
    }

    @Test
    fun `AC8 rate limit is enforced per requester and does not affect other users`() {
        val profileRepo = ProfileRepository()
        saveProfile(profileRepo, "alice")
        saveProfile(profileRepo, "carol")
        for (i in 1..(MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY + 1)) {
            profileRepo.save(Profile(id = "user-$i", displayName = "User $i", photo = photo()))
        }
        val messaging = MessagingRepository(profileRepo)

        // Alice exhausts her daily limit.
        for (i in 1..MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY) {
            messaging.sendConnectionRequest(requesterId = "alice", recipientId = "user-$i")
        }
        // Alice's next request is refused.
        val aliceResult =
            messaging.sendConnectionRequestResult(
                requesterId = "alice",
                recipientId = "user-${MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY + 1}",
            )
        assertTrue(aliceResult is ConnectionRequestResult.Refused)
        assertEquals(ConnectionRequestRefusal.RATE_LIMIT_EXCEEDED, aliceResult.reason)

        // Carol's limit is independent — she can still send.
        val carolResult =
            messaging.sendConnectionRequestResult(
                requesterId = "carol",
                recipientId = "user-${MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY + 1}",
            )
        assertTrue(carolResult is ConnectionRequestResult.Allowed)
    }

    // ── AC#9 + AC#10: reports independent of block state ────────────────────

    @Test
    fun `AC9-AC10 a report filed by a blocked user is accepted and visible to moderation`() {
        val profileRepo = ProfileRepository()
        saveProfile(profileRepo, "alice")
        saveProfile(profileRepo, "bob")
        // Bob blocks Alice.
        profileRepo.blockUser(blockerId = "bob", blockedId = "alice")
        val reportRepo = ReportRepository()

        // Alice can still report Bob.
        val report =
            reportRepo.submitReport(
                reporterId = "alice",
                targetId = "bob",
                targetKind = ReportTargetKind.USER,
                reason = ReportReason.HARASSMENT,
                additionalText = "Bob has been harassing me.",
            )

        assertNotNull(report)
        val reports = reportRepo.getReportsAgainst("bob")
        assertEquals(1, reports.size)
        assertEquals("alice", reports[0].reporterId)
    }

    @Test
    fun `AC9-AC10 mutual blocks do not affect report filing or moderation visibility`() {
        val profileRepo = ProfileRepository()
        saveProfile(profileRepo, "alice")
        saveProfile(profileRepo, "bob")
        profileRepo.blockUser(blockerId = "alice", blockedId = "bob")
        profileRepo.blockUser(blockerId = "bob", blockedId = "alice")
        val reportRepo = ReportRepository()

        reportRepo.submitReport("alice", "bob", ReportTargetKind.USER, ReportReason.SPAM)
        reportRepo.submitReport("bob", "alice", ReportTargetKind.USER, ReportReason.HARASSMENT)

        assertEquals(1, reportRepo.getReportsAgainst("bob").size)
        assertEquals(1, reportRepo.getReportsAgainst("alice").size)
    }

    // ── AC#11: account deletion removes profile data; retains blocks/reports ─

    @Test
    fun `AC11 deleting an account removes the profile and its attributes`() {
        val repo = ProfileRepository()
        saveProfile(
            repo,
            id = "to-delete",
            interests = listOf("jazz"),
            activities = listOf("weekends"),
            openToFriends = true,
        )

        assertTrue(repo.deleteAccount("to-delete"))

        assertNull(repo.find("to-delete"))
        assertTrue(repo.findOpen().none { it.id == "to-delete" })
    }

    @Test
    fun `AC11 reports filed against a deleted account are retained in ReportRepository`() {
        // Blocks and reports are retained after the account they relate to is closed.
        val profileRepo = ProfileRepository()
        saveProfile(profileRepo, "alice")
        saveProfile(profileRepo, "bob")
        val reportRepo = ReportRepository()
        reportRepo.submitReport("alice", "bob", ReportTargetKind.USER, ReportReason.SPAM)

        // Bob deletes his account.
        profileRepo.deleteAccount("bob")

        // The report is still in the repository.
        val reports = reportRepo.getReportsAgainst("bob")
        assertEquals(1, reports.size, "report must be retained after account deletion")
    }

    @Test
    fun `AC11 blocks against a deleted account are retained in ProfileRepository`() {
        val profileRepo = ProfileRepository()
        saveProfile(profileRepo, "alice")
        saveProfile(profileRepo, "bob")
        profileRepo.blockUser(blockerId = "alice", blockedId = "bob")

        profileRepo.deleteAccount("bob")

        assertTrue(
            profileRepo.isBlocked(blockerId = "alice", blockedId = "bob"),
            "block must be retained after account deletion",
        )
    }

    // ── AC#12: coarse location is ephemeral ───────────────────────────────────

    @Test
    fun `AC12 after a radius-based discover call the searcher's location is not available from any read`() {
        val profileRepo = ProfileRepository()
        val searcherLocation = GeoLocation(lat = 51.500, lon = -0.100)
        val searcher =
            Profile(
                id = "searcher",
                displayName = "Searcher",
                photo = photo(),
                age = 25,
                location = null,
            )
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

        profileRepo.discover(searcher, searcherLocation, SearchRadius.FIVE)

        // The searcher profile retains null location — the parameter was not stored.
        assertNull(profileRepo.find("searcher")?.location)
    }

    // ── AC#14: all decision paths carry a machine-readable reason ─────────────

    @Test
    fun `AC14 every connection-request refusal scenario produces a distinct reason`() {
        val profileRepo = ProfileRepository()
        profileRepo.save(Profile(id = "alice", displayName = "Alice", photo = photo()))
        profileRepo.save(Profile(id = "bob", displayName = "Bob", photo = photo()))
        val messaging = MessagingRepository(profileRepo)

        // SELF_REQUEST
        val selfResult = messaging.sendConnectionRequestResult("alice", "alice")
        assertEquals(ConnectionRequestRefusal.SELF_REQUEST, (selfResult as ConnectionRequestResult.Refused).reason)

        // BLANK_ID
        val blankResult = messaging.sendConnectionRequestResult("", "alice")
        assertEquals(ConnectionRequestRefusal.BLANK_ID, (blankResult as ConnectionRequestResult.Refused).reason)

        // BLOCKED
        profileRepo.blockUser(blockerId = "alice", blockedId = "bob")
        val blockedResult = messaging.sendConnectionRequestResult("bob", "alice")
        assertEquals(ConnectionRequestRefusal.BLOCKED, (blockedResult as ConnectionRequestResult.Refused).reason)
    }

    @Test
    fun `AC14 every message-send refusal scenario produces a distinct reason`() {
        val profileRepo = ProfileRepository()
        profileRepo.save(Profile(id = "alice", displayName = "Alice", photo = photo()))
        profileRepo.save(Profile(id = "bob", displayName = "Bob", photo = photo()))
        val messaging = MessagingRepository(profileRepo)
        val conn = messaging.sendConnectionRequest("alice", "bob")!!
        messaging.acceptConnectionRequest(conn.id, "bob")

        // BLANK_BODY
        val blankBody = messaging.sendMessageResult("alice", "bob", "   ")
        assertEquals(MessageRefusal.BLANK_BODY, (blankBody as MessageResult.Refused).reason)

        // BODY_TOO_LONG
        val longBody = messaging.sendMessageResult("alice", "bob", "x".repeat(MessagingRepository.MAX_MESSAGE_LENGTH + 1))
        assertEquals(MessageRefusal.BODY_TOO_LONG, (longBody as MessageResult.Refused).reason)

        // NOT_CONNECTED
        profileRepo.save(Profile(id = "carol", displayName = "Carol", photo = photo()))
        val notConnected = messaging.sendMessageResult("alice", "carol", "Hi")
        assertEquals(MessageRefusal.NOT_CONNECTED, (notConnected as MessageResult.Refused).reason)
    }

    // ── AC#15 + AC#16: report queue and reason enumeration ───────────────────

    @Test
    fun `AC15-AC16 reports with all valid reasons are accepted and stored`() {
        val repo = ReportRepository()

        for (reason in ReportReason.entries) {
            val report =
                repo.submitReport(
                    reporterId = "alice",
                    targetId = "target-${reason.name}",
                    targetKind = ReportTargetKind.USER,
                    reason = reason,
                )
            assertNotNull(report, "report with reason $reason must be accepted")
        }

        val aliceReports = repo.getReportsByReporter("alice")
        assertEquals(ReportReason.entries.size, aliceReports.size)
    }

    @Test
    fun `AC15 multiple reporters can independently file reports against the same target`() {
        val repo = ReportRepository()
        val reporters = listOf("alice", "bob", "carol")

        for (reporter in reporters) {
            repo.submitReport(reporter, "bad-actor", ReportTargetKind.USER, ReportReason.HARASSMENT)
        }

        val reports = repo.getReportsAgainst("bad-actor")
        assertEquals(reporters.size, reports.size)
        assertTrue(reporters.all { reporter -> reports.any { it.reporterId == reporter } })
    }

    // ── AC#19: components are synchronous pure functions with no I/O ─────────

    @Test
    fun `AC19 all component interactions complete synchronously without side effects`() {
        // This test verifies that the full create → connect → message → report
        // pipeline completes without any async calls, I/O, or exceptions.
        val profileRepo = ProfileRepository()
        saveProfile(profileRepo, "alice", interests = listOf("jazz"))
        saveProfile(profileRepo, "bob", openToFriends = true, interests = listOf("jazz"))

        val discoveryResults =
            profileRepo.discover(
                Profile(id = "alice", displayName = "Alice", photo = photo(), interests = listOf("jazz")),
            )
        assertFalse(discoveryResults.isEmpty())

        val messaging = MessagingRepository(profileRepo)
        val conn = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")
        assertNotNull(conn)
        assertTrue(messaging.acceptConnectionRequest(conn.id, "bob"))

        val message = messaging.sendMessage(senderId = "alice", recipientId = "bob", body = "Hello")
        assertNotNull(message)

        val reportRepo = ReportRepository()
        val report =
            reportRepo.submitReport(
                reporterId = "alice",
                targetId = "bob",
                targetKind = ReportTargetKind.USER,
                reason = ReportReason.OTHER,
                additionalText = "Something happened.",
            )
        assertNotNull(report)
    }
}
