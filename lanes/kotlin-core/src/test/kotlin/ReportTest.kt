import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class ReportTest {

    // ── submitReport: user target ─────────────────────────────────────────

    @Test
    fun `submitReport for a user with valid arguments returns the persisted report`() {
        val repo = ReportRepository()

        val report = repo.submitReport(
            reporterId = "alice",
            targetId = "bob",
            targetKind = ReportTargetKind.USER,
            reason = ReportReason.SPAM,
        )

        assertNotNull(report)
        assertEquals("alice", report.reporterId)
        assertEquals("bob", report.targetId)
        assertEquals(ReportTargetKind.USER, report.targetKind)
        assertEquals(ReportReason.SPAM, report.reason)
        assertEquals("", report.additionalText)
    }

    // ── submitReport: message target ──────────────────────────────────────

    @Test
    fun `submitReport for a message with valid arguments returns the persisted report`() {
        val repo = ReportRepository()

        val report = repo.submitReport(
            reporterId = "alice",
            targetId = "msg-42",
            targetKind = ReportTargetKind.MESSAGE,
            reason = ReportReason.HARASSMENT,
        )

        assertNotNull(report)
        assertEquals(ReportTargetKind.MESSAGE, report.targetKind)
        assertEquals("msg-42", report.targetId)
    }

    // ── submitReport: blank id validation ─────────────────────────────────

    @Test
    fun `submitReport with a blank reporterId returns null`() {
        val repo = ReportRepository()

        assertNull(
            repo.submitReport(
                reporterId = "   ",
                targetId = "bob",
                targetKind = ReportTargetKind.USER,
                reason = ReportReason.SPAM,
            )
        )
    }

    @Test
    fun `submitReport with a blank targetId returns null`() {
        val repo = ReportRepository()

        assertNull(
            repo.submitReport(
                reporterId = "alice",
                targetId = "",
                targetKind = ReportTargetKind.USER,
                reason = ReportReason.SPAM,
            )
        )
    }

    // ── submitReport: additionalText ──────────────────────────────────────

    @Test
    fun `submitReport stores the trimmed additional text`() {
        val repo = ReportRepository()

        val report = repo.submitReport(
            reporterId = "alice",
            targetId = "bob",
            targetKind = ReportTargetKind.USER,
            reason = ReportReason.OTHER,
            additionalText = "  extra context  ",
        )

        assertNotNull(report)
        assertEquals("extra context", report.additionalText)
    }

    @Test
    fun `submitReport with additional text at the maximum length is accepted`() {
        val repo = ReportRepository()
        val maxText = "a".repeat(ReportRepository.MAX_FREE_TEXT_LENGTH)

        val report = repo.submitReport(
            reporterId = "alice",
            targetId = "bob",
            targetKind = ReportTargetKind.USER,
            reason = ReportReason.SPAM,
            additionalText = maxText,
        )

        assertNotNull(report)
        assertEquals(maxText, report.additionalText)
    }

    @Test
    fun `submitReport with additional text one character over the maximum length returns null`() {
        val repo = ReportRepository()
        val tooLong = "a".repeat(ReportRepository.MAX_FREE_TEXT_LENGTH + 1)

        assertNull(
            repo.submitReport(
                reporterId = "alice",
                targetId = "bob",
                targetKind = ReportTargetKind.USER,
                reason = ReportReason.SPAM,
                additionalText = tooLong,
            )
        )
    }

    // ── submitReport: each reason is accepted ─────────────────────────────

    @Test
    fun `submitReport accepts each report reason`() {
        val repo = ReportRepository()
        for (reason in ReportReason.entries) {
            assertNotNull(
                repo.submitReport(
                    reporterId = "alice",
                    targetId = "target-${reason.name}",
                    targetKind = ReportTargetKind.USER,
                    reason = reason,
                ),
                "reason $reason should be accepted",
            )
        }
    }

    // ── getReportsAgainst ─────────────────────────────────────────────────

    @Test
    fun `getReportsAgainst returns all reports for the given target`() {
        val repo = ReportRepository()
        repo.submitReport("alice", "bob", ReportTargetKind.USER, ReportReason.SPAM)
        repo.submitReport("carol", "bob", ReportTargetKind.USER, ReportReason.HARASSMENT)

        val reports = repo.getReportsAgainst("bob")

        assertEquals(2, reports.size)
        assertTrue(reports.all { it.targetId == "bob" })
    }

    @Test
    fun `getReportsAgainst returns an empty list when no reports have been filed against that target`() {
        val repo = ReportRepository()

        assertTrue(repo.getReportsAgainst("bob").isEmpty())
    }

    @Test
    fun `getReportsAgainst does not include reports for a different target`() {
        val repo = ReportRepository()
        repo.submitReport("alice", "bob", ReportTargetKind.USER, ReportReason.SPAM)
        repo.submitReport("alice", "carol", ReportTargetKind.USER, ReportReason.SPAM)

        val reportsAgainstBob = repo.getReportsAgainst("bob")

        assertEquals(1, reportsAgainstBob.size)
        assertEquals("bob", reportsAgainstBob[0].targetId)
    }

    // ── getReportsByReporter ──────────────────────────────────────────────

    @Test
    fun `getReportsByReporter returns all reports filed by the given reporter`() {
        val repo = ReportRepository()
        repo.submitReport("alice", "bob", ReportTargetKind.USER, ReportReason.SPAM)
        repo.submitReport("alice", "carol", ReportTargetKind.USER, ReportReason.HARASSMENT)
        repo.submitReport("bob", "carol", ReportTargetKind.USER, ReportReason.SPAM)

        val aliceReports = repo.getReportsByReporter("alice")

        assertEquals(2, aliceReports.size)
        assertTrue(aliceReports.all { it.reporterId == "alice" })
    }

    @Test
    fun `getReportsByReporter returns an empty list when the reporter has filed no reports`() {
        val repo = ReportRepository()

        assertTrue(repo.getReportsByReporter("alice").isEmpty())
    }

    // ── duplicate reports ─────────────────────────────────────────────────

    @Test
    fun `submitReport allows multiple reports from the same reporter against the same target`() {
        // De-duplication is an operational concern; the domain layer records
        // every submission as a distinct report.
        val repo = ReportRepository()
        repo.submitReport("alice", "bob", ReportTargetKind.USER, ReportReason.SPAM)
        repo.submitReport("alice", "bob", ReportTargetKind.USER, ReportReason.HARASSMENT)

        assertEquals(2, repo.getReportsAgainst("bob").size)
    }

    // ── report ids ────────────────────────────────────────────────────────

    @Test
    fun `each submitted report gets a distinct id`() {
        val repo = ReportRepository()
        val r1 = repo.submitReport("alice", "bob", ReportTargetKind.USER, ReportReason.SPAM)!!
        val r2 = repo.submitReport("alice", "carol", ReportTargetKind.USER, ReportReason.SPAM)!!

        assertTrue(r1.id != r2.id)
    }
}
