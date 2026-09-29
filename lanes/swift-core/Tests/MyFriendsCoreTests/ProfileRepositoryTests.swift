import XCTest
@testable import MyFriendsCore

// AC#2: open-to-friends toggle

final class ProfileRepositoryTests: XCTestCase {

    func testFreshlyCreatedProfileHasOpenToFriendsFalseByDefault() {
        let repository = ProfileRepository()
        repository.save(Profile(id: "user-1"))
        XCTAssertFalse(repository.find(id: "user-1")?.openToFriends ?? true)
    }

    func testSetOpenToFriendsTrueMarksProfileAsOpen() {
        let repository = ProfileRepository()
        repository.save(Profile(id: "user-1"))
        XCTAssertTrue(repository.setOpenToFriends(id: "user-1", open: true))
        XCTAssertTrue(repository.find(id: "user-1")?.openToFriends ?? false)
    }

    func testSetOpenToFriendsFalseMarksProfileAsClosed() {
        let repository = ProfileRepository()
        repository.save(Profile(id: "user-1", openToFriends: true))
        XCTAssertTrue(repository.setOpenToFriends(id: "user-1", open: false))
        XCTAssertFalse(repository.find(id: "user-1")?.openToFriends ?? true)
    }

    func testSetOpenToFriendsOnUnknownIdReturnsFalse() {
        let repository = ProfileRepository()
        XCTAssertFalse(repository.setOpenToFriends(id: "never-saved", open: true))
    }

    func testFindOpenReturnsOnlyOpenProfiles() {
        let repository = ProfileRepository()
        repository.save(Profile(id: "user-1"))
        repository.save(Profile(id: "user-2"))
        repository.setOpenToFriends(id: "user-1", open: true)

        let open = repository.findOpen()
        XCTAssertEqual(open.count, 1)
        XCTAssertEqual(open.first?.id, "user-1")
    }

    func testFindOpenExcludesProfileAfterFlagIsTurnedOff() {
        let repository = ProfileRepository()
        repository.save(Profile(id: "user-1"))
        repository.setOpenToFriends(id: "user-1", open: true)
        XCTAssertTrue(repository.findOpen().contains(where: { $0.id == "user-1" }))

        repository.setOpenToFriends(id: "user-1", open: false)
        XCTAssertFalse(repository.findOpen().contains(where: { $0.id == "user-1" }))
    }

    func testFindOpenReturnsEmptyListWhenNoProfilesAreOpen() {
        let repository = ProfileRepository()
        repository.save(Profile(id: "user-1"))
        XCTAssertTrue(repository.findOpen().isEmpty)
    }

    func testProfileSavedWithOpenToFriendsTrueAppearsInFindOpenImmediately() {
        let repository = ProfileRepository()
        repository.save(Profile(id: "user-1", openToFriends: true))
        let open = repository.findOpen()
        XCTAssertEqual(open.count, 1)
        XCTAssertEqual(open.first?.id, "user-1")
    }

    func testFindOpenReturnsAllOpenProfilesWhenMultipleExist() {
        let repository = ProfileRepository()
        repository.save(Profile(id: "user-1"))
        repository.save(Profile(id: "user-2"))
        repository.save(Profile(id: "user-3"))
        repository.setOpenToFriends(id: "user-1", open: true)
        repository.setOpenToFriends(id: "user-2", open: true)

        let open = repository.findOpen()
        XCTAssertEqual(open.count, 2)
        XCTAssertTrue(open.contains(where: { $0.id == "user-1" }))
        XCTAssertTrue(open.contains(where: { $0.id == "user-2" }))
        XCTAssertFalse(open.contains(where: { $0.id == "user-3" }))
    }
}
