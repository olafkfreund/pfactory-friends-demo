import XCTest
@testable import MyFriendsCore

final class DiscoveryTests: XCTestCase {

    // MARK: - Helpers

    private func validPhoto() -> ProfilePhoto {
        return ProfilePhoto(bytes: [1, 2, 3, 4], format: "png")
    }

    // MARK: - AC#4: ordered by score

    func testDiscoverReturnsCandidatesOrderedByScoreDescending() {
        // Searcher has jazz + climbing. Ada shares jazz (score 0.5),
        // Grace shares jazz + climbing (score 1.0). Grace must come first.
        let repository = ProfileRepository()
        let searcher = Profile(
            id: "searcher",
            displayName: "Searcher",
            photo: validPhoto(),
            interests: ["jazz", "climbing"]
        )
        try! repository.save(Profile(
            id: "ada",
            displayName: "Ada Lovelace",
            photo: validPhoto(),
            interests: ["jazz", "chess"],
            openToFriends: true
        ))
        try! repository.save(Profile(
            id: "grace",
            displayName: "Grace Hopper",
            photo: validPhoto(),
            interests: ["jazz", "climbing"],
            openToFriends: true
        ))

        let results = repository.discover(searcher: searcher)

        XCTAssertEqual(results.count, 2)
        XCTAssertEqual(results[0].profile.id, "grace")
        XCTAssertEqual(results[1].profile.id, "ada")
        XCTAssertEqual(results[0].score, 1.0)
        XCTAssertEqual(results[1].score, 0.5)
    }

    func testDiscoverExcludesTheSearcherEvenWhenTheyHaveOpenToFriendsTrue() {
        let repository = ProfileRepository()
        let searcher = Profile(
            id: "searcher",
            displayName: "Searcher",
            photo: validPhoto(),
            interests: ["jazz"],
            openToFriends: true
        )
        try! repository.save(searcher)
        try! repository.save(Profile(
            id: "other",
            displayName: "Other Person",
            photo: validPhoto(),
            interests: ["jazz"],
            openToFriends: true
        ))

        let results = repository.discover(searcher: searcher)

        XCTAssertFalse(results.contains(where: { $0.profile.id == "searcher" }))
        XCTAssertEqual(results.count, 1)
        XCTAssertEqual(results[0].profile.id, "other")
    }

    func testDiscoverExcludesProfilesWithOpenToFriendsFalse() {
        let repository = ProfileRepository()
        let searcher = Profile(
            id: "searcher",
            displayName: "Searcher",
            photo: validPhoto(),
            interests: ["jazz"]
        )
        try! repository.save(Profile(
            id: "closed",
            displayName: "Closed Profile",
            photo: validPhoto(),
            interests: ["jazz"],
            openToFriends: false
        ))

        let results = repository.discover(searcher: searcher)

        XCTAssertTrue(results.isEmpty)
    }

    func testDiscoverReturnsEmptyListWhenNoOpenProfilesExist() {
        let repository = ProfileRepository()
        let searcher = Profile(
            id: "searcher",
            displayName: "Searcher",
            photo: validPhoto()
        )

        let results = repository.discover(searcher: searcher)

        XCTAssertTrue(results.isEmpty)
    }

    // MARK: - AC#4: shows why each result was surfaced

    func testDiscoverPopulatesSharedInterestsWithTheSortedIntersectionOfInterestTags() {
        let repository = ProfileRepository()
        let searcher = Profile(
            id: "searcher",
            displayName: "Searcher",
            photo: validPhoto(),
            interests: ["jazz", "climbing", "chess"]
        )
        try! repository.save(Profile(
            id: "ada",
            displayName: "Ada Lovelace",
            photo: validPhoto(),
            interests: ["climbing", "jazz", "cycling"],
            openToFriends: true
        ))

        let result = repository.discover(searcher: searcher).first!

        // jazz and climbing overlap; sorted alphabetically
        XCTAssertEqual(result.sharedInterests, ["climbing", "jazz"])
    }

    func testDiscoverPopulatesSharedActivitiesWithTheSortedIntersectionOfActivityTags() {
        let repository = ProfileRepository()
        let searcher = Profile(
            id: "searcher",
            displayName: "Searcher",
            photo: validPhoto(),
            activities: ["weekends", "weekday-evenings"]
        )
        try! repository.save(Profile(
            id: "ada",
            displayName: "Ada Lovelace",
            photo: validPhoto(),
            activities: ["weekday-evenings", "mornings"],
            openToFriends: true
        ))

        let result = repository.discover(searcher: searcher).first!

        XCTAssertEqual(result.sharedActivities, ["weekday-evenings"])
    }

    func testDiscoverReturnsEmptySharedInterestsAndActivitiesWhenThereIsNoOverlap() {
        let repository = ProfileRepository()
        let searcher = Profile(
            id: "searcher",
            displayName: "Searcher",
            photo: validPhoto(),
            interests: ["jazz"],
            activities: ["weekends"]
        )
        try! repository.save(Profile(
            id: "ada",
            displayName: "Ada Lovelace",
            photo: validPhoto(),
            interests: ["chess"],
            activities: ["mornings"],
            openToFriends: true
        ))

        let result = repository.discover(searcher: searcher).first!

        XCTAssertTrue(result.sharedInterests.isEmpty)
        XCTAssertTrue(result.sharedActivities.isEmpty)
        XCTAssertEqual(result.score, 0.0)
    }

    func testDiscoverWithEmptySearcherInterestsStillReturnsOpenProfilesWithScoreZero() {
        let repository = ProfileRepository()
        let searcher = Profile(
            id: "searcher",
            displayName: "Searcher",
            photo: validPhoto()
        )
        try! repository.save(Profile(
            id: "ada",
            displayName: "Ada Lovelace",
            photo: validPhoto(),
            interests: ["jazz"],
            openToFriends: true
        ))

        let results = repository.discover(searcher: searcher)

        XCTAssertEqual(results.count, 1)
        XCTAssertEqual(results[0].score, 0.0)
    }

    func testDiscoverScoreMatchesMatchScoreOutputForTheSameInputs() {
        // interests: mine={jazz,climbing}, theirs={jazz,chess} => 1/2 = 0.5
        // activities: mine={weekday-evenings}, theirs={weekday-evenings} => 1/1 = 1.0
        // combined = (0.5 + 1.0) / 2 = 0.75
        let repository = ProfileRepository()
        let searcher = Profile(
            id: "searcher",
            displayName: "Searcher",
            photo: validPhoto(),
            interests: ["jazz", "climbing"],
            activities: ["weekday-evenings"]
        )
        try! repository.save(Profile(
            id: "ada",
            displayName: "Ada Lovelace",
            photo: validPhoto(),
            interests: ["jazz", "chess"],
            activities: ["weekday-evenings"],
            openToFriends: true
        ))

        let result = repository.discover(searcher: searcher).first!

        XCTAssertEqual(result.score, 0.75)
    }

    func testDiscoverSearcherWithoutOpenToFriendsCanStillBrowseOpenProfiles() {
        // The searcher does not need openToFriends=true to browse.
        let repository = ProfileRepository()
        let searcher = Profile(
            id: "searcher",
            displayName: "Searcher",
            photo: validPhoto(),
            interests: ["jazz"],
            openToFriends: false
        )
        try! repository.save(Profile(
            id: "ada",
            displayName: "Ada Lovelace",
            photo: validPhoto(),
            interests: ["jazz"],
            openToFriends: true
        ))

        let results = repository.discover(searcher: searcher)

        XCTAssertEqual(results.count, 1)
        XCTAssertEqual(results[0].profile.id, "ada")
    }
}
