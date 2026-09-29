import XCTest
@testable import MyFriendsCore

final class ReportTests: XCTestCase {

    // MARK: - submitReport: user target

    func testSubmitReportForAUserWithValidArgumentsReturnsThePersistedReport() {
        let repo = ReportRepository()

        let report = repo.submitReport(
            reporterId: "alice",
            targetId: "bob",
            targetKind: .user,
            reason: .spam
        )

        XCTAssertNotNil(report)
        XCTAssertEqual(report?.reporterId, "alice")
        XCTAssertEqual(report?.targetId, "bob")
        XCTAssertEqual(report?.targetKind, .user)
        XCTAssertEqual(report?.reason, .spam)
        XCTAssertEqual(report?.additionalText, "")
    }

    // MARK: - submitReport: message target

    func testSubmitReportForAMessageWithValidArgumentsReturnsThePersistedReport() {
        let repo = ReportRepository()

        let report = repo.submitReport(
            reporterId: "alice",
            targetId: "msg-42",
            targetKind: .message,
            reason: .harassment
        )

        XCTAssertNotNil(report)
        XCTAssertEqual(report?.targetKind, .message)
        XCTAssertEqual(report?.targetId, "msg-42")
    }

    // MARK: - submitReport: blank id validation

    func testSubmitReportWithABlankReporterIdReturnsNil() {
        let repo = ReportRepository()

        XCTAssertNil(repo.submitReport(
            reporterId: "   ",
            targetId: "bob",
            targetKind: .user,
            reason: .spam
        ))
    }

    func testSubmitReportWithABlankTargetIdReturnsNil() {
        let repo = ReportRepository()

        XCTAssertNil(repo.submitReport(
            reporterId: "alice",
            targetId: "",
            targetKind: .user,
            reason: .spam
        ))
    }

    // MARK: - submitReport: additionalText

    func testSubmitReportStoresTheTrimmedAdditionalText() {
        let repo = ReportRepository()

        let report = repo.submitReport(
            reporterId: "alice",
            targetId: "bob",
            targetKind: .user,
            reason: .other,
            additionalText: "  extra context  "
        )

        XCTAssertNotNil(report)
        XCTAssertEqual(report?.additionalText, "extra context")
    }

    func testSubmitReportWithAdditionalTextAtTheMaximumLengthIsAccepted() {
        let repo = ReportRepository()
        let maxText = String(repeating: "a", count: ReportRepository.maxFreeTextLength)

        let report = repo.submitReport(
            reporterId: "alice",
            targetId: "bob",
            targetKind: .user,
            reason: .spam,
            additionalText: maxText
        )

        XCTAssertNotNil(report)
        XCTAssertEqual(report?.additionalText, maxText)
    }

    func testSubmitReportWithAdditionalTextOneCharacterOverTheMaximumLengthReturnsNil() {
        let repo = ReportRepository()
        let tooLong = String(repeating: "a", count: ReportRepository.maxFreeTextLength + 1)

        XCTAssertNil(repo.submitReport(
            reporterId: "alice",
            targetId: "bob",
            targetKind: .user,
            reason: .spam,
            additionalText: tooLong
        ))
    }

    // MARK: - submitReport: each reason is accepted

    func testSubmitReportAcceptsEachReportReason() {
        let repo = ReportRepository()
        let reasons: [ReportReason] = [
            .spam, .harassment, .inappropriateContent, .fakeProfile, .underageUser, .other,
        ]
        for reason in reasons {
            XCTAssertNotNil(
                repo.submitReport(
                    reporterId: "alice",
                    targetId: "target",
                    targetKind: .user,
                    reason: reason
                ),
                "reason \(reason) should be accepted"
            )
        }
    }

    // MARK: - getReportsAgainst

    func testGetReportsAgainstReturnsAllReportsForTheGivenTarget() {
        let repo = ReportRepository()
        repo.submitReport(reporterId: "alice", targetId: "bob", targetKind: .user, reason: .spam)
        repo.submitReport(reporterId: "carol", targetId: "bob", targetKind: .user, reason: .harassment)

        let reports = repo.getReportsAgainst(targetId: "bob")

        XCTAssertEqual(reports.count, 2)
        XCTAssertTrue(reports.allSatisfy { $0.targetId == "bob" })
    }

    func testGetReportsAgainstReturnsEmptyArrayWhenNoReportsHaveBeenFiled() {
        let repo = ReportRepository()

        XCTAssertTrue(repo.getReportsAgainst(targetId: "bob").isEmpty)
    }

    func testGetReportsAgainstDoesNotIncludeReportsForADifferentTarget() {
        let repo = ReportRepository()
        repo.submitReport(reporterId: "alice", targetId: "bob", targetKind: .user, reason: .spam)
        repo.submitReport(reporterId: "alice", targetId: "carol", targetKind: .user, reason: .spam)

        let reportsAgainstBob = repo.getReportsAgainst(targetId: "bob")

        XCTAssertEqual(reportsAgainstBob.count, 1)
        XCTAssertEqual(reportsAgainstBob[0].targetId, "bob")
    }

    // MARK: - getReportsByReporter

    func testGetReportsByReporterReturnsAllReportsFiledByTheGivenReporter() {
        let repo = ReportRepository()
        repo.submitReport(reporterId: "alice", targetId: "bob", targetKind: .user, reason: .spam)
        repo.submitReport(reporterId: "alice", targetId: "carol", targetKind: .user, reason: .harassment)
        repo.submitReport(reporterId: "bob", targetId: "carol", targetKind: .user, reason: .spam)

        let aliceReports = repo.getReportsByReporter(reporterId: "alice")

        XCTAssertEqual(aliceReports.count, 2)
        XCTAssertTrue(aliceReports.allSatisfy { $0.reporterId == "alice" })
    }

    func testGetReportsByReporterReturnsEmptyArrayWhenReporterHasFiledNoReports() {
        let repo = ReportRepository()

        XCTAssertTrue(repo.getReportsByReporter(reporterId: "alice").isEmpty)
    }

    // MARK: - duplicate reports

    func testSubmitReportAllowsMultipleReportsFromTheSameReporterAgainstTheSameTarget() {
        // De-duplication is an operational concern; the domain layer records
        // every submission as a distinct report.
        let repo = ReportRepository()
        repo.submitReport(reporterId: "alice", targetId: "bob", targetKind: .user, reason: .spam)
        repo.submitReport(reporterId: "alice", targetId: "bob", targetKind: .user, reason: .harassment)

        XCTAssertEqual(repo.getReportsAgainst(targetId: "bob").count, 2)
    }

    // MARK: - report ids

    func testEachSubmittedReportGetsADistinctId() {
        let repo = ReportRepository()
        let r1 = repo.submitReport(reporterId: "alice", targetId: "bob", targetKind: .user, reason: .spam)!
        let r2 = repo.submitReport(reporterId: "alice", targetId: "carol", targetKind: .user, reason: .spam)!

        XCTAssertNotEqual(r1.id, r2.id)
    }
}
