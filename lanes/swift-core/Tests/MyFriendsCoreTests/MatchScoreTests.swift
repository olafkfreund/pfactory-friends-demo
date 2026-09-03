import XCTest
@testable import MyFriendsCore

final class MatchScoreTests: XCTestCase {
    func testHalfTheInterestsOverlap() {
        XCTAssertEqual(MatchScore.score(mine: ["climbing", "jazz"], theirs: ["jazz", "chess"]), 0.5)
    }

    func testEmptyInterestsScoreZeroRatherThanCrashing() {
        XCTAssertEqual(MatchScore.score(mine: [], theirs: ["jazz"]), 0)
    }
}
