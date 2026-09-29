import XCTest
@testable import MyFriendsCore

final class ProfileRepositoryTests: XCTestCase {

    // MARK: - Helpers

    /// A photo that passes validation: a supported format and a byte payload
    /// well within `ProfileRepository.maxPhotoSizeBytes`. The photo field is
    /// required for a complete profile; this keeps tests focused on the
    /// property under test rather than repeating photo boilerplate.
    private func validPhoto(
        bytes: [UInt8] = [1, 2, 3, 4],
        format: String = "png"
    ) -> ProfilePhoto {
        return ProfilePhoto(bytes: bytes, format: format)
    }

    // MARK: - Basic save / find

    func testSavingAValidDisplayNamePersistsItForAnIndependentReadBack() {
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto()))

        XCTAssertEqual(repository.find(id: "user-1")?.displayName, "Ada Lovelace")
    }

    // MARK: - id validation

    func testSavingABlankIdThrowsAndPersistsNothing() {
        let repository = ProfileRepository()

        XCTAssertThrowsError(
            try repository.save(Profile(id: "", displayName: "Ada Lovelace", photo: validPhoto()))
        ) { error in
            XCTAssertEqual(error as? ProfileRepositoryError, .blankId)
        }
        XCTAssertNil(repository.find(id: ""))
    }

    func testSavingAWhitespaceOnlyIdThrowsAndPersistsNothing() {
        let repository = ProfileRepository()

        XCTAssertThrowsError(
            try repository.save(Profile(id: "   ", displayName: "Ada Lovelace", photo: validPhoto()))
        ) { error in
            XCTAssertEqual(error as? ProfileRepositoryError, .blankId)
        }
        XCTAssertNil(repository.find(id: "   "))
    }

    // MARK: - displayName validation

    func testSavingABlankDisplayNameThrowsAndPersistsNothing() {
        let repository = ProfileRepository()

        XCTAssertThrowsError(
            try repository.save(Profile(id: "user-1", displayName: "   ", photo: validPhoto()))
        ) { error in
            XCTAssertEqual(error as? ProfileRepositoryError, .blankDisplayName)
        }
        XCTAssertNil(repository.find(id: "user-1"))
    }

    func testADisplayNameExactlyAtTheMaximumLengthIsAccepted() {
        let repository = ProfileRepository()
        let maxName = String(repeating: "a", count: ProfileRepository.maxDisplayNameLength)
        try! repository.save(Profile(id: "user-1", displayName: maxName, photo: validPhoto()))

        XCTAssertEqual(repository.find(id: "user-1")?.displayName, maxName)
    }

    func testADisplayNameOneCharacterOverTheMaximumLengthThrowsAndPersistsNothing() {
        let repository = ProfileRepository()
        let tooLong = String(repeating: "a", count: ProfileRepository.maxDisplayNameLength + 1)

        XCTAssertThrowsError(
            try repository.save(Profile(id: "user-1", displayName: tooLong, photo: validPhoto()))
        ) { error in
            XCTAssertEqual(error as? ProfileRepositoryError, .displayNameTooLong)
        }
        XCTAssertNil(repository.find(id: "user-1"))
    }

    func testADisplayNameContainingANewlineThrowsAndPersistsNothing() {
        // A newline is a display-spoofing / log-injection surface once the name
        // is rendered in lists, notifications and logs.
        let repository = ProfileRepository()

        XCTAssertThrowsError(
            try repository.save(Profile(id: "user-1", displayName: "Ada\nLovelace", photo: validPhoto()))
        ) { error in
            XCTAssertEqual(error as? ProfileRepositoryError, .displayNameContainsControlCharacter)
        }
        XCTAssertNil(repository.find(id: "user-1"))
    }

    func testADisplayNameContainingACarriageReturnThrowsAndPersistsNothing() {
        let repository = ProfileRepository()

        XCTAssertThrowsError(
            try repository.save(Profile(id: "user-1", displayName: "Ada\rLovelace", photo: validPhoto()))
        ) { error in
            XCTAssertEqual(error as? ProfileRepositoryError, .displayNameContainsControlCharacter)
        }
        XCTAssertNil(repository.find(id: "user-1"))
    }

    func testADisplayNameIsStoredWithoutItsSurroundingWhitespace() {
        // Validates the check-and-store alignment: the trimmed value must be
        // what the repository keeps, not the padded original.
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "  Ada Lovelace  ", photo: validPhoto()))

        XCTAssertEqual(repository.find(id: "user-1")?.displayName, "Ada Lovelace")
    }

    func testAPaddedNameAtTheLimitIsStoredWithinTheLimit() {
        // A name padded with surrounding whitespace is trimmed before the length
        // check, so a name that is exactly at the limit after trimming must be
        // accepted and stored at the limit — not rejected because the padded
        // form is longer.
        let repository = ProfileRepository()
        let padded = "  " + String(repeating: "a", count: ProfileRepository.maxDisplayNameLength) + "  "
        try! repository.save(Profile(id: "user-1", displayName: padded, photo: validPhoto()))

        XCTAssertEqual(
            repository.find(id: "user-1")?.displayName.unicodeScalars.count,
            ProfileRepository.maxDisplayNameLength
        )
    }

    func testADisplayNameOf50SimpleEmojiAtTheMaximumLengthIsAccepted() {
        // With length measured in Unicode scalar values, 50 single-scalar emoji
        // is exactly the limit — the same fix as the Kotlin lane (issue #36,
        // item 3).
        let repository = ProfileRepository()
        let fiftyEmoji = String(repeating: "\u{1F600}", count: ProfileRepository.maxDisplayNameLength)

        try! repository.save(Profile(id: "user-1", displayName: fiftyEmoji, photo: validPhoto()))

        XCTAssertEqual(repository.find(id: "user-1")?.displayName, fiftyEmoji)
    }

    func testADisplayNameOf51SimpleEmojiOverTheMaximumLengthThrows() {
        let repository = ProfileRepository()
        let fiftyOneEmoji = String(repeating: "\u{1F600}", count: ProfileRepository.maxDisplayNameLength + 1)

        XCTAssertThrowsError(
            try repository.save(Profile(id: "user-1", displayName: fiftyOneEmoji, photo: validPhoto()))
        ) { error in
            XCTAssertEqual(error as? ProfileRepositoryError, .displayNameTooLong)
        }
        XCTAssertNil(repository.find(id: "user-1"))
    }

    // MARK: - Update semantics

    func testSavingTwiceForTheSameIdOverwritesRatherThanDuplicating() {
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Grace", photo: validPhoto()))
        try! repository.save(Profile(id: "user-1", displayName: "Grace Hopper", photo: validPhoto()))

        XCTAssertEqual(repository.find(id: "user-1")?.displayName, "Grace Hopper")
    }

    // MARK: - deleteAccount

    func testDeleteAccountRemovesTheStoredProfileSoALaterFindReturnsNil() {
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto()))

        XCTAssertTrue(repository.deleteAccount(id: "user-1"))
        XCTAssertNil(repository.find(id: "user-1"))
    }

    func testDeleteAccountOnAnUnknownIdReturnsFalseWithoutThrowing() {
        let repository = ProfileRepository()

        XCTAssertFalse(repository.deleteAccount(id: "never-saved"))
    }

    func testDeleteAccountRemovesTheProfileIncludingItsBiography() {
        // P2 (enforceable): account deletion removes all associated data,
        // including the biography, in the same call.
        let repository = ProfileRepository()
        try! repository.save(
            Profile(
                id: "user-1",
                displayName: "Ada Lovelace",
                photo: validPhoto(),
                biography: "Mathematician and first programmer."
            )
        )

        XCTAssertTrue(repository.deleteAccount(id: "user-1"))
        XCTAssertNil(repository.find(id: "user-1"))
    }

    // MARK: - biography validation

    func testSavingABiographyWithinTheLimitPersistsTheTrimmedValue() {
        let repository = ProfileRepository()
        try! repository.save(
            Profile(
                id: "user-1",
                displayName: "Ada Lovelace",
                photo: validPhoto(),
                biography: "  Mathematician and first programmer.  "
            )
        )

        XCTAssertEqual(
            repository.find(id: "user-1")?.biography,
            "Mathematician and first programmer."
        )
    }

    func testABiographyOneCharacterOverTheMaximumLengthThrowsAndPersistsNothing() {
        let repository = ProfileRepository()
        let tooLong = String(repeating: "a", count: ProfileRepository.maxBiographyLength + 1)

        XCTAssertThrowsError(
            try repository.save(
                Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto(), biography: tooLong)
            )
        ) { error in
            XCTAssertEqual(error as? ProfileRepositoryError, .biographyTooLong)
        }
        XCTAssertNil(repository.find(id: "user-1"))
    }

    // MARK: - photo validation

    func testSavingAValidPhotoPeristsItForAnIndependentReadBack() {
        let repository = ProfileRepository()
        let bytes: [UInt8] = [9, 8, 7, 6, 5]
        try! repository.save(
            Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto(bytes: bytes, format: "png"))
        )

        let found = repository.find(id: "user-1")?.photo
        XCTAssertEqual(found?.format, "png")
        XCTAssertEqual(found?.bytes, bytes)
    }

    func testAPhotoFormatIsStoredNormalisedToLowercaseAndTrimmed() {
        let repository = ProfileRepository()
        try! repository.save(
            Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto(format: "  PNG  "))
        )

        XCTAssertEqual(repository.find(id: "user-1")?.photo?.format, "png")
    }

    func testSavingAPhotoWithAnUnsupportedFormatThrowsAndPersistsNothing() {
        let repository = ProfileRepository()

        XCTAssertThrowsError(
            try repository.save(
                Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto(format: "gif"))
            )
        ) { error in
            XCTAssertEqual(error as? ProfileRepositoryError, .unsupportedPhotoFormat)
        }
        XCTAssertNil(repository.find(id: "user-1"))
    }

    func testSavingAPhotoLargerThanTheMaximumSizeThrowsAndPersistsNothing() {
        let repository = ProfileRepository()
        let tooBig = [UInt8](repeating: 0, count: ProfileRepository.maxPhotoSizeBytes + 1)

        XCTAssertThrowsError(
            try repository.save(
                Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto(bytes: tooBig))
            )
        ) { error in
            XCTAssertEqual(error as? ProfileRepositoryError, .photoTooLarge)
        }
        XCTAssertNil(repository.find(id: "user-1"))
    }

    func testAPhotoExactlyAtTheMaximumSizeIsAccepted() {
        let repository = ProfileRepository()
        let maxBytes = [UInt8](repeating: 0, count: ProfileRepository.maxPhotoSizeBytes)

        try! repository.save(
            Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto(bytes: maxBytes))
        )

        XCTAssertEqual(
            repository.find(id: "user-1")?.photo?.bytes.count,
            ProfileRepository.maxPhotoSizeBytes
        )
    }

    func testReplacingAnExistingPhotoWithANewValidPhotoPerisistsTheNewPhoto() {
        // Update semantics: saving a new valid photo for an existing id
        // overwrites the whole record.
        let repository = ProfileRepository()
        let originalBytes: [UInt8] = [1, 1, 1]
        try! repository.save(
            Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto(bytes: originalBytes, format: "png"))
        )

        let newBytes: [UInt8] = [2, 2, 2, 2]
        try! repository.save(
            Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto(bytes: newBytes, format: "jpeg"))
        )

        let found = repository.find(id: "user-1")?.photo
        XCTAssertEqual(found?.format, "jpeg")
        XCTAssertEqual(found?.bytes, newBytes)
    }

    func testAttemptingToReplaceAnExistingPhotoWithAnInvalidNewPhotoLeavesTheOriginalPhotoIntact() {
        // Validation throws before the dict is reassigned, so a failed replace
        // attempt leaves the previously stored photo untouched.
        let repository = ProfileRepository()
        let originalBytes: [UInt8] = [1, 1, 1]
        try! repository.save(
            Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto(bytes: originalBytes, format: "png"))
        )

        XCTAssertThrowsError(
            try repository.save(
                Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto(format: "gif"))
            )
        )

        let found = repository.find(id: "user-1")?.photo
        XCTAssertEqual(found?.format, "png")
        XCTAssertEqual(found?.bytes, originalBytes)
    }

    func testDeleteAccountRemovesTheProfileIncludingItsPhoto() {
        // P2 (enforceable): account deletion removes all associated data,
        // including the stored photo, in the same call.
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto()))

        XCTAssertTrue(repository.deleteAccount(id: "user-1"))
        XCTAssertNil(repository.find(id: "user-1"))
    }

    func testACPROF01301SavingAProfileWithAllMandatoryFieldsValidSucceedsAndReadsBackTheSameData() {
        // AC-PROF-013-01: with both mandatory fields valid (displayName and
        // photo), save() returns normally — the repository-layer signal that the
        // profile was saved — and an independent find() reads back the same data.
        let repository = ProfileRepository()
        let bytes: [UInt8] = [4, 3, 2, 1]
        try! repository.save(
            Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto(bytes: bytes, format: "png"))
        )

        let found = repository.find(id: "user-1")
        XCTAssertEqual(found?.displayName, "Ada Lovelace")
        XCTAssertEqual(found?.photo?.format, "png")
        XCTAssertEqual(found?.photo?.bytes, bytes)
    }

    func testACPROF01301SavingAProfileWithAnInvalidMandatoryFieldThrowsAndFindReturnsNil() {
        // AC-PROF-013-01 (negative): a mandatory field that fails validation —
        // here the mandatory photo carries an unsupported format — makes save()
        // throw before anything is stored, so a later find() returns nil.
        let repository = ProfileRepository()

        XCTAssertThrowsError(
            try repository.save(
                Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto(format: "gif"))
            )
        ) { error in
            XCTAssertEqual(error as? ProfileRepositoryError, .unsupportedPhotoFormat)
        }
        XCTAssertNil(repository.find(id: "user-1"))
    }

    // MARK: - interests / activities limits

    func testInterestsAndActivitiesExactlyAtTheirLimitsAreAccepted() {
        let repository = ProfileRepository()
        let interests = (0..<ProfileRepository.maxInterests).map { "interest-\($0)" }
        let activities = (0..<ProfileRepository.maxActivities).map { "activity-\($0)" }

        try! repository.save(
            Profile(
                id: "user-1",
                displayName: "Ada Lovelace",
                photo: validPhoto(),
                interests: interests,
                activities: activities
            )
        )

        XCTAssertEqual(repository.find(id: "user-1")?.interests, interests)
        XCTAssertEqual(repository.find(id: "user-1")?.activities, activities)
    }

    func testInterestsOneEntryOverTheMaximumCountThrowsAndPersistsNothing() {
        let repository = ProfileRepository()
        let tooMany = (0...(ProfileRepository.maxInterests)).map { "interest-\($0)" }

        XCTAssertThrowsError(
            try repository.save(
                Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto(), interests: tooMany)
            )
        ) { error in
            XCTAssertEqual(error as? ProfileRepositoryError, .tooManyInterests)
        }
        XCTAssertNil(repository.find(id: "user-1"))
    }

    func testActivitiesOneEntryOverTheMaximumCountThrowsAndPersistsNothing() {
        let repository = ProfileRepository()
        let tooMany = (0...(ProfileRepository.maxActivities)).map { "activity-\($0)" }

        XCTAssertThrowsError(
            try repository.save(
                Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto(), activities: tooMany)
            )
        ) { error in
            XCTAssertEqual(error as? ProfileRepositoryError, .tooManyActivities)
        }
        XCTAssertNil(repository.find(id: "user-1"))
    }

    func testAnAtLimitInterestsListIsAcceptedAlongsideAnOverLimitActivitiesListBeingRejected() {
        // AC-PROF-021-01: the two limits are enforced independently. A list at
        // the interests limit does not excuse an over-limit activities list, and
        // the activities failure is what rejects the save — nothing is stored.
        let repository = ProfileRepository()
        let interestsAtLimit = (0..<ProfileRepository.maxInterests).map { "interest-\($0)" }
        let activitiesOverLimit = (0...ProfileRepository.maxActivities).map { "activity-\($0)" }

        XCTAssertThrowsError(
            try repository.save(
                Profile(
                    id: "user-1",
                    displayName: "Ada Lovelace",
                    photo: validPhoto(),
                    interests: interestsAtLimit,
                    activities: activitiesOverLimit
                )
            )
        ) { error in
            XCTAssertEqual(error as? ProfileRepositoryError, .tooManyActivities)
        }
        XCTAssertNil(repository.find(id: "user-1"))
    }

    func testAnAtLimitActivitiesListIsAcceptedAlongsideAnOverLimitInterestsListBeingRejected() {
        // AC-PROF-021-01: the mirror case — a list at the activities limit does
        // not excuse an over-limit interests list, confirming each count is
        // checked on its own field and nothing is stored.
        let repository = ProfileRepository()
        let interestsOverLimit = (0...ProfileRepository.maxInterests).map { "interest-\($0)" }
        let activitiesAtLimit = (0..<ProfileRepository.maxActivities).map { "activity-\($0)" }

        XCTAssertThrowsError(
            try repository.save(
                Profile(
                    id: "user-1",
                    displayName: "Ada Lovelace",
                    photo: validPhoto(),
                    interests: interestsOverLimit,
                    activities: activitiesAtLimit
                )
            )
        ) { error in
            XCTAssertEqual(error as? ProfileRepositoryError, .tooManyInterests)
        }
        XCTAssertNil(repository.find(id: "user-1"))
    }

    // MARK: - isComplete

    func testAFreshlyCreatedProfileWithAPhotoIsComplete() {
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto()))

        XCTAssertTrue(repository.find(id: "user-1")?.isComplete == true)
    }

    // MARK: - removePhoto

    func testRemovePhotoClearsThePhotoOfAnExistingProfile() {
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto()))

        XCTAssertTrue(repository.removePhoto(id: "user-1"))
        XCTAssertNil(repository.find(id: "user-1")?.photo)
    }

    func testRemovePhotoLeavesTheProfileIncomplete() {
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto()))

        XCTAssertTrue(repository.removePhoto(id: "user-1"))
        XCTAssertFalse(repository.find(id: "user-1")?.isComplete == true)
    }

    func testRemovePhotoOnAnUnknownIdReturnsFalseWithoutThrowing() {
        let repository = ProfileRepository()

        XCTAssertFalse(repository.removePhoto(id: "never-saved"))
    }

    // MARK: - AC#2: open-to-friends toggle

    func testFreshlyCreatedProfileHasOpenToFriendsFalseByDefault() {
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto()))

        XCTAssertFalse(repository.find(id: "user-1")?.openToFriends ?? true)
    }

    func testSetOpenToFriendsTrueMarksProfileAsOpen() {
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto()))

        XCTAssertTrue(repository.setOpenToFriends(id: "user-1", open: true))
        XCTAssertTrue(repository.find(id: "user-1")?.openToFriends ?? false)
    }

    func testSetOpenToFriendsFalseMarksProfileAsClosed() {
        let repository = ProfileRepository()
        try! repository.save(
            Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto(), openToFriends: true)
        )

        XCTAssertTrue(repository.setOpenToFriends(id: "user-1", open: false))
        XCTAssertFalse(repository.find(id: "user-1")?.openToFriends ?? true)
    }

    func testSetOpenToFriendsOnUnknownIdReturnsFalse() {
        let repository = ProfileRepository()

        XCTAssertFalse(repository.setOpenToFriends(id: "never-saved", open: true))
    }

    func testFindOpenReturnsOnlyOpenProfiles() {
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto()))
        try! repository.save(Profile(id: "user-2", displayName: "Grace Hopper", photo: validPhoto()))
        repository.setOpenToFriends(id: "user-1", open: true)

        let open = repository.findOpen()
        XCTAssertEqual(open.count, 1)
        XCTAssertEqual(open.first?.id, "user-1")
    }

    func testFindOpenExcludesProfileAfterFlagIsTurnedOff() {
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto()))
        repository.setOpenToFriends(id: "user-1", open: true)
        XCTAssertTrue(repository.findOpen().contains(where: { $0.id == "user-1" }))

        repository.setOpenToFriends(id: "user-1", open: false)
        XCTAssertFalse(repository.findOpen().contains(where: { $0.id == "user-1" }))
    }

    func testFindOpenReturnsEmptyListWhenNoProfilesAreOpen() {
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto()))

        XCTAssertTrue(repository.findOpen().isEmpty)
    }

    func testProfileSavedWithOpenToFriendsTrueAppearsInFindOpenImmediately() {
        let repository = ProfileRepository()
        try! repository.save(
            Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto(), openToFriends: true)
        )

        let open = repository.findOpen()
        XCTAssertEqual(open.count, 1)
        XCTAssertEqual(open.first?.id, "user-1")
    }

    func testFindOpenReturnsAllOpenProfilesWhenMultipleExist() {
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto()))
        try! repository.save(Profile(id: "user-2", displayName: "Grace Hopper", photo: validPhoto()))
        try! repository.save(Profile(id: "user-3", displayName: "Alan Turing", photo: validPhoto()))
        repository.setOpenToFriends(id: "user-1", open: true)
        repository.setOpenToFriends(id: "user-2", open: true)

        let open = repository.findOpen()
        XCTAssertEqual(open.count, 2)
        XCTAssertTrue(open.contains(where: { $0.id == "user-1" }))
        XCTAssertTrue(open.contains(where: { $0.id == "user-2" }))
        XCTAssertFalse(open.contains(where: { $0.id == "user-3" }))
    }

    // MARK: - AC#7: block user

    func testBlockUserReturnsTrueWhenBothProfilesExist() {
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto()))
        try! repository.save(Profile(id: "user-2", displayName: "Grace Hopper", photo: validPhoto()))

        XCTAssertTrue(repository.blockUser(blockerId: "user-1", blockedId: "user-2"))
    }

    func testBlockUserReturnsFalseWhenBlockerDoesNotExist() {
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-2", displayName: "Grace Hopper", photo: validPhoto()))

        XCTAssertFalse(repository.blockUser(blockerId: "unknown", blockedId: "user-2"))
    }

    func testBlockUserReturnsFalseWhenBlockedUserDoesNotExist() {
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto()))

        XCTAssertFalse(repository.blockUser(blockerId: "user-1", blockedId: "unknown"))
    }

    func testBlockUserIsIdempotentBlockingTheSamePersonTwiceStillReturnsTrue() {
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto()))
        try! repository.save(Profile(id: "user-2", displayName: "Grace Hopper", photo: validPhoto()))
        repository.blockUser(blockerId: "user-1", blockedId: "user-2")

        XCTAssertTrue(repository.blockUser(blockerId: "user-1", blockedId: "user-2"))
    }

    func testIsBlockedReturnsTrueAfterAUserIsBlocked() {
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto()))
        try! repository.save(Profile(id: "user-2", displayName: "Grace Hopper", photo: validPhoto()))
        repository.blockUser(blockerId: "user-1", blockedId: "user-2")

        XCTAssertTrue(repository.isBlocked(blockerId: "user-1", blockedId: "user-2"))
    }

    func testIsBlockedReturnsFalseBeforeAnyBlockIsRecorded() {
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto()))
        try! repository.save(Profile(id: "user-2", displayName: "Grace Hopper", photo: validPhoto()))

        XCTAssertFalse(repository.isBlocked(blockerId: "user-1", blockedId: "user-2"))
    }

    func testIsBlockedIsDirectionalBlockingAToB_DoesNotBlockBToA() {
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto()))
        try! repository.save(Profile(id: "user-2", displayName: "Grace Hopper", photo: validPhoto()))
        repository.blockUser(blockerId: "user-1", blockedId: "user-2")

        XCTAssertFalse(repository.isBlocked(blockerId: "user-2", blockedId: "user-1"))
    }

    func testDiscoverExcludesAProfileThatTheSearcherHasBlocked() {
        // AC#7: a blocked person never appears in the blocker's discovery results.
        let repository = ProfileRepository()
        let searcher = Profile(id: "searcher", displayName: "Searcher", photo: validPhoto())
        try! repository.save(searcher)
        try! repository.save(Profile(
            id: "blocked",
            displayName: "Blocked Person",
            photo: validPhoto(),
            openToFriends: true
        ))
        repository.blockUser(blockerId: "searcher", blockedId: "blocked")

        let results = repository.discover(searcher: searcher)

        XCTAssertFalse(results.contains(where: { $0.profile.id == "blocked" }))
    }

    func testDiscoverStillReturnsOtherOpenProfilesWhenOneIsBlocked() {
        let repository = ProfileRepository()
        let searcher = Profile(
            id: "searcher",
            displayName: "Searcher",
            photo: validPhoto(),
            interests: ["jazz"]
        )
        try! repository.save(searcher)
        try! repository.save(Profile(
            id: "ada",
            displayName: "Ada Lovelace",
            photo: validPhoto(),
            interests: ["jazz"],
            openToFriends: true
        ))
        try! repository.save(Profile(
            id: "grace",
            displayName: "Grace Hopper",
            photo: validPhoto(),
            interests: ["jazz"],
            openToFriends: true
        ))
        repository.blockUser(blockerId: "searcher", blockedId: "ada")

        let results = repository.discover(searcher: searcher)

        XCTAssertEqual(results.count, 1)
        XCTAssertEqual(results[0].profile.id, "grace")
    }

    // AC#1 / constitution P3: age field and minimum-age enforcement

    func testAProfileWithTheMinimumAgeIsAccepted() {
        // AC#1: the profile carries an age. minAge (16) is the lowest accepted
        // value, reflecting that the brief includes 16- and 17-year-olds.
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto(), age: ProfileRepository.minAge))

        XCTAssertEqual(repository.find(id: "user-1")?.age, ProfileRepository.minAge)
    }

    func testAProfileAgeBelowTheMinimumThrowsAndPersistsNothing() {
        // Constitution P3 (enforceable): any feature reachable by someone under
        // 18 must state its age-assurance mechanism. The domain-layer floor
        // rejects anyone below minAge (16) before anything is stored.
        let repository = ProfileRepository()

        XCTAssertThrowsError(
            try repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto(), age: ProfileRepository.minAge - 1))
        ) { error in
            XCTAssertEqual(error as? ProfileRepositoryError, ProfileRepositoryError.ageBelowMinimum)
        }
        XCTAssertNil(repository.find(id: "user-1"))
    }

    func testAProfileAtAge17IsAcceptedAsAValidMinorAboveTheMinimum() {
        // The brief names 16-and-17-year-olds as a user segment. Both are
        // above minAge (16) and must be accepted.
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto(), age: 17))

        XCTAssertEqual(repository.find(id: "user-1")?.age, 17)
    }

    func testAProfileAtAge18IsAcceptedAsAnAdult() {
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto(), age: 18))

        XCTAssertEqual(repository.find(id: "user-1")?.age, 18)
    }

    func testAgeIsStoredAndReadsBackTheSameValue() {
        let repository = ProfileRepository()
        try! repository.save(Profile(id: "user-1", displayName: "Ada Lovelace", photo: validPhoto(), age: 25))

        XCTAssertEqual(repository.find(id: "user-1")?.age, 25)
    }
}
