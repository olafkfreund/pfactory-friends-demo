import XCTest

// nixpkgs swift 5.10 ships no libIndexStore.so, so SwiftPM's automatic test
// discovery fails (NixOS/nixpkgs#379859). This manifest is the pre-5.4
// convention that replaces it. A test missing from this list silently does not
// run, so every new test must be added here.
extension MatchScoreTests {
    static let __allTests = [
        ("testHalfTheInterestsOverlap", testHalfTheInterestsOverlap),
        ("testEmptyInterestsScoreZeroRatherThanCrashing", testEmptyInterestsScoreZeroRatherThanCrashing),
        // AC#1: combined score including availability
        ("testCombinedScoreWithNoAvailabilityFallsBackToInterestScore", testCombinedScoreWithNoAvailabilityFallsBackToInterestScore),
        ("testCombinedScoreIsMeanOfInterestAndAvailabilityScores", testCombinedScoreIsMeanOfInterestAndAvailabilityScores),
        ("testCombinedScoreWithNoAvailabilityOverlapReducesOverallScore", testCombinedScoreWithNoAvailabilityOverlapReducesOverallScore),
        ("testCombinedScoreWithEmptyInterestsAndAvailabilityScoresZero", testCombinedScoreWithEmptyInterestsAndAvailabilityScoresZero),
    ]
}

// Profile model parity (Swift ↔ Kotlin, constitution P9) + AC#2
extension ProfileRepositoryTests {
    static let __allTests = [
        // Basic save / find
        ("testSavingAValidDisplayNamePersistsItForAnIndependentReadBack", testSavingAValidDisplayNamePersistsItForAnIndependentReadBack),
        // id validation
        ("testSavingABlankIdThrowsAndPersistsNothing", testSavingABlankIdThrowsAndPersistsNothing),
        ("testSavingAWhitespaceOnlyIdThrowsAndPersistsNothing", testSavingAWhitespaceOnlyIdThrowsAndPersistsNothing),
        // displayName validation
        ("testSavingABlankDisplayNameThrowsAndPersistsNothing", testSavingABlankDisplayNameThrowsAndPersistsNothing),
        ("testADisplayNameExactlyAtTheMaximumLengthIsAccepted", testADisplayNameExactlyAtTheMaximumLengthIsAccepted),
        ("testADisplayNameOneCharacterOverTheMaximumLengthThrowsAndPersistsNothing", testADisplayNameOneCharacterOverTheMaximumLengthThrowsAndPersistsNothing),
        ("testADisplayNameContainingANewlineThrowsAndPersistsNothing", testADisplayNameContainingANewlineThrowsAndPersistsNothing),
        ("testADisplayNameContainingACarriageReturnThrowsAndPersistsNothing", testADisplayNameContainingACarriageReturnThrowsAndPersistsNothing),
        ("testADisplayNameIsStoredWithoutItsSurroundingWhitespace", testADisplayNameIsStoredWithoutItsSurroundingWhitespace),
        ("testADisplayNameOf50SimpleEmojiAtTheMaximumLengthIsAccepted", testADisplayNameOf50SimpleEmojiAtTheMaximumLengthIsAccepted),
        ("testADisplayNameOf51SimpleEmojiOverTheMaximumLengthThrows", testADisplayNameOf51SimpleEmojiOverTheMaximumLengthThrows),
        // Update semantics
        ("testSavingTwiceForTheSameIdOverwritesRatherThanDuplicating", testSavingTwiceForTheSameIdOverwritesRatherThanDuplicating),
        // deleteAccount
        ("testDeleteAccountRemovesTheStoredProfileSoALaterFindReturnsNil", testDeleteAccountRemovesTheStoredProfileSoALaterFindReturnsNil),
        ("testDeleteAccountOnAnUnknownIdReturnsFalseWithoutThrowing", testDeleteAccountOnAnUnknownIdReturnsFalseWithoutThrowing),
        // biography validation
        ("testSavingABiographyWithinTheLimitPersistsTheTrimmedValue", testSavingABiographyWithinTheLimitPersistsTheTrimmedValue),
        ("testABiographyOneCharacterOverTheMaximumLengthThrowsAndPersistsNothing", testABiographyOneCharacterOverTheMaximumLengthThrowsAndPersistsNothing),
        // photo validation
        ("testSavingAValidPhotoPeristsItForAnIndependentReadBack", testSavingAValidPhotoPeristsItForAnIndependentReadBack),
        ("testAPhotoFormatIsStoredNormalisedToLowercaseAndTrimmed", testAPhotoFormatIsStoredNormalisedToLowercaseAndTrimmed),
        ("testSavingAPhotoWithAnUnsupportedFormatThrowsAndPersistsNothing", testSavingAPhotoWithAnUnsupportedFormatThrowsAndPersistsNothing),
        ("testSavingAPhotoLargerThanTheMaximumSizeThrowsAndPersistsNothing", testSavingAPhotoLargerThanTheMaximumSizeThrowsAndPersistsNothing),
        ("testAPhotoExactlyAtTheMaximumSizeIsAccepted", testAPhotoExactlyAtTheMaximumSizeIsAccepted),
        ("testReplacingAnExistingPhotoWithANewValidPhotoPerisistsTheNewPhoto", testReplacingAnExistingPhotoWithANewValidPhotoPerisistsTheNewPhoto),
        ("testAttemptingToReplaceAnExistingPhotoWithAnInvalidNewPhotoLeavesTheOriginalPhotoIntact", testAttemptingToReplaceAnExistingPhotoWithAnInvalidNewPhotoLeavesTheOriginalPhotoIntact),
        // interests / activities
        ("testInterestsAndActivitiesExactlyAtTheirLimitsAreAccepted", testInterestsAndActivitiesExactlyAtTheirLimitsAreAccepted),
        ("testInterestsOneEntryOverTheMaximumCountThrowsAndPersistsNothing", testInterestsOneEntryOverTheMaximumCountThrowsAndPersistsNothing),
        ("testActivitiesOneEntryOverTheMaximumCountThrowsAndPersistsNothing", testActivitiesOneEntryOverTheMaximumCountThrowsAndPersistsNothing),
        // isComplete
        ("testAFreshlyCreatedProfileWithAPhotoIsComplete", testAFreshlyCreatedProfileWithAPhotoIsComplete),
        // removePhoto
        ("testRemovePhotoClearsThePhotoOfAnExistingProfile", testRemovePhotoClearsThePhotoOfAnExistingProfile),
        ("testRemovePhotoLeavesTheProfileIncomplete", testRemovePhotoLeavesTheProfileIncomplete),
        ("testRemovePhotoOnAnUnknownIdReturnsFalseWithoutThrowing", testRemovePhotoOnAnUnknownIdReturnsFalseWithoutThrowing),
        // AC#2: open-to-friends toggle
        ("testFreshlyCreatedProfileHasOpenToFriendsFalseByDefault", testFreshlyCreatedProfileHasOpenToFriendsFalseByDefault),
        ("testSetOpenToFriendsTrueMarksProfileAsOpen", testSetOpenToFriendsTrueMarksProfileAsOpen),
        ("testSetOpenToFriendsFalseMarksProfileAsClosed", testSetOpenToFriendsFalseMarksProfileAsClosed),
        ("testSetOpenToFriendsOnUnknownIdReturnsFalse", testSetOpenToFriendsOnUnknownIdReturnsFalse),
        ("testFindOpenReturnsOnlyOpenProfiles", testFindOpenReturnsOnlyOpenProfiles),
        ("testFindOpenExcludesProfileAfterFlagIsTurnedOff", testFindOpenExcludesProfileAfterFlagIsTurnedOff),
        ("testFindOpenReturnsEmptyListWhenNoProfilesAreOpen", testFindOpenReturnsEmptyListWhenNoProfilesAreOpen),
        ("testProfileSavedWithOpenToFriendsTrueAppearsInFindOpenImmediately", testProfileSavedWithOpenToFriendsTrueAppearsInFindOpenImmediately),
        ("testFindOpenReturnsAllOpenProfilesWhenMultipleExist", testFindOpenReturnsAllOpenProfilesWhenMultipleExist),
    ]
}

// AC#4: discovery ordering and explanation
extension DiscoveryTests {
    static let __allTests = [
        // ordered by score
        ("testDiscoverReturnsCandidatesOrderedByScoreDescending", testDiscoverReturnsCandidatesOrderedByScoreDescending),
        ("testDiscoverExcludesTheSearcherEvenWhenTheyHaveOpenToFriendsTrue", testDiscoverExcludesTheSearcherEvenWhenTheyHaveOpenToFriendsTrue),
        ("testDiscoverExcludesProfilesWithOpenToFriendsFalse", testDiscoverExcludesProfilesWithOpenToFriendsFalse),
        ("testDiscoverReturnsEmptyListWhenNoOpenProfilesExist", testDiscoverReturnsEmptyListWhenNoOpenProfilesExist),
        // shows why each result was surfaced
        ("testDiscoverPopulatesSharedInterestsWithTheSortedIntersectionOfInterestTags", testDiscoverPopulatesSharedInterestsWithTheSortedIntersectionOfInterestTags),
        ("testDiscoverPopulatesSharedActivitiesWithTheSortedIntersectionOfActivityTags", testDiscoverPopulatesSharedActivitiesWithTheSortedIntersectionOfActivityTags),
        ("testDiscoverReturnsEmptySharedInterestsAndActivitiesWhenThereIsNoOverlap", testDiscoverReturnsEmptySharedInterestsAndActivitiesWhenThereIsNoOverlap),
        ("testDiscoverWithEmptySearcherInterestsStillReturnsOpenProfilesWithScoreZero", testDiscoverWithEmptySearcherInterestsStillReturnsOpenProfilesWithScoreZero),
        ("testDiscoverScoreMatchesMatchScoreOutputForTheSameInputs", testDiscoverScoreMatchesMatchScoreOutputForTheSameInputs),
        ("testDiscoverSearcherWithoutOpenToFriendsCanStillBrowseOpenProfiles", testDiscoverSearcherWithoutOpenToFriendsCanStillBrowseOpenProfiles),
    ]
}

public func __allDiscoveredTests() -> [XCTestCaseEntry] {
    return [
        testCase(MatchScoreTests.__allTests),
        testCase(ProfileRepositoryTests.__allTests),
        testCase(DiscoveryTests.__allTests),
    ]
}
