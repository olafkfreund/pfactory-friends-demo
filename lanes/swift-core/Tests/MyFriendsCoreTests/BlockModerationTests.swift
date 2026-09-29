import XCTest
@testable import MyFriendsCore

/// Tests for AC#7 (blocking) and AC#8 (reporting): a person can block users,
/// and the moderation outcome of a report is independent of whether either
/// person has blocked the other.
///
/// Two aspects are verified here:
///
/// 1. A user can block multiple users and all blocks are independently recorded.
/// 2. The report pipeline—from submission through to moderation retrieval—is
///    completely independent of block relationships: a report filed by a user
///    who has blocked the target, or by a user who has been blocked by the
///    target, is accepted and visible to moderators exactly as any other report
///    would be.  This matters because a moderator reviewing a report must see
///    all reports to make an unbiased decision; the block state between the
///    parties is personal to each user and must not silently hide a report or
///    influence its priority.
///
/// `ReportRepository` intentionally has no reference to `ProfileRepository`
/// and performs no block check; these tests confirm that the design holds.
///
/// The same tests exist in the Kotlin lane (BlockModerationTest.kt),
/// per constitution P9.
final class BlockModerationTests: XCTestCase {

    // MARK: - Helpers

    private func validPhoto() -> ProfilePhoto {
        return ProfilePhoto(bytes: [1, 2, 3, 4], format: "png")
    }

    /// Saves a profile with the given `id` in `repo` and returns it.
    @discardableResult
    private func savedProfile(in repo: ProfileRepository, id: String) -> Profile {
        let profile = Profile(id: id, displayName: "User \(id)", photo: validPhoto())
        try! repo.save(profile)
        return profile
    }

    // MARK: - AC#7 part 1: a person can block multiple users

    func testBlockUserRecordsTheBlockSoIsBlockedReturnsTrueForTheSamePair() {
        let profileRepo = ProfileRepository()
        savedProfile(in: profileRepo, id: "alice")
        savedProfile(in: profileRepo, id: "bob")

        XCTAssertTrue(profileRepo.blockUser(blockerId: "alice", blockedId: "bob"))
        XCTAssertTrue(profileRepo.isBlocked(blockerId: "alice", blockedId: "bob"))
    }

    func testAPersonCanBlockMultipleUsersAndAllBlocksAreIndependentlyRecorded() {
        let profileRepo = ProfileRepository()
        savedProfile(in: profileRepo, id: "alice")
        savedProfile(in: profileRepo, id: "bob")
        savedProfile(in: profileRepo, id: "carol")

        profileRepo.blockUser(blockerId: "alice", blockedId: "bob")
        profileRepo.blockUser(blockerId: "alice", blockedId: "carol")

        XCTAssertTrue(profileRepo.isBlocked(blockerId: "alice", blockedId: "bob"))
        XCTAssertTrue(profileRepo.isBlocked(blockerId: "alice", blockedId: "carol"))
    }

    // MARK: - AC#8 + AC#7: moderation outcome is independent of blocks

    func testAReportIsAcceptedWhenTheReporterHasBlockedTheReportedPerson() {
        // Alice blocks Bob, then files a report against Bob.
        // The block must not prevent the report from being stored.
        let profileRepo = ProfileRepository()
        savedProfile(in: profileRepo, id: "alice")
        savedProfile(in: profileRepo, id: "bob")
        profileRepo.blockUser(blockerId: "alice", blockedId: "bob")

        let reportRepo = ReportRepository()
        let report = reportRepo.submitReport(
            reporterId: "alice",
            targetId: "bob",
            targetKind: .user,
            reason: .harassment
        )

        XCTAssertNotNil(report, "report must be accepted even when alice has blocked bob")
        XCTAssertEqual(report?.reporterId, "alice")
        XCTAssertEqual(report?.targetId, "bob")
    }

    func testAReportIsAcceptedWhenTheReportedPersonHasBlockedTheReporter() {
        // Bob blocks Alice, but Alice can still file a report against Bob.
        let profileRepo = ProfileRepository()
        savedProfile(in: profileRepo, id: "alice")
        savedProfile(in: profileRepo, id: "bob")
        profileRepo.blockUser(blockerId: "bob", blockedId: "alice")

        let reportRepo = ReportRepository()
        let report = reportRepo.submitReport(
            reporterId: "alice",
            targetId: "bob",
            targetKind: .user,
            reason: .spam
        )

        XCTAssertNotNil(report, "report must be accepted even when bob has blocked alice")
        XCTAssertEqual(report?.reporterId, "alice")
        XCTAssertEqual(report?.targetId, "bob")
    }

    func testAReportIsAcceptedWhenBothPartiesHaveMutuallyBlockedEachOther() {
        // Both alice→bob and bob→alice blocks are active; reporting must still work.
        let profileRepo = ProfileRepository()
        savedProfile(in: profileRepo, id: "alice")
        savedProfile(in: profileRepo, id: "bob")
        profileRepo.blockUser(blockerId: "alice", blockedId: "bob")
        profileRepo.blockUser(blockerId: "bob", blockedId: "alice")

        let reportRepo = ReportRepository()
        let report = reportRepo.submitReport(
            reporterId: "alice",
            targetId: "bob",
            targetKind: .user,
            reason: .inappropriateContent
        )

        XCTAssertNotNil(report, "report must be accepted even with mutual blocks")
    }

    func testGetReportsAgainstReturnsReportsRegardlessOfAnyBlockBetweenTheParties() {
        // Three reporters each block bob, then each files a report against bob.
        // A moderator querying for all reports against bob must see all three,
        // not a filtered view based on the block state of any reporter.
        let profileRepo = ProfileRepository()
        savedProfile(in: profileRepo, id: "alice")
        savedProfile(in: profileRepo, id: "carol")
        savedProfile(in: profileRepo, id: "dave")
        savedProfile(in: profileRepo, id: "bob")
        profileRepo.blockUser(blockerId: "alice", blockedId: "bob")
        profileRepo.blockUser(blockerId: "carol", blockedId: "bob")
        profileRepo.blockUser(blockerId: "dave", blockedId: "bob")

        let reportRepo = ReportRepository()
        reportRepo.submitReport(reporterId: "alice", targetId: "bob", targetKind: .user, reason: .spam)
        reportRepo.submitReport(reporterId: "carol", targetId: "bob", targetKind: .user, reason: .harassment)
        reportRepo.submitReport(reporterId: "dave",  targetId: "bob", targetKind: .user, reason: .fakeProfile)

        let reports = reportRepo.getReportsAgainst(targetId: "bob")

        XCTAssertEqual(
            reports.count,
            3,
            "all three reports must be visible to a moderator regardless of blocks"
        )
        XCTAssertTrue(reports.allSatisfy { $0.targetId == "bob" })
    }

    func testGetReportsAgainstIsNotAffectedByTheReportedPersonHavingBlockedReporters() {
        // Bob blocks all reporters. The moderation view must still show every
        // report filed against bob.
        let profileRepo = ProfileRepository()
        savedProfile(in: profileRepo, id: "alice")
        savedProfile(in: profileRepo, id: "carol")
        savedProfile(in: profileRepo, id: "bob")
        profileRepo.blockUser(blockerId: "bob", blockedId: "alice")
        profileRepo.blockUser(blockerId: "bob", blockedId: "carol")

        let reportRepo = ReportRepository()
        reportRepo.submitReport(reporterId: "alice", targetId: "bob", targetKind: .user, reason: .spam)
        reportRepo.submitReport(reporterId: "carol", targetId: "bob", targetKind: .user, reason: .harassment)

        let reports = reportRepo.getReportsAgainst(targetId: "bob")

        XCTAssertEqual(
            reports.count,
            2,
            "all reports must be visible regardless of bob having blocked the reporters"
        )
    }

    func testAReportFiledBeforeABlockIsEstablishedRemainsVisibleToModeratorsAfterTheBlock() {
        // The report was filed first; the block was added later. Blocks are
        // prospective: they restrict future interactions (discovery, messaging,
        // connection requests) but must not retroactively hide prior reports
        // from the moderation view.
        let profileRepo = ProfileRepository()
        savedProfile(in: profileRepo, id: "alice")
        savedProfile(in: profileRepo, id: "bob")

        let reportRepo = ReportRepository()
        let report = reportRepo.submitReport(
            reporterId: "alice",
            targetId: "bob",
            targetKind: .user,
            reason: .harassment
        )
        XCTAssertNotNil(report)

        // Block established after the report.
        profileRepo.blockUser(blockerId: "alice", blockedId: "bob")

        // The report is still visible.
        let reports = reportRepo.getReportsAgainst(targetId: "bob")
        XCTAssertEqual(reports.count, 1, "pre-block report must still be visible after the block")
        XCTAssertEqual(reports.first?.id, report?.id)
    }

    func testBlockStateBetweenReporterAndTargetDoesNotAffectReportsFiledAboutMessages() {
        // A report about a specific message (e.g. harmful content) must reach
        // moderation even when the parties have blocked each other.
        let profileRepo = ProfileRepository()
        savedProfile(in: profileRepo, id: "alice")
        savedProfile(in: profileRepo, id: "bob")
        profileRepo.blockUser(blockerId: "alice", blockedId: "bob")
        profileRepo.blockUser(blockerId: "bob", blockedId: "alice")

        let reportRepo = ReportRepository()
        let report = reportRepo.submitReport(
            reporterId: "alice",
            targetId: "msg-42",
            targetKind: .message,
            reason: .inappropriateContent
        )

        XCTAssertNotNil(report, "message report must be accepted regardless of mutual blocks")
        XCTAssertEqual(report?.targetKind, .message)
        XCTAssertEqual(report?.targetId, "msg-42")
    }
}
