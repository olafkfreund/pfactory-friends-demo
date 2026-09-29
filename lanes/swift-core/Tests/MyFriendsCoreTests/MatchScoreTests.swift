import XCTest
@testable import MyFriendsCore

final class MatchScoreTests: XCTestCase {
    func testHalfTheInterestsOverlap() {
        XCTAssertEqual(MatchScore.score(mine: ["climbing", "jazz"], theirs: ["jazz", "chess"]), 0.5)
    }

    func testEmptyInterestsScoreZeroRatherThanCrashing() {
        XCTAssertEqual(MatchScore.score(mine: [], theirs: ["jazz"]), 0)
    }

    // AC#1: combined score including availability

    func testCombinedScoreWithNoAvailabilityFallsBackToInterestScore() {
        // When the searcher has no stated availability the availability component
        // is absent and the result equals the interest-only score.
        XCTAssertEqual(
            MatchScore.score(
                myInterests: ["climbing", "jazz"],
                theirInterests: ["jazz", "chess"],
                myAvailability: [],
                theirAvailability: ["weekday-evenings"]
            ),
            0.5
        )
    }

    func testCombinedScoreIsMeanOfInterestAndAvailabilityScores() {
        // interests: 1/2 = 0.5, availability: 1/1 = 1.0, combined = 0.75
        XCTAssertEqual(
            MatchScore.score(
                myInterests: ["jazz", "climbing"],
                theirInterests: ["jazz", "chess"],
                myAvailability: ["weekday-evenings"],
                theirAvailability: ["weekday-evenings"]
            ),
            0.75
        )
    }

    func testCombinedScoreWithNoAvailabilityOverlapReducesOverallScore() {
        // interests: 1/2 = 0.5, availability: 0/1 = 0.0, combined = 0.25
        XCTAssertEqual(
            MatchScore.score(
                myInterests: ["jazz", "climbing"],
                theirInterests: ["jazz", "chess"],
                myAvailability: ["weekday-evenings"],
                theirAvailability: ["weekends"]
            ),
            0.25
        )
    }

    func testCombinedScoreWithEmptyInterestsAndAvailabilityScoresZero() {
        XCTAssertEqual(
            MatchScore.score(
                myInterests: [],
                theirInterests: ["jazz"],
                myAvailability: [],
                theirAvailability: ["weekends"]
            ),
            0.0
        )
    }
}
