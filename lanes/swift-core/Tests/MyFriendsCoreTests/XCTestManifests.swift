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
        ("testAPaddedNameAtTheLimitIsStoredWithinTheLimit", testAPaddedNameAtTheLimitIsStoredWithinTheLimit),
        ("testADisplayNameOf50SimpleEmojiAtTheMaximumLengthIsAccepted", testADisplayNameOf50SimpleEmojiAtTheMaximumLengthIsAccepted),
        ("testADisplayNameOf51SimpleEmojiOverTheMaximumLengthThrows", testADisplayNameOf51SimpleEmojiOverTheMaximumLengthThrows),
        // Update semantics
        ("testSavingTwiceForTheSameIdOverwritesRatherThanDuplicating", testSavingTwiceForTheSameIdOverwritesRatherThanDuplicating),
        // deleteAccount
        ("testDeleteAccountRemovesTheStoredProfileSoALaterFindReturnsNil", testDeleteAccountRemovesTheStoredProfileSoALaterFindReturnsNil),
        ("testDeleteAccountOnAnUnknownIdReturnsFalseWithoutThrowing", testDeleteAccountOnAnUnknownIdReturnsFalseWithoutThrowing),
        ("testDeleteAccountRemovesTheProfileIncludingItsBiography", testDeleteAccountRemovesTheProfileIncludingItsBiography),
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
        ("testDeleteAccountRemovesTheProfileIncludingItsPhoto", testDeleteAccountRemovesTheProfileIncludingItsPhoto),
        ("testACPROF01301SavingAProfileWithAllMandatoryFieldsValidSucceedsAndReadsBackTheSameData", testACPROF01301SavingAProfileWithAllMandatoryFieldsValidSucceedsAndReadsBackTheSameData),
        ("testACPROF01301SavingAProfileWithAnInvalidMandatoryFieldThrowsAndFindReturnsNil", testACPROF01301SavingAProfileWithAnInvalidMandatoryFieldThrowsAndFindReturnsNil),
        // interests / activities
        ("testInterestsAndActivitiesExactlyAtTheirLimitsAreAccepted", testInterestsAndActivitiesExactlyAtTheirLimitsAreAccepted),
        ("testInterestsOneEntryOverTheMaximumCountThrowsAndPersistsNothing", testInterestsOneEntryOverTheMaximumCountThrowsAndPersistsNothing),
        ("testActivitiesOneEntryOverTheMaximumCountThrowsAndPersistsNothing", testActivitiesOneEntryOverTheMaximumCountThrowsAndPersistsNothing),
        ("testAnAtLimitInterestsListIsAcceptedAlongsideAnOverLimitActivitiesListBeingRejected", testAnAtLimitInterestsListIsAcceptedAlongsideAnOverLimitActivitiesListBeingRejected),
        ("testAnAtLimitActivitiesListIsAcceptedAlongsideAnOverLimitInterestsListBeingRejected", testAnAtLimitActivitiesListIsAcceptedAlongsideAnOverLimitInterestsListBeingRejected),
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
        // AC#7: block user
        ("testBlockUserReturnsTrueWhenBothProfilesExist", testBlockUserReturnsTrueWhenBothProfilesExist),
        ("testBlockUserReturnsFalseWhenBlockerDoesNotExist", testBlockUserReturnsFalseWhenBlockerDoesNotExist),
        ("testBlockUserReturnsFalseWhenBlockedUserDoesNotExist", testBlockUserReturnsFalseWhenBlockedUserDoesNotExist),
        ("testBlockUserIsIdempotentBlockingTheSamePersonTwiceStillReturnsTrue", testBlockUserIsIdempotentBlockingTheSamePersonTwiceStillReturnsTrue),
        ("testIsBlockedReturnsTrueAfterAUserIsBlocked", testIsBlockedReturnsTrueAfterAUserIsBlocked),
        ("testIsBlockedReturnsFalseBeforeAnyBlockIsRecorded", testIsBlockedReturnsFalseBeforeAnyBlockIsRecorded),
        ("testIsBlockedIsDirectionalBlockingAToB_DoesNotBlockBToA", testIsBlockedIsDirectionalBlockingAToB_DoesNotBlockBToA),
        ("testDiscoverExcludesAProfileThatTheSearcherHasBlocked", testDiscoverExcludesAProfileThatTheSearcherHasBlocked),
        ("testDiscoverStillReturnsOtherOpenProfilesWhenOneIsBlocked", testDiscoverStillReturnsOtherOpenProfilesWhenOneIsBlocked),
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
        // AC#3: radius-based discovery
        ("testDiscoverWithRadiusReturnsOnlyProfilesWithinThatRadius", testDiscoverWithRadiusReturnsOnlyProfilesWithinThatRadius),
        ("testDiscoverWithRadiusExcludesProfilesWithoutALocation", testDiscoverWithRadiusExcludesProfilesWithoutALocation),
        ("testDiscoverWithRadiusStillHonoursTheOpenToFriendsGate", testDiscoverWithRadiusStillHonoursTheOpenToFriendsGate),
        ("testDiscoverWithRadiusResultsAreOrderedByScoreDescending", testDiscoverWithRadiusResultsAreOrderedByScoreDescending),
        ("testDiscoverWithAllFourRadiusValuesUsesTheCorrectThresholds", testDiscoverWithAllFourRadiusValuesUsesTheCorrectThresholds),
    ]
}

// AC#6: messaging after mutual connection acceptance
extension MessagingTests {
    static let __allTests = [
        // AC#6: connection-state gate on sendMessage
        ("testSendMessageWithoutAnyConnectionReturnsNil", testSendMessageWithoutAnyConnectionReturnsNil),
        ("testSendMessageWithPendingConnectionReturnsNil", testSendMessageWithPendingConnectionReturnsNil),
        ("testSendMessageAfterAcceptedConnectionReturnsThePersistedMessage", testSendMessageAfterAcceptedConnectionReturnsThePersistedMessage),
        ("testSendMessageWorksInBothDirectionsAfterAcceptance", testSendMessageWorksInBothDirectionsAfterAcceptance),
        // areConnected
        ("testAreConnectedReturnsFalseBeforeAnyConnectionRequest", testAreConnectedReturnsFalseBeforeAnyConnectionRequest),
        ("testAreConnectedReturnsFalseWhenConnectionIsPending", testAreConnectedReturnsFalseWhenConnectionIsPending),
        ("testAreConnectedReturnsTrueAfterAcceptanceAndCheckIsSymmetric", testAreConnectedReturnsTrueAfterAcceptanceAndCheckIsSymmetric),
        // sendConnectionRequest
        ("testSendConnectionRequestCreatesAPendingConnection", testSendConnectionRequestCreatesAPendingConnection),
        ("testSendConnectionRequestToSelfReturnsNil", testSendConnectionRequestToSelfReturnsNil),
        ("testSendConnectionRequestWhenConnectionAlreadyExistsReturnsNil", testSendConnectionRequestWhenConnectionAlreadyExistsReturnsNil),
        // acceptConnectionRequest
        ("testAcceptConnectionRequestByRecipientMovesConnectionToAccepted", testAcceptConnectionRequestByRecipientMovesConnectionToAccepted),
        ("testAcceptConnectionRequestByRequesterInsteadOfRecipientReturnsFalse", testAcceptConnectionRequestByRequesterInsteadOfRecipientReturnsFalse),
        ("testAcceptConnectionRequestForUnknownConnectionIdReturnsFalse", testAcceptConnectionRequestForUnknownConnectionIdReturnsFalse),
        ("testAcceptConnectionRequestOnAlreadyAcceptedConnectionReturnsFalse", testAcceptConnectionRequestOnAlreadyAcceptedConnectionReturnsFalse),
        // AC#7: blocking integration
        ("testSendConnectionRequestIsRejectedWhenRecipientHasBlockedRequester", testSendConnectionRequestIsRejectedWhenRecipientHasBlockedRequester),
        ("testSendConnectionRequestIsRejectedWhenRequesterHasBlockedRecipient", testSendConnectionRequestIsRejectedWhenRequesterHasBlockedRecipient),
        ("testSendMessageIsRejectedWhenRecipientHasBlockedSender", testSendMessageIsRejectedWhenRecipientHasBlockedSender),
        // Message body validation
        ("testSendMessageWithBlankBodyReturnsNil", testSendMessageWithBlankBodyReturnsNil),
        ("testSendMessageWithBodyAtMaximumLengthIsAccepted", testSendMessageWithBodyAtMaximumLengthIsAccepted),
        ("testSendMessageWithBodyOneCharacterOverMaximumLengthReturnsNil", testSendMessageWithBodyOneCharacterOverMaximumLengthReturnsNil),
        // getMessages
        ("testGetMessagesReturnsEmptyArrayBeforeAnyMessagesAreSent", testGetMessagesReturnsEmptyArrayBeforeAnyMessagesAreSent),
        ("testGetMessagesReturnsAllMessagesBetweenTwoUsersInChronologicalOrder", testGetMessagesReturnsAllMessagesBetweenTwoUsersInChronologicalOrder),
        ("testGetMessagesIsSymmetricSwappingArgumentOrderReturnsSameList", testGetMessagesIsSymmetricSwappingArgumentOrderReturnsSameList),
        ("testGetMessagesDoesNotIncludeMessagesFromADifferentPair", testGetMessagesDoesNotIncludeMessagesFromADifferentPair),
        // AC#5: connection request rate limiting
        ("testSendConnectionRequestSucceedsForEachRequestUpToTheDailyLimit", testSendConnectionRequestSucceedsForEachRequestUpToTheDailyLimit),
        ("testSendConnectionRequestIsRejectedOnceDailyLimitIsReached", testSendConnectionRequestIsRejectedOnceDailyLimitIsReached),
        ("testConnectionRequestLimitsArePerRequesterAndDoNotAffectOtherRequesters", testConnectionRequestLimitsArePerRequesterAndDoNotAffectOtherRequesters),
        // C14: sendConnectionRequestResult — typed refusal reasons
        ("testSendConnectionRequestResultReturnsAllowedWithConnectionOnSuccess", testSendConnectionRequestResultReturnsAllowedWithConnectionOnSuccess),
        ("testSendConnectionRequestResultReturnsBlankIdWhenRequesterIdIsBlank", testSendConnectionRequestResultReturnsBlankIdWhenRequesterIdIsBlank),
        ("testSendConnectionRequestResultReturnsBlankIdWhenRecipientIdIsEmpty", testSendConnectionRequestResultReturnsBlankIdWhenRecipientIdIsEmpty),
        ("testSendConnectionRequestResultReturnsSelfRequestWhenIdsAreEqual", testSendConnectionRequestResultReturnsSelfRequestWhenIdsAreEqual),
        ("testSendConnectionRequestResultReturnsBlockedWhenRecipientBlockedRequester", testSendConnectionRequestResultReturnsBlockedWhenRecipientBlockedRequester),
        ("testSendConnectionRequestResultReturnsBlockedWhenRequesterBlockedRecipient", testSendConnectionRequestResultReturnsBlockedWhenRequesterBlockedRecipient),
        ("testSendConnectionRequestResultReturnsAlreadyExistsOnDuplicateRequest", testSendConnectionRequestResultReturnsAlreadyExistsOnDuplicateRequest),
        ("testSendConnectionRequestResultReturnsRateLimitExceededAfterDailyLimit", testSendConnectionRequestResultReturnsRateLimitExceededAfterDailyLimit),
        // C14: sendMessageResult — typed refusal reasons
        ("testSendMessageResultReturnsAllowedWithMessageOnSuccess", testSendMessageResultReturnsAllowedWithMessageOnSuccess),
        ("testSendMessageResultReturnsNotConnectedWhenNoConnectionExists", testSendMessageResultReturnsNotConnectedWhenNoConnectionExists),
        ("testSendMessageResultReturnsNotConnectedWhenConnectionIsPending", testSendMessageResultReturnsNotConnectedWhenConnectionIsPending),
        ("testSendMessageResultReturnsBlockedWhenRecipientHasBlockedSender", testSendMessageResultReturnsBlockedWhenRecipientHasBlockedSender),
        ("testSendMessageResultReturnsBlankBodyWhenBodyIsBlank", testSendMessageResultReturnsBlankBodyWhenBodyIsBlank),
        ("testSendMessageResultReturnsBodyTooLongWhenBodyExceedsLimit", testSendMessageResultReturnsBodyTooLongWhenBodyExceedsLimit),
        ("testSendMessageResultReturnsAllowedForBodyAtMaximumLength", testSendMessageResultReturnsAllowedForBodyAtMaximumLength),
    ]
}

// AC#9: offline snapshot store (own profile, accepted connections, loaded messages)
extension OfflineCacheTests {
    static let __allTests = [
        // cacheProfile
        ("testCacheProfileStoresAProfileAndGetCachedProfileReturnsIt", testCacheProfileStoresAProfileAndGetCachedProfileReturnsIt),
        ("testGetCachedProfileReturnsNilWhenNoSnapshotIsStored", testGetCachedProfileReturnsNilWhenNoSnapshotIsStored),
        ("testCacheProfileReplacesAnExistingSnapshotForTheSameId", testCacheProfileReplacesAnExistingSnapshotForTheSameId),
        ("testCacheProfileWithABlankIdReturnsFalseAndStoresNothing", testCacheProfileWithABlankIdReturnsFalseAndStoresNothing),
        // cacheConnections
        ("testCacheConnectionsStoresAcceptedConnectionsAndGetCachedConnectionsReturnsThem", testCacheConnectionsStoresAcceptedConnectionsAndGetCachedConnectionsReturnsThem),
        ("testGetCachedConnectionsReturnsAnEmptyArrayWhenNoSnapshotIsStored", testGetCachedConnectionsReturnsAnEmptyArrayWhenNoSnapshotIsStored),
        ("testCacheConnectionsDropsPendingConnectionsAC9OfflineShowsOnlyAccepted", testCacheConnectionsDropsPendingConnectionsAC9OfflineShowsOnlyAccepted),
        ("testCacheConnectionsWithABlankUserIdReturnsFalseAndStoresNothing", testCacheConnectionsWithABlankUserIdReturnsFalseAndStoresNothing),
        ("testCacheConnectionsReplacesAnExistingSnapshotForTheSameUserId", testCacheConnectionsReplacesAnExistingSnapshotForTheSameUserId),
        // cacheMessages
        ("testCacheMessagesStoresMessagesAndGetCachedMessagesReturnsThem", testCacheMessagesStoresMessagesAndGetCachedMessagesReturnsThem),
        ("testGetCachedMessagesReturnsAnEmptyArrayWhenNoSnapshotIsStoredForThatPair", testGetCachedMessagesReturnsAnEmptyArrayWhenNoSnapshotIsStoredForThatPair),
        ("testGetCachedMessagesIsSymmetricSwappingUserIdAndPeerIdReturnsTheSameList", testGetCachedMessagesIsSymmetricSwappingUserIdAndPeerIdReturnsTheSameList),
        ("testCacheMessagesWithABlankUserIdReturnsFalseAndStoresNothing", testCacheMessagesWithABlankUserIdReturnsFalseAndStoresNothing),
        ("testCacheMessagesWithABlankPeerIdReturnsFalseAndStoresNothing", testCacheMessagesWithABlankPeerIdReturnsFalseAndStoresNothing),
        ("testCacheMessagesReplacesAnExistingSnapshotForTheSamePair", testCacheMessagesReplacesAnExistingSnapshotForTheSamePair),
        // clearForUser
        ("testClearForUserRemovesTheCachedProfileForThatUser", testClearForUserRemovesTheCachedProfileForThatUser),
        ("testClearForUserRemovesTheCachedConnectionsForThatUser", testClearForUserRemovesTheCachedConnectionsForThatUser),
        ("testClearForUserRemovesCachedMessagesWhereTheUserIsAParticipant", testClearForUserRemovesCachedMessagesWhereTheUserIsAParticipant),
        ("testClearForUserDoesNotRemoveDataForOtherUsers", testClearForUserDoesNotRemoveDataForOtherUsers),
    ]
}

// AC#8: reporting a person or message
extension ReportTests {
    static let __allTests = [
        // submitReport: user target
        ("testSubmitReportForAUserWithValidArgumentsReturnsThePersistedReport", testSubmitReportForAUserWithValidArgumentsReturnsThePersistedReport),
        // submitReport: message target
        ("testSubmitReportForAMessageWithValidArgumentsReturnsThePersistedReport", testSubmitReportForAMessageWithValidArgumentsReturnsThePersistedReport),
        // submitReport: blank id validation
        ("testSubmitReportWithABlankReporterIdReturnsNil", testSubmitReportWithABlankReporterIdReturnsNil),
        ("testSubmitReportWithABlankTargetIdReturnsNil", testSubmitReportWithABlankTargetIdReturnsNil),
        // submitReport: additionalText
        ("testSubmitReportStoresTheTrimmedAdditionalText", testSubmitReportStoresTheTrimmedAdditionalText),
        ("testSubmitReportWithAdditionalTextAtTheMaximumLengthIsAccepted", testSubmitReportWithAdditionalTextAtTheMaximumLengthIsAccepted),
        ("testSubmitReportWithAdditionalTextOneCharacterOverTheMaximumLengthReturnsNil", testSubmitReportWithAdditionalTextOneCharacterOverTheMaximumLengthReturnsNil),
        // submitReport: each reason is accepted
        ("testSubmitReportAcceptsEachReportReason", testSubmitReportAcceptsEachReportReason),
        // getReportsAgainst
        ("testGetReportsAgainstReturnsAllReportsForTheGivenTarget", testGetReportsAgainstReturnsAllReportsForTheGivenTarget),
        ("testGetReportsAgainstReturnsEmptyArrayWhenNoReportsHaveBeenFiled", testGetReportsAgainstReturnsEmptyArrayWhenNoReportsHaveBeenFiled),
        ("testGetReportsAgainstDoesNotIncludeReportsForADifferentTarget", testGetReportsAgainstDoesNotIncludeReportsForADifferentTarget),
        // getReportsByReporter
        ("testGetReportsByReporterReturnsAllReportsFiledByTheGivenReporter", testGetReportsByReporterReturnsAllReportsFiledByTheGivenReporter),
        ("testGetReportsByReporterReturnsEmptyArrayWhenReporterHasFiledNoReports", testGetReportsByReporterReturnsEmptyArrayWhenReporterHasFiledNoReports),
        // duplicate reports
        ("testSubmitReportAllowsMultipleReportsFromTheSameReporterAgainstTheSameTarget", testSubmitReportAllowsMultipleReportsFromTheSameReporterAgainstTheSameTarget),
        // report ids
        ("testEachSubmittedReportGetsADistinctId", testEachSubmittedReportGetsADistinctId),
    ]
}

// AC#7 (blocking) + AC#8 (reporting): moderation outcome is independent of blocks
extension BlockModerationTests {
    static let __allTests = [
        // AC#7 part 1: a person can block multiple users
        ("testBlockUserRecordsTheBlockSoIsBlockedReturnsTrueForTheSamePair", testBlockUserRecordsTheBlockSoIsBlockedReturnsTrueForTheSamePair),
        ("testAPersonCanBlockMultipleUsersAndAllBlocksAreIndependentlyRecorded", testAPersonCanBlockMultipleUsersAndAllBlocksAreIndependentlyRecorded),
        // AC#8 + AC#7: moderation outcome is independent of blocks
        ("testAReportIsAcceptedWhenTheReporterHasBlockedTheReportedPerson", testAReportIsAcceptedWhenTheReporterHasBlockedTheReportedPerson),
        ("testAReportIsAcceptedWhenTheReportedPersonHasBlockedTheReporter", testAReportIsAcceptedWhenTheReportedPersonHasBlockedTheReporter),
        ("testAReportIsAcceptedWhenBothPartiesHaveMutuallyBlockedEachOther", testAReportIsAcceptedWhenBothPartiesHaveMutuallyBlockedEachOther),
        ("testGetReportsAgainstReturnsReportsRegardlessOfAnyBlockBetweenTheParties", testGetReportsAgainstReturnsReportsRegardlessOfAnyBlockBetweenTheParties),
        ("testGetReportsAgainstIsNotAffectedByTheReportedPersonHavingBlockedReporters", testGetReportsAgainstIsNotAffectedByTheReportedPersonHavingBlockedReporters),
        ("testAReportFiledBeforeABlockIsEstablishedRemainsVisibleToModeratorsAfterTheBlock", testAReportFiledBeforeABlockIsEstablishedRemainsVisibleToModeratorsAfterTheBlock),
        ("testBlockStateBetweenReporterAndTargetDoesNotAffectReportsFiledAboutMessages", testBlockStateBetweenReporterAndTargetDoesNotAffectReportsFiledAboutMessages),
    ]
}

public func __allDiscoveredTests() -> [XCTestCaseEntry] {
    return [
        testCase(MatchScoreTests.__allTests),
        testCase(ProfileRepositoryTests.__allTests),
        testCase(DiscoveryTests.__allTests),
        testCase(MessagingTests.__allTests),
        testCase(ReportTests.__allTests),
        testCase(OfflineCacheTests.__allTests),
        testCase(BlockModerationTests.__allTests),
    ]
}
