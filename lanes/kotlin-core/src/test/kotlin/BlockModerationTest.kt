import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/**
 * Tests for AC#10: a person can block users, and the moderation outcome of a
 * report is independent of whether either person has blocked the other.
 *
 * Two aspects are verified here:
 *
 * 1. A user can block other users (the block is recorded and queryable).
 * 2. The report pipeline—from submission through to moderation retrieval—is
 *    completely independent of block relationships: a report filed by a user
 *    who has blocked the target, or by a user who has been blocked by the
 *    target, is accepted and visible to moderators exactly as any other report
 *    would be.  This matters because a moderator reviewing a report must see
 *    all reports to make an unbiased decision; the block state between the
 *    parties is personal to each user and must not silently hide a report or
 *    influence its priority.
 *
 * The `ReportRepository` intentionally has no reference to `ProfileRepository`
 * and performs no block check; these tests confirm that the design holds.
 */
class BlockModerationTest {
    // ── helpers ──────────────────────────────────────────────────────────────

    private fun validPhoto(): ProfilePhoto = ProfilePhoto(bytes = byteArrayOf(1, 2, 3, 4), format = "png")

    /** Returns a saved profile with the given [id]. */
    private fun savedProfile(
        repo: ProfileRepository,
        id: String,
    ): Profile {
        val profile = Profile(id = id, displayName = "User $id", photo = validPhoto())
        repo.save(profile)
        return profile
    }

    // ── AC#10 part 1: a person can block users ────────────────────────────

    @Test
    fun `blockUser records the block so isBlocked returns true for the same pair`() {
        val profileRepo = ProfileRepository()
        savedProfile(profileRepo, "alice")
        savedProfile(profileRepo, "bob")

        assertTrue(profileRepo.blockUser(blockerId = "alice", blockedId = "bob"))
        assertTrue(profileRepo.isBlocked(blockerId = "alice", blockedId = "bob"))
    }

    @Test
    fun `a person can block multiple users and all blocks are independently recorded`() {
        val profileRepo = ProfileRepository()
        savedProfile(profileRepo, "alice")
        savedProfile(profileRepo, "bob")
        savedProfile(profileRepo, "carol")

        profileRepo.blockUser(blockerId = "alice", blockedId = "bob")
        profileRepo.blockUser(blockerId = "alice", blockedId = "carol")

        assertTrue(profileRepo.isBlocked(blockerId = "alice", blockedId = "bob"))
        assertTrue(profileRepo.isBlocked(blockerId = "alice", blockedId = "carol"))
    }

    // ── AC#10 part 2: moderation outcome is independent of blocks ─────────

    @Test
    fun `a report is accepted when the reporter has blocked the reported person`() {
        // Alice blocks Bob, then files a report against Bob.
        // The block must not prevent the report from being stored.
        val profileRepo = ProfileRepository()
        savedProfile(profileRepo, "alice")
        savedProfile(profileRepo, "bob")
        profileRepo.blockUser(blockerId = "alice", blockedId = "bob")

        val reportRepo = ReportRepository()
        val report =
            reportRepo.submitReport(
                reporterId = "alice",
                targetId = "bob",
                targetKind = ReportTargetKind.USER,
                reason = ReportReason.HARASSMENT,
            )

        assertNotNull(report, "report must be accepted even when alice has blocked bob")
        assertEquals("alice", report.reporterId)
        assertEquals("bob", report.targetId)
    }

    @Test
    fun `a report is accepted when the reported person has blocked the reporter`() {
        // Bob blocks Alice, but Alice can still file a report against Bob.
        val profileRepo = ProfileRepository()
        savedProfile(profileRepo, "alice")
        savedProfile(profileRepo, "bob")
        profileRepo.blockUser(blockerId = "bob", blockedId = "alice")

        val reportRepo = ReportRepository()
        val report =
            reportRepo.submitReport(
                reporterId = "alice",
                targetId = "bob",
                targetKind = ReportTargetKind.USER,
                reason = ReportReason.SPAM,
            )

        assertNotNull(report, "report must be accepted even when bob has blocked alice")
        assertEquals("alice", report.reporterId)
        assertEquals("bob", report.targetId)
    }

    @Test
    fun `a report is accepted when both parties have mutually blocked each other`() {
        // Both alice→bob and bob→alice blocks are active; reporting must still work.
        val profileRepo = ProfileRepository()
        savedProfile(profileRepo, "alice")
        savedProfile(profileRepo, "bob")
        profileRepo.blockUser(blockerId = "alice", blockedId = "bob")
        profileRepo.blockUser(blockerId = "bob", blockedId = "alice")

        val reportRepo = ReportRepository()
        val report =
            reportRepo.submitReport(
                reporterId = "alice",
                targetId = "bob",
                targetKind = ReportTargetKind.USER,
                reason = ReportReason.INAPPROPRIATE_CONTENT,
            )

        assertNotNull(report, "report must be accepted even with mutual blocks")
    }

    @Test
    fun `getReportsAgainst returns reports regardless of any block between the parties`() {
        // Three reporters each block bob, then each files a report against bob.
        // A moderator querying for all reports against bob must see all three,
        // not a filtered view based on the block state of any reporter.
        val profileRepo = ProfileRepository()
        savedProfile(profileRepo, "alice")
        savedProfile(profileRepo, "carol")
        savedProfile(profileRepo, "dave")
        savedProfile(profileRepo, "bob")
        profileRepo.blockUser(blockerId = "alice", blockedId = "bob")
        profileRepo.blockUser(blockerId = "carol", blockedId = "bob")
        profileRepo.blockUser(blockerId = "dave", blockedId = "bob")

        val reportRepo = ReportRepository()
        reportRepo.submitReport("alice", "bob", ReportTargetKind.USER, ReportReason.SPAM)
        reportRepo.submitReport("carol", "bob", ReportTargetKind.USER, ReportReason.HARASSMENT)
        reportRepo.submitReport("dave", "bob", ReportTargetKind.USER, ReportReason.FAKE_PROFILE)

        val reports = reportRepo.getReportsAgainst("bob")

        assertEquals(
            3,
            reports.size,
            "all three reports must be visible to a moderator regardless of blocks",
        )
        assertTrue(reports.all { it.targetId == "bob" })
    }

    @Test
    fun `getReportsAgainst is not affected by the reported person having blocked reporters`() {
        // Bob blocks all three reporters.  The moderation view must still show
        // every report filed against bob.
        val profileRepo = ProfileRepository()
        savedProfile(profileRepo, "alice")
        savedProfile(profileRepo, "carol")
        savedProfile(profileRepo, "bob")
        profileRepo.blockUser(blockerId = "bob", blockedId = "alice")
        profileRepo.blockUser(blockerId = "bob", blockedId = "carol")

        val reportRepo = ReportRepository()
        reportRepo.submitReport("alice", "bob", ReportTargetKind.USER, ReportReason.SPAM)
        reportRepo.submitReport("carol", "bob", ReportTargetKind.USER, ReportReason.HARASSMENT)

        val reports = reportRepo.getReportsAgainst("bob")

        assertEquals(
            2,
            reports.size,
            "all reports must be visible regardless of bob having blocked the reporters",
        )
    }

    @Test
    fun `a report filed before a block is established remains visible to moderators after the block`() {
        // The report was filed first; the block was added later.  Blocks are
        // prospective: they restrict future interactions (discovery, messaging,
        // connection requests) but must not retroactively hide prior reports
        // from the moderation view.
        val profileRepo = ProfileRepository()
        savedProfile(profileRepo, "alice")
        savedProfile(profileRepo, "bob")

        val reportRepo = ReportRepository()
        val report =
            reportRepo.submitReport(
                reporterId = "alice",
                targetId = "bob",
                targetKind = ReportTargetKind.USER,
                reason = ReportReason.HARASSMENT,
            )
        assertNotNull(report)

        // Block established after the report.
        profileRepo.blockUser(blockerId = "alice", blockedId = "bob")

        // The report is still visible.
        val reports = reportRepo.getReportsAgainst("bob")
        assertEquals(1, reports.size, "pre-block report must still be visible after the block")
        assertEquals(report.id, reports[0].id)
    }

    @Test
    fun `block state between reporter and target does not affect reports filed about messages`() {
        // A report about a specific message (e.g. harmful content) must reach
        // moderation even when the parties have blocked each other.
        val profileRepo = ProfileRepository()
        savedProfile(profileRepo, "alice")
        savedProfile(profileRepo, "bob")
        profileRepo.blockUser(blockerId = "alice", blockedId = "bob")
        profileRepo.blockUser(blockerId = "bob", blockedId = "alice")

        val reportRepo = ReportRepository()
        val report =
            reportRepo.submitReport(
                reporterId = "alice",
                targetId = "msg-42",
                targetKind = ReportTargetKind.MESSAGE,
                reason = ReportReason.INAPPROPRIATE_CONTENT,
            )

        assertNotNull(report, "message report must be accepted regardless of mutual blocks")
        assertEquals(ReportTargetKind.MESSAGE, report.targetKind)
        assertEquals("msg-42", report.targetId)
    }
}
