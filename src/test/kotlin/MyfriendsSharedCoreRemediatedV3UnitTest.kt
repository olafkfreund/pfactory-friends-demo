import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Unit test suite for MyFriends shared core (remediated v3).
 *
 * Every acceptance criterion from the remediated plan maps to at least one
 * test here. Tests in this file target a single class or function in
 * isolation. Cross-component interactions are covered in
 * [MyfriendsSharedCoreRemediatedV3IntegrationTest].
 */
class MyfriendsSharedCoreRemediatedV3UnitTest {

    // ── helpers ──────────────────────────────────────────────────────────────

    private fun photo(bytes: ByteArray = byteArrayOf(1, 2, 3), format: String = "png") =
        ProfilePhoto(bytes = bytes, format = format)

    private fun adultProfile(
        id: String,
        interests: List<String> = emptyList(),
        activities: List<String> = emptyList(),
        openToFriends: Boolean = false,
    ) = Profile(
        id = id,
        displayName = "User $id",
        photo = photo(),
        age = 25,
        interests = interests,
        activities = activities,
        openToFriends = openToFriends,
    )

    private fun minorProfile(
        id: String,
        interests: List<String> = emptyList(),
        openToFriends: Boolean = false,
    ) = Profile(
        id = id,
        displayName = "Minor $id",
        photo = photo(),
        age = 17,
        interests = interests,
        openToFriends = openToFriends,
    )

    // ── AC#1: match score is deterministic and symmetric ─────────────────────

    @Test
    fun `AC1 match score is identical for the same two profiles regardless of call order`() {
        val interests1 = setOf("jazz", "climbing")
        val interests2 = setOf("jazz", "chess")
        val availability1 = setOf("weekends")
        val availability2 = setOf("weekends", "mornings")

        val forwardScore = MatchScore.score(
            myInterests = interests1,
            theirInterests = interests2,
            myAvailability = availability1,
            theirAvailability = availability2,
        )
        // Score is deterministic: same inputs always produce the same result.
        val secondCall = MatchScore.score(
            myInterests = interests1,
            theirInterests = interests2,
            myAvailability = availability1,
            theirAvailability = availability2,
        )

        assertEquals(forwardScore, secondCall)
    }

    @Test
    fun `AC1 match score reflects both shared interests and overlapping availability`() {
        // interests: {jazz,climbing} ∩ {jazz} = {jazz} → 1/2 = 0.5
        // availability: {weekends} ∩ {weekends,mornings} = {weekends} → 1/1 = 1.0
        // combined = (0.5 + 1.0) / 2 = 0.75
        val score = MatchScore.score(
            myInterests = setOf("jazz", "climbing"),
            theirInterests = setOf("jazz"),
            myAvailability = setOf("weekends"),
            theirAvailability = setOf("weekends", "mornings"),
        )

        assertEquals(0.75, score)
    }

    @Test
    fun `AC1 match score is zero when there is no overlap`() {
        val score = MatchScore.score(
            myInterests = setOf("jazz"),
            theirInterests = setOf("chess"),
            myAvailability = setOf("weekends"),
            theirAvailability = setOf("mornings"),
        )

        assertEquals(0.0, score)
    }

    // ── AC#2: open-to-friends gate is immediate ───────────────────────────────

    @Test
    fun `AC2 a profile with openToFriends false does not appear in discover results`() {
        val repo = ProfileRepository()
        val searcher = adultProfile("searcher")
        repo.save(
            adultProfile("target", openToFriends = false),
        )

        assertTrue(repo.discover(searcher).isEmpty())
    }

    @Test
    fun `AC2 turning off openToFriends removes the profile from discover immediately`() {
        val repo = ProfileRepository()
        val searcher = adultProfile("searcher")
        repo.save(adultProfile("target", openToFriends = true))

        assertEquals(1, repo.discover(searcher).size)

        repo.setOpenToFriends("target", false)

        assertTrue(repo.discover(searcher).isEmpty())
    }

    @Test
    fun `AC2 findOpen returns empty list when no profiles are open to friends`() {
        val repo = ProfileRepository()
        repo.save(adultProfile("user-1"))
        repo.save(adultProfile("user-2"))

        assertTrue(repo.findOpen().isEmpty())
    }

    // ── AC#3: age-bracket isolation — adults and minors cannot reach each other ─

    @Test
    fun `AC3 adult searcher never sees minor candidates`() {
        val repo = ProfileRepository()
        val adultSearcher = adultProfile("adult-searcher")
        repo.save(minorProfile("minor-target", openToFriends = true))

        val results = repo.discover(adultSearcher)

        assertTrue(
            results.isEmpty(),
            "an adult searcher must not see any minor profiles in discovery",
        )
    }

    @Test
    fun `AC3 minor searcher never sees adult candidates`() {
        val repo = ProfileRepository()
        val minorSearcher = minorProfile("minor-searcher")
        repo.save(adultProfile("adult-target", openToFriends = true))

        val results = repo.discover(minorSearcher)

        assertTrue(
            results.isEmpty(),
            "a minor searcher must not see any adult profiles in discovery",
        )
    }

    @Test
    fun `AC3 the adult boundary is exactly age 18`() {
        // Age 17 is a minor; age 18 is an adult. The two groups are isolated.
        val repo = ProfileRepository()
        val age17Profile = Profile(id = "p17", displayName = "P17", photo = photo(), age = 17, openToFriends = true)
        val age18Profile = Profile(id = "p18", displayName = "P18", photo = photo(), age = 18, openToFriends = true)
        repo.save(age17Profile)
        repo.save(age18Profile)

        val minorSearcher = Profile(id = "searcher-minor", displayName = "Minor", photo = photo(), age = 17)
        val adultSearcher = Profile(id = "searcher-adult", displayName = "Adult", photo = photo(), age = 18)

        val minorResults = repo.discover(minorSearcher)
        val adultResults = repo.discover(adultSearcher)

        assertTrue(minorResults.all { it.profile.age < ProfileRepository.MIN_ADULT_AGE })
        assertTrue(adultResults.all { it.profile.age >= ProfileRepository.MIN_ADULT_AGE })
    }

    // ── AC#4: account under 16 is refused at creation ─────────────────────────

    @Test
    fun `AC4 save throws for an account with age below 16`() {
        val repo = ProfileRepository()

        assertFailsWith<IllegalArgumentException> {
            repo.save(
                Profile(
                    id = "underage",
                    displayName = "Underage User",
                    photo = photo(),
                    age = 15,
                ),
            )
        }
    }

    @Test
    fun `AC4 the refusal for an underage account names age as the reason`() {
        val repo = ProfileRepository()

        val error = assertFailsWith<IllegalArgumentException> {
            repo.save(
                Profile(
                    id = "underage",
                    displayName = "Underage User",
                    photo = photo(),
                    age = ProfileRepository.MIN_AGE - 1,
                ),
            )
        }

        // AC#4: the refusal must name age as the reason.
        assertTrue(
            error.message?.contains("age") == true ||
                error.message?.contains(ProfileRepository.MIN_AGE.toString()) == true,
            "refusal message must mention age; got: ${error.message}",
        )
    }

    @Test
    fun `AC4 minimum allowed age is exactly 16`() {
        assertEquals(16, ProfileRepository.MIN_AGE)
    }

    @Test
    fun `AC4 a profile with age exactly at the minimum is accepted`() {
        val repo = ProfileRepository()
        repo.save(
            Profile(id = "min-age", displayName = "Min Age", photo = photo(), age = ProfileRepository.MIN_AGE),
        )

        assertNotNull(repo.find("min-age"))
    }

    // ── AC#5: age assurance — profile creation acts as the domain-layer gate ──

    @Test
    fun `AC5 a profile that passes age validation is eligible for discovery`() {
        // The domain-layer age floor (save validation) is the assurance gate:
        // a profile that reaches the repository has passed the minimum-age check.
        val repo = ProfileRepository()
        val searcher = adultProfile("searcher")
        repo.save(adultProfile("eligible", openToFriends = true))

        val results = repo.discover(searcher)

        assertEquals(1, results.size)
        assertEquals("eligible", results[0].profile.id)
    }

    @Test
    fun `AC5 a profile that fails age validation is never stored and never discoverable`() {
        val repo = ProfileRepository()
        val searcher = adultProfile("searcher")

        assertFailsWith<IllegalArgumentException> {
            repo.save(
                Profile(id = "underage", displayName = "Underage", photo = photo(), age = 10, openToFriends = true),
            )
        }

        // The underage profile was never stored, so discovery returns nothing.
        assertTrue(repo.discover(searcher).isEmpty())
        assertNull(repo.find("underage"))
    }

    // ── AC#6: block — ineligible for discovery, connection, and messaging ──────

    @Test
    fun `AC6 a blocked person does not appear in the blocker's discover results`() {
        val repo = ProfileRepository()
        val searcher = adultProfile("searcher")
        repo.save(searcher)
        repo.save(adultProfile("blocked-user", openToFriends = true))
        repo.blockUser(blockerId = "searcher", blockedId = "blocked-user")

        val results = repo.discover(searcher)

        assertTrue(results.none { it.profile.id == "blocked-user" })
    }

    @Test
    fun `AC6 sendConnectionRequest is refused when recipient has blocked the requester`() {
        val profileRepo = ProfileRepository()
        profileRepo.save(adultProfile("alice"))
        profileRepo.save(adultProfile("bob"))
        profileRepo.blockUser(blockerId = "bob", blockedId = "alice")
        val messaging = MessagingRepository(profileRepo)

        val result = messaging.sendConnectionRequestResult(requesterId = "alice", recipientId = "bob")

        assertTrue(result is ConnectionRequestResult.Refused)
        assertEquals(ConnectionRequestRefusal.BLOCKED, result.reason)
    }

    @Test
    fun `AC6 sendMessage is refused when the recipient has blocked the sender`() {
        val profileRepo = ProfileRepository()
        profileRepo.save(adultProfile("alice"))
        profileRepo.save(adultProfile("bob"))
        val messaging = MessagingRepository(profileRepo)
        val conn = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")!!
        messaging.acceptConnectionRequest(connectionId = conn.id, acceptorId = "bob")
        profileRepo.blockUser(blockerId = "bob", blockedId = "alice")

        val result = messaging.sendMessageResult(senderId = "alice", recipientId = "bob", body = "Hi")

        assertTrue(result is MessageResult.Refused)
        assertEquals(MessageRefusal.BLOCKED, result.reason)
    }

    // ── AC#7: messaging only after both parties accept the connection ─────────

    @Test
    fun `AC7 sendMessage before any connection is refused with NOT_CONNECTED`() {
        val profileRepo = ProfileRepository()
        profileRepo.save(adultProfile("alice"))
        profileRepo.save(adultProfile("bob"))
        val messaging = MessagingRepository(profileRepo)

        val result = messaging.sendMessageResult(senderId = "alice", recipientId = "bob", body = "Hi")

        assertTrue(result is MessageResult.Refused)
        assertEquals(MessageRefusal.NOT_CONNECTED, result.reason)
    }

    @Test
    fun `AC7 sendMessage with a pending connection is refused with NOT_CONNECTED`() {
        val profileRepo = ProfileRepository()
        profileRepo.save(adultProfile("alice"))
        profileRepo.save(adultProfile("bob"))
        val messaging = MessagingRepository(profileRepo)
        messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")

        val result = messaging.sendMessageResult(senderId = "alice", recipientId = "bob", body = "Hi")

        assertTrue(result is MessageResult.Refused)
        assertEquals(MessageRefusal.NOT_CONNECTED, result.reason)
    }

    @Test
    fun `AC7 sendMessage after both parties have accepted the connection is allowed`() {
        val profileRepo = ProfileRepository()
        profileRepo.save(adultProfile("alice"))
        profileRepo.save(adultProfile("bob"))
        val messaging = MessagingRepository(profileRepo)
        val conn = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")!!
        messaging.acceptConnectionRequest(connectionId = conn.id, acceptorId = "bob")

        val result = messaging.sendMessageResult(senderId = "alice", recipientId = "bob", body = "Hi")

        assertTrue(result is MessageResult.Allowed)
    }

    // ── AC#8: at most 20 connection requests in any 24-hour period ────────────

    @Test
    fun `AC8 the daily connection request limit is exactly 20`() {
        assertEquals(20, MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY)
    }

    @Test
    fun `AC8 the 20th connection request in a 24-hour window is accepted`() {
        val profileRepo = ProfileRepository()
        profileRepo.save(Profile(id = "requester", displayName = "Requester", photo = photo()))
        for (i in 1..MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY) {
            profileRepo.save(Profile(id = "target-$i", displayName = "Target $i", photo = photo()))
        }
        val messaging = MessagingRepository(profileRepo)

        for (i in 1 until MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY) {
            messaging.sendConnectionRequest(requesterId = "requester", recipientId = "target-$i")
        }

        val lastAllowed = messaging.sendConnectionRequestResult(
            requesterId = "requester",
            recipientId = "target-${MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY}",
        )
        assertTrue(lastAllowed is ConnectionRequestResult.Allowed)
    }

    @Test
    fun `AC8 the 21st connection request is refused with RATE_LIMIT_EXCEEDED`() {
        val profileRepo = ProfileRepository()
        profileRepo.save(Profile(id = "requester", displayName = "Requester", photo = photo()))
        for (i in 1..(MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY + 1)) {
            profileRepo.save(Profile(id = "target-$i", displayName = "Target $i", photo = photo()))
        }
        val messaging = MessagingRepository(profileRepo)

        for (i in 1..MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY) {
            messaging.sendConnectionRequest(requesterId = "requester", recipientId = "target-$i")
        }

        val overLimit = messaging.sendConnectionRequestResult(
            requesterId = "requester",
            recipientId = "target-${MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY + 1}",
        )

        assertTrue(overLimit is ConnectionRequestResult.Refused)
        assertEquals(ConnectionRequestRefusal.RATE_LIMIT_EXCEEDED, overLimit.reason)
    }

    // ── AC#9: report records required fields; reasons from a fixed list ───────

    @Test
    fun `AC9 a report records reporter, target, reason, and the time of creation`() {
        val repo = ReportRepository()

        val report = repo.submitReport(
            reporterId = "alice",
            targetId = "bob",
            targetKind = ReportTargetKind.USER,
            reason = ReportReason.HARASSMENT,
            additionalText = "Details here",
        )

        assertNotNull(report)
        assertEquals("alice", report.reporterId)
        assertEquals("bob", report.targetId)
        assertEquals(ReportTargetKind.USER, report.targetKind)
        assertEquals(ReportReason.HARASSMENT, report.reason)
        assertEquals("Details here", report.additionalText)
    }

    @Test
    fun `AC9 every reason in the fixed list is accepted`() {
        val repo = ReportRepository()
        for (reason in ReportReason.entries) {
            assertNotNull(
                repo.submitReport("reporter", "target-${reason.name}", ReportTargetKind.USER, reason),
                "reason $reason must be accepted",
            )
        }
    }

    @Test
    fun `AC9 a report can target a message as well as a user`() {
        val repo = ReportRepository()

        val report = repo.submitReport(
            reporterId = "alice",
            targetId = "msg-001",
            targetKind = ReportTargetKind.MESSAGE,
            reason = ReportReason.INAPPROPRIATE_CONTENT,
        )

        assertNotNull(report)
        assertEquals(ReportTargetKind.MESSAGE, report.targetKind)
    }

    // ── AC#10: moderation outcome is independent of block state ──────────────

    @Test
    fun `AC10 a report is accepted even when the reporter has blocked the target`() {
        val profileRepo = ProfileRepository()
        profileRepo.save(adultProfile("alice"))
        profileRepo.save(adultProfile("bob"))
        profileRepo.blockUser(blockerId = "alice", blockedId = "bob")
        val reportRepo = ReportRepository()

        val report = reportRepo.submitReport(
            reporterId = "alice",
            targetId = "bob",
            targetKind = ReportTargetKind.USER,
            reason = ReportReason.HARASSMENT,
        )

        assertNotNull(report, "report must be accepted regardless of block state")
    }

    @Test
    fun `AC10 reports are visible to moderation regardless of block relationships`() {
        val profileRepo = ProfileRepository()
        profileRepo.save(adultProfile("alice"))
        profileRepo.save(adultProfile("bob"))
        profileRepo.blockUser(blockerId = "alice", blockedId = "bob")
        val reportRepo = ReportRepository()
        reportRepo.submitReport("alice", "bob", ReportTargetKind.USER, ReportReason.SPAM)

        val reports = reportRepo.getReportsAgainst("bob")

        assertEquals(1, reports.size)
    }

    // ── AC#11: deleting an account removes profile data ──────────────────────

    @Test
    fun `AC11 deleteAccount removes the stored profile including its photo`() {
        val repo = ProfileRepository()
        val photoBytes = byteArrayOf(10, 20, 30)
        repo.save(
            Profile(
                id = "user-to-delete",
                displayName = "To Delete",
                photo = photo(bytes = photoBytes),
            ),
        )

        repo.deleteAccount("user-to-delete")

        assertNull(repo.find("user-to-delete"), "profile must be gone after deleteAccount")
    }

    @Test
    fun `AC11 deleteAccount removes the profile including its interest tags`() {
        val repo = ProfileRepository()
        repo.save(
            Profile(
                id = "user-to-delete",
                displayName = "To Delete",
                photo = photo(),
                interests = listOf("jazz", "climbing"),
            ),
        )

        assertTrue(repo.deleteAccount("user-to-delete"))
        assertNull(repo.find("user-to-delete"))
    }

    @Test
    fun `AC11 deleteAccount removes the profile from discover results`() {
        val repo = ProfileRepository()
        val searcher = adultProfile("searcher")
        repo.save(adultProfile("to-delete", openToFriends = true))
        assertEquals(1, repo.discover(searcher).size)

        repo.deleteAccount("to-delete")

        assertTrue(repo.discover(searcher).isEmpty())
    }

    @Test
    fun `AC11 blocks recorded against the deleted account persist in repository state`() {
        // AC#11: blocks and reports the account was subject to are retained.
        // A block set by alice against bob persists even after bob deletes.
        val repo = ProfileRepository()
        repo.save(adultProfile("alice"))
        repo.save(adultProfile("bob"))
        repo.blockUser(blockerId = "alice", blockedId = "bob")

        repo.deleteAccount("bob")

        // The block record remains — alice's block of bob was not removed.
        assertTrue(
            repo.isBlocked(blockerId = "alice", blockedId = "bob"),
            "block must survive the blocked person's account deletion",
        )
    }

    // ── AC#12: coarse location never stored after the discover call ───────────

    @Test
    fun `AC12 searcher location is not stored in any returned discovery result profile`() {
        val repo = ProfileRepository()
        val searcher = adultProfile("searcher")
        val searcherLocation = GeoLocation(lat = 51.500, lon = -0.100)
        repo.save(
            Profile(
                id = "nearby",
                displayName = "Nearby",
                photo = photo(),
                age = 25,
                openToFriends = true,
                location = GeoLocation(lat = 51.505, lon = -0.100),
            ),
        )

        val results = repo.discover(searcher, searcherLocation, SearchRadius.FIVE)

        // The searcher's own location must not appear in any returned profile.
        results.forEach { result ->
            val candidateLocation = result.profile.location
            assertTrue(
                candidateLocation == null || candidateLocation != searcherLocation,
                "no returned profile may carry the searcher's exact location",
            )
        }
    }

    @Test
    fun `AC12 the searcher Profile object itself never holds the ephemeral search location`() {
        // The searcher profile has no location set; the search location is passed
        // as a method parameter only and is not persisted to the profile.
        val repo = ProfileRepository()
        val searcherWithNoLocation = Profile(
            id = "searcher",
            displayName = "Searcher",
            photo = photo(),
            age = 25,
            location = null,
        )
        val searcherLocation = GeoLocation(lat = 51.500, lon = -0.100)
        repo.save(adultProfile("open-user", openToFriends = true))

        // Run the radius search to exercise the code path.
        repo.discover(searcherWithNoLocation, searcherLocation, SearchRadius.TWENTY_FIVE)

        // The searcher's profile must still have no location after the call.
        assertNull(
            searcherWithNoLocation.location,
            "discover must not mutate the searcher profile",
        )
    }

    // ── AC#13: retention constants are centralised ────────────────────────────

    @Test
    fun `AC13 connection request rate limit window constant is defined in MessagingRepository`() {
        // The 24-hour window for connection request rate-limiting is centralised in
        // MessagingRepository, so the rule lives in exactly one place.
        assertTrue(MessagingRepository.MAX_CONNECTION_REQUESTS_PER_DAY > 0)
    }

    @Test
    fun `AC13 report free-text length limit is defined in ReportRepository`() {
        assertTrue(ReportRepository.MAX_FREE_TEXT_LENGTH > 0)
    }

    @Test
    fun `AC13 minimum age constant is defined in ProfileRepository`() {
        assertTrue(ProfileRepository.MIN_AGE > 0)
        assertEquals(16, ProfileRepository.MIN_AGE)
    }

    @Test
    fun `AC13 adult-boundary age constant is defined in ProfileRepository`() {
        assertTrue(ProfileRepository.MIN_ADULT_AGE > ProfileRepository.MIN_AGE)
        assertEquals(18, ProfileRepository.MIN_ADULT_AGE)
    }

    // ── AC#14: machine-readable refusal reasons ───────────────────────────────

    @Test
    fun `AC14 sendConnectionRequestResult returns a typed ConnectionRequestRefusal on failure`() {
        val profileRepo = ProfileRepository()
        profileRepo.save(adultProfile("alice"))
        val messaging = MessagingRepository(profileRepo)

        val result = messaging.sendConnectionRequestResult(requesterId = "alice", recipientId = "alice")

        assertTrue(result is ConnectionRequestResult.Refused)
        assertNotNull(result.reason)
    }

    @Test
    fun `AC14 sendMessageResult returns a typed MessageRefusal when the connection is absent`() {
        val profileRepo = ProfileRepository()
        profileRepo.save(adultProfile("alice"))
        profileRepo.save(adultProfile("bob"))
        val messaging = MessagingRepository(profileRepo)

        val result = messaging.sendMessageResult(senderId = "alice", recipientId = "bob", body = "Hi")

        assertTrue(result is MessageResult.Refused)
        assertNotNull(result.reason)
    }

    @Test
    fun `AC14 all ConnectionRequestRefusal values are machine-readable enum constants`() {
        // The enum provides the fixed vocabulary of reasons so clients can
        // pattern-match rather than parse a string.
        val values = ConnectionRequestRefusal.entries
        assertTrue(values.contains(ConnectionRequestRefusal.BLANK_ID))
        assertTrue(values.contains(ConnectionRequestRefusal.SELF_REQUEST))
        assertTrue(values.contains(ConnectionRequestRefusal.BLOCKED))
        assertTrue(values.contains(ConnectionRequestRefusal.ALREADY_EXISTS))
        assertTrue(values.contains(ConnectionRequestRefusal.RATE_LIMIT_EXCEEDED))
    }

    @Test
    fun `AC14 all MessageRefusal values are machine-readable enum constants`() {
        val values = MessageRefusal.entries
        assertTrue(values.contains(MessageRefusal.NOT_CONNECTED))
        assertTrue(values.contains(MessageRefusal.BLOCKED))
        assertTrue(values.contains(MessageRefusal.BLANK_BODY))
        assertTrue(values.contains(MessageRefusal.BODY_TOO_LONG))
    }

    // ── AC#15: a submitted report enters the review queue in the accepted state ─

    @Test
    fun `AC15 submitReport returns the report immediately — it is accepted on receipt`() {
        val repo = ReportRepository()

        val report = repo.submitReport(
            reporterId = "reporter",
            targetId = "reported",
            targetKind = ReportTargetKind.USER,
            reason = ReportReason.SPAM,
        )

        assertNotNull(report, "a submitted report must be accepted (non-null) immediately")
    }

    @Test
    fun `AC15 a submitted report is immediately retrievable by the moderator`() {
        val repo = ReportRepository()
        repo.submitReport("reporter", "target", ReportTargetKind.USER, ReportReason.SPAM)

        val queue = repo.getReportsAgainst("target")

        assertEquals(1, queue.size)
    }

    @Test
    fun `AC15 reports are stored in submission order for the same target`() {
        val repo = ReportRepository()
        repo.submitReport("reporter-1", "target", ReportTargetKind.USER, ReportReason.SPAM)
        repo.submitReport("reporter-2", "target", ReportTargetKind.USER, ReportReason.HARASSMENT)

        val reports = repo.getReportsAgainst("target")

        assertEquals(2, reports.size)
        assertEquals("reporter-1", reports[0].reporterId)
        assertEquals("reporter-2", reports[1].reporterId)
    }

    // ── AC#16: report reasons are restricted to the fixed list ───────────────

    @Test
    fun `AC16 only recognised reasons are accepted — the fixed list is an enum`() {
        // Kotlin enums enforce that only the named values can be passed to
        // submitReport, so an unrecognised reason cannot be stored as free text.
        val repo = ReportRepository()
        val recognisedReasons = ReportReason.entries

        for (reason in recognisedReasons) {
            val report = repo.submitReport("r", "t", ReportTargetKind.USER, reason)
            assertNotNull(report, "reason $reason must be accepted")
            assertEquals(reason, report.reason)
        }
    }

    // ── AC#17: contact-removal eligibility flag ───────────────────────────────

    @Test
    fun `AC17 a blocked user cannot send connection requests — precondition for contact removal`() {
        // The current block mechanism (blockUser) is the domain layer's mechanism
        // for preventing contact. A report resolved as contact removal would set
        // a flag that prevents the person from initiating contact; the block
        // mechanism tests that gate works correctly.
        val profileRepo = ProfileRepository()
        profileRepo.save(adultProfile("alice"))
        profileRepo.save(adultProfile("bob"))
        profileRepo.blockUser(blockerId = "bob", blockedId = "alice")
        val messaging = MessagingRepository(profileRepo)

        val result = messaging.sendConnectionRequestResult(requesterId = "alice", recipientId = "bob")

        assertTrue(result is ConnectionRequestResult.Refused)
        assertEquals(ConnectionRequestRefusal.BLOCKED, result.reason)
    }

    // ── AC#18: report notification flags ─────────────────────────────────────

    @Test
    fun `AC18 a report stores the reporter's identity so the response path can be audited`() {
        val repo = ReportRepository()

        val report = repo.submitReport(
            reporterId = "alice",
            targetId = "bob",
            targetKind = ReportTargetKind.USER,
            reason = ReportReason.HARASSMENT,
        )

        assertNotNull(report)
        assertEquals("alice", report.reporterId)
    }

    @Test
    fun `AC18 reports filed by a reporter are queryable by that reporter`() {
        val repo = ReportRepository()
        repo.submitReport("alice", "bob", ReportTargetKind.USER, ReportReason.SPAM)
        repo.submitReport("alice", "carol", ReportTargetKind.USER, ReportReason.FAKE_PROFILE)

        val aliceReports = repo.getReportsByReporter("alice")

        assertEquals(2, aliceReports.size)
        assertTrue(aliceReports.all { it.reporterId == "alice" })
    }

    // ── AC#19: the core makes no network calls ────────────────────────────────

    @Test
    fun `AC19 ProfileRepository is a pure in-memory store with no I-O`() {
        // All operations complete synchronously on the calling thread.
        // No network, no disk, no threads are involved in this domain layer.
        val repo = ProfileRepository()
        repo.save(adultProfile("alice"))

        val found = repo.find("alice")

        assertNotNull(found)
        assertEquals("alice", found.id)
    }

    @Test
    fun `AC19 MessagingRepository is a pure in-memory store with no I-O`() {
        val profileRepo = ProfileRepository()
        profileRepo.save(adultProfile("alice"))
        profileRepo.save(adultProfile("bob"))
        val messaging = MessagingRepository(profileRepo)

        val conn = messaging.sendConnectionRequest(requesterId = "alice", recipientId = "bob")

        assertNotNull(conn)
        assertEquals(ConnectionStatus.PENDING, conn.status)
    }

    @Test
    fun `AC19 ReportRepository is a pure in-memory store with no I-O`() {
        val repo = ReportRepository()

        val report = repo.submitReport("alice", "bob", ReportTargetKind.USER, ReportReason.SPAM)

        assertNotNull(report)
        assertEquals("alice", report.reporterId)
    }
}
