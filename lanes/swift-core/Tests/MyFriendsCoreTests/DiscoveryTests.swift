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

    // MARK: - AC#3: radius-based discovery
    //
    // Base location: lat=51.500, lon=-0.100 (central London, approx).
    // Offsets (same longitude, haversine on latitude arc only):
    //   +0.005° ≈  0.56 km  → inside 1 km, 5 km, 10 km, 25 km
    //   +0.040° ≈  4.45 km  → inside 5 km, 10 km, 25 km; outside 1 km
    //   +0.070° ≈  7.78 km  → inside 10 km, 25 km; outside 1 km, 5 km
    //   +0.150° ≈ 16.68 km  → inside 25 km; outside 1 km, 5 km, 10 km
    //   +0.300° ≈ 33.37 km  → outside all four radii

    private var baseLocation: GeoLocation { GeoLocation(lat: 51.500, lon: -0.100) }

    private func locationAt(deltaLat: Double) -> GeoLocation {
        GeoLocation(lat: 51.500 + deltaLat, lon: -0.100)
    }

    func testDiscoverWithRadiusReturnsOnlyProfilesWithinThatRadius() {
        // ada is ~0.56 km away, grace is ~4.45 km away.
        // A 1 km radius should include only ada; a 5 km radius should include both.
        let repository = ProfileRepository()
        let searcher = Profile(id: "searcher", displayName: "Searcher", photo: validPhoto())
        try! repository.save(Profile(
            id: "ada",
            displayName: "Ada Lovelace",
            photo: validPhoto(),
            openToFriends: true,
            location: locationAt(deltaLat: 0.005)   // ~0.56 km
        ))
        try! repository.save(Profile(
            id: "grace",
            displayName: "Grace Hopper",
            photo: validPhoto(),
            openToFriends: true,
            location: locationAt(deltaLat: 0.040)   // ~4.45 km
        ))

        let within1km = repository.discover(searcher: searcher, near: baseLocation, within: .one)
        let within5km = repository.discover(searcher: searcher, near: baseLocation, within: .five)

        XCTAssertEqual(within1km.count, 1)
        XCTAssertEqual(within1km[0].profile.id, "ada")
        XCTAssertEqual(within5km.count, 2)
    }

    func testDiscoverWithRadiusExcludesProfilesWithoutALocation() {
        // A profile that has never reported its location cannot be placed within
        // any radius and must be excluded from radius-filtered results.
        let repository = ProfileRepository()
        let searcher = Profile(id: "searcher", displayName: "Searcher", photo: validPhoto())
        try! repository.save(Profile(
            id: "no-location",
            displayName: "No Location",
            photo: validPhoto(),
            openToFriends: true
            // location deliberately omitted (defaults to nil)
        ))

        let results = repository.discover(searcher: searcher, near: baseLocation, within: .twentyFive)

        XCTAssertTrue(results.isEmpty)
    }

    func testDiscoverWithRadiusStillHonoursTheOpenToFriendsGate() {
        // A profile within the radius but with openToFriends=false must not appear.
        let repository = ProfileRepository()
        let searcher = Profile(id: "searcher", displayName: "Searcher", photo: validPhoto())
        try! repository.save(Profile(
            id: "closed",
            displayName: "Closed Profile",
            photo: validPhoto(),
            openToFriends: false,                       // flag is off
            location: locationAt(deltaLat: 0.005)       // well within any radius
        ))

        let results = repository.discover(searcher: searcher, near: baseLocation, within: .twentyFive)

        XCTAssertTrue(results.isEmpty)
    }

    func testDiscoverWithRadiusResultsAreOrderedByScoreDescending() {
        // Two profiles within the radius; higher-scoring one must come first.
        let repository = ProfileRepository()
        let searcher = Profile(
            id: "searcher",
            displayName: "Searcher",
            photo: validPhoto(),
            interests: ["jazz", "climbing"]
        )
        // grace shares both interests → score 1.0
        try! repository.save(Profile(
            id: "grace",
            displayName: "Grace Hopper",
            photo: validPhoto(),
            interests: ["jazz", "climbing"],
            openToFriends: true,
            location: locationAt(deltaLat: 0.005)   // ~0.56 km
        ))
        // ada shares only jazz → score 0.5
        try! repository.save(Profile(
            id: "ada",
            displayName: "Ada Lovelace",
            photo: validPhoto(),
            interests: ["jazz"],
            openToFriends: true,
            location: locationAt(deltaLat: 0.040)   // ~4.45 km
        ))

        let results = repository.discover(searcher: searcher, near: baseLocation, within: .ten)

        XCTAssertEqual(results.count, 2)
        XCTAssertEqual(results[0].profile.id, "grace")
        XCTAssertEqual(results[0].score, 1.0)
        XCTAssertEqual(results[1].profile.id, "ada")
        XCTAssertEqual(results[1].score, 0.5)
    }

    func testDiscoverWithAllFourRadiusValuesUsesTheCorrectThresholds() {
        // One profile per zone; each radius value should include exactly the
        // profiles within it.
        //   ~0.56 km → within all four radii
        //   ~4.45 km → within 5 km, 10 km, 25 km; outside 1 km
        //   ~7.78 km → within 10 km, 25 km; outside 1 km, 5 km
        //  ~16.68 km → within 25 km; outside 1 km, 5 km, 10 km
        let repository = ProfileRepository()
        let searcher = Profile(id: "searcher", displayName: "Searcher", photo: validPhoto())
        try! repository.save(Profile(id: "p1", displayName: "P1", photo: validPhoto(), openToFriends: true, location: locationAt(deltaLat: 0.005)))
        try! repository.save(Profile(id: "p2", displayName: "P2", photo: validPhoto(), openToFriends: true, location: locationAt(deltaLat: 0.040)))
        try! repository.save(Profile(id: "p3", displayName: "P3", photo: validPhoto(), openToFriends: true, location: locationAt(deltaLat: 0.070)))
        try! repository.save(Profile(id: "p4", displayName: "P4", photo: validPhoto(), openToFriends: true, location: locationAt(deltaLat: 0.150)))

        XCTAssertEqual(repository.discover(searcher: searcher, near: baseLocation, within: .one).count, 1)
        XCTAssertEqual(repository.discover(searcher: searcher, near: baseLocation, within: .five).count, 2)
        XCTAssertEqual(repository.discover(searcher: searcher, near: baseLocation, within: .ten).count, 3)
        XCTAssertEqual(repository.discover(searcher: searcher, near: baseLocation, within: .twentyFive).count, 4)
    }

    // MARK: - AC#1 / constitution P3: age-bracket isolation in discovery

    func testDiscoverExcludesAdultCandidatesFromAMinorSearcher() {
        // A 17-year-old searcher must not see 18+ profiles in their results.
        // Constitution P3 (enforceable): discovery is age-isolated so that
        // minors (age < minAdultAge) are never surfaced to adults and vice versa.
        let repository = ProfileRepository()
        let searcher = Profile(
            id: "minor-searcher",
            displayName: "Minor Searcher",
            photo: validPhoto(),
            interests: ["jazz"],
            age: 17
        )
        try! repository.save(Profile(
            id: "adult",
            displayName: "Adult User",
            photo: validPhoto(),
            interests: ["jazz"],
            openToFriends: true,
            age: ProfileRepository.minAdultAge
        ))

        let results = repository.discover(searcher: searcher)

        XCTAssertTrue(results.isEmpty)
    }

    func testDiscoverExcludesMinorCandidatesFromAnAdultSearcher() {
        // An 18-year-old searcher must not see under-18 profiles in their results.
        let repository = ProfileRepository()
        let searcher = Profile(
            id: "adult-searcher",
            displayName: "Adult Searcher",
            photo: validPhoto(),
            interests: ["jazz"],
            age: ProfileRepository.minAdultAge
        )
        try! repository.save(Profile(
            id: "minor",
            displayName: "Minor User",
            photo: validPhoto(),
            interests: ["jazz"],
            openToFriends: true,
            age: 17
        ))

        let results = repository.discover(searcher: searcher)

        XCTAssertTrue(results.isEmpty)
    }

    func testDiscoverShowsMinorCandidatesToAMinorSearcher() {
        // A 16-year-old sees other under-18 profiles (both are minors).
        let repository = ProfileRepository()
        let searcher = Profile(
            id: "minor-16",
            displayName: "Minor 16",
            photo: validPhoto(),
            interests: ["jazz"],
            age: 16
        )
        try! repository.save(Profile(
            id: "minor-17",
            displayName: "Minor 17",
            photo: validPhoto(),
            interests: ["jazz"],
            openToFriends: true,
            age: 17
        ))

        let results = repository.discover(searcher: searcher)

        XCTAssertEqual(results.count, 1)
        XCTAssertEqual(results[0].profile.id, "minor-17")
    }

    func testDiscoverShowsAdultCandidatesToAnAdultSearcher() {
        // An 18-year-old sees other 18+ profiles (both are adults).
        let repository = ProfileRepository()
        let searcher = Profile(
            id: "adult-18",
            displayName: "Adult 18",
            photo: validPhoto(),
            interests: ["jazz"],
            age: ProfileRepository.minAdultAge
        )
        try! repository.save(Profile(
            id: "adult-25",
            displayName: "Adult 25",
            photo: validPhoto(),
            interests: ["jazz"],
            openToFriends: true,
            age: 25
        ))

        let results = repository.discover(searcher: searcher)

        XCTAssertEqual(results.count, 1)
        XCTAssertEqual(results[0].profile.id, "adult-25")
    }
}
