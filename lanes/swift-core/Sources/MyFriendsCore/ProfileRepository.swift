import Foundation

/// Errors thrown by `ProfileRepository.save(_:)` when a profile fails
/// validation.
///
/// The same validation rules are enforced in the Kotlin lane via
/// `require()` / `IllegalArgumentException`; this error type is the Swift
/// equivalent (constitution P9).
public enum ProfileRepositoryError: Error, Equatable {
    /// The profile id was blank or whitespace-only.
    case blankId
    /// The display name was blank or whitespace-only after trimming.
    case blankDisplayName
    /// The display name contained a control character (including a newline).
    case displayNameContainsControlCharacter
    /// The display name exceeded `ProfileRepository.maxDisplayNameLength`
    /// Unicode scalar values after trimming.
    case displayNameTooLong
    /// The biography exceeded `ProfileRepository.maxBiographyLength`
    /// characters after trimming.
    case biographyTooLong
    /// The photo format was not in `ProfileRepository.supportedPhotoFormats`.
    case unsupportedPhotoFormat
    /// The photo byte count exceeded `ProfileRepository.maxPhotoSizeBytes`.
    case photoTooLarge
    /// The interests list exceeded `ProfileRepository.maxInterests` entries.
    case tooManyInterests
    /// The activities list exceeded `ProfileRepository.maxActivities` entries.
    case tooManyActivities
}

/// In-process storage for `Profile` records.
///
/// Data ownership, per constitution P1: the only personal data kept here is
/// the display name, the optional photo and the optional biography. All three
/// are kept for as long as the account exists and are deleted the moment the
/// person calls `deleteAccount(id:)` — the photo, like the biography, is part
/// of the same `Profile` record, so it needs no separate cleanup. There is no
/// other copy and no background retention.
///
/// Deletion path, per constitution P2: `deleteAccount(id:)` is the in-app
/// deletion path, shipped in this same change rather than deferred. A person
/// can remove their profile without contacting anyone.
///
/// Discovery gate, per AC#2: only profiles with `openToFriends == true` are
/// returned by `findOpen()`. Turning the flag off removes the person from
/// discovery immediately at this layer; the one-minute SLA is an
/// infrastructure concern (cache TTL or push propagation) outside the scope
/// of this in-process repository.
///
/// The same validation rules and constants exist in the Kotlin lane
/// (ProfileRepository.kt) so that both platforms enforce one shared policy
/// (constitution P9).
public final class ProfileRepository {

    private var profiles: [String: Profile] = [:]

    public init() {}

    /// Persists `profile`, overwriting any existing record with the same id
    /// (update semantics, not duplicate-create).
    ///
    /// Rejects a blank/whitespace-only id. Rejects a blank/whitespace-only
    /// display name, one containing a control character (including a newline),
    /// and one longer than `maxDisplayNameLength` Unicode scalar values after
    /// trimming. The biography is optional (a blank one is allowed) but is
    /// rejected if longer than `maxBiographyLength` after trimming.
    ///
    /// The photo is optional. When a photo is present its format is normalised
    /// (trimmed and lowercased) and rejected unless it names one of
    /// `supportedPhotoFormats`; the photo bytes are rejected if larger than
    /// `maxPhotoSizeBytes`. Both checks throw before anything is stored.
    ///
    /// The interests and activities lists are optional (empty is allowed) but
    /// are rejected if they hold more than `maxInterests` and `maxActivities`
    /// entries respectively; each check throws before anything is stored.
    ///
    /// Throws `ProfileRepositoryError` when any validation rule fails; nothing
    /// is stored when an error is thrown, so a call that returns normally is
    /// the success signal (mirroring the Kotlin `require`-based contract).
    public func save(_ profile: Profile) throws {
        guard !profile.id.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw ProfileRepositoryError.blankId
        }

        let trimmedName = profile.displayName.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedName.isEmpty else {
            throw ProfileRepositoryError.blankDisplayName
        }
        // Control characters (including newlines and carriage returns) are
        // rejected outright. A newline in a name that gets rendered in lists,
        // notifications and logs is a display-spoofing / log-injection surface.
        guard !trimmedName.unicodeScalars.contains(where: {
            CharacterSet.controlCharacters.contains($0)
        }) else {
            throw ProfileRepositoryError.displayNameContainsControlCharacter
        }
        // Length measured in Unicode scalar values (code points), matching the
        // Kotlin lane's codePointCount — an improvement over UTF-16 code units
        // that would double-count emoji. The unit question is still open per
        // docs/product-decisions.md.
        guard trimmedName.unicodeScalars.count <= ProfileRepository.maxDisplayNameLength else {
            throw ProfileRepositoryError.displayNameTooLong
        }

        let trimmedBiography = profile.biography.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmedBiography.count <= ProfileRepository.maxBiographyLength else {
            throw ProfileRepositoryError.biographyTooLong
        }

        // The photo is optional: only validate and normalise a format/size when
        // one is present. An absent photo is stored as nil, leaving the profile
        // incomplete rather than being rejected.
        var normalizedPhoto: ProfilePhoto? = nil
        if let photo = profile.photo {
            let normalizedFormat = photo.format
                .trimmingCharacters(in: .whitespaces)
                .lowercased()
            guard ProfileRepository.supportedPhotoFormats.contains(normalizedFormat) else {
                throw ProfileRepositoryError.unsupportedPhotoFormat
            }
            guard photo.bytes.count <= ProfileRepository.maxPhotoSizeBytes else {
                throw ProfileRepositoryError.photoTooLarge
            }
            normalizedPhoto = ProfilePhoto(bytes: photo.bytes, format: normalizedFormat)
        }

        guard profile.interests.count <= ProfileRepository.maxInterests else {
            throw ProfileRepositoryError.tooManyInterests
        }

        guard profile.activities.count <= ProfileRepository.maxActivities else {
            throw ProfileRepositoryError.tooManyActivities
        }

        // Store what was validated. Storing the original profile unchanged would
        // mean the check and the record disagreed: "  Ada  " would be measured
        // as 3 characters and kept as 7. The same rule applies to the biography
        // and to the photo format, which is kept in its normalised form.
        profiles[profile.id] = Profile(
            id: profile.id,
            displayName: trimmedName,
            photo: normalizedPhoto,
            biography: trimmedBiography,
            interests: profile.interests,
            activities: profile.activities,
            openToFriends: profile.openToFriends
        )
    }

    /// Returns all open profiles as `DiscoveryResult`s, sorted by `MatchScore`
    /// descending, excluding the searcher themselves.
    ///
    /// AC#4: discovery results are ordered by the match score computed from
    /// shared interest tags and overlapping activities. Each result also carries
    /// the shared interests and activities that produced the score, so the
    /// caller can show the person why each result was surfaced.
    ///
    /// The searcher does not need `openToFriends` set: they are browsing,
    /// not being browsed. Only the candidates need the flag.
    ///
    /// Profiles with equal scores preserve stable relative ordering (Swift's
    /// `sorted(by:)` is a stable sort since Swift 5).
    ///
    /// The same algorithm is in
    /// lanes/kotlin-core/src/main/kotlin/ProfileRepository.kt (constitution P9).
    public func discover(searcher: Profile) -> [DiscoveryResult] {
        let myInterests = Set(searcher.interests)
        let myActivities = Set(searcher.activities)
        return profiles.values
            .filter { $0.openToFriends && $0.id != searcher.id }
            .map { candidate -> DiscoveryResult in
                let theirInterests = Set(candidate.interests)
                let theirActivities = Set(candidate.activities)
                let score = MatchScore.score(
                    myInterests: myInterests,
                    theirInterests: theirInterests,
                    myAvailability: myActivities,
                    theirAvailability: theirActivities
                )
                return DiscoveryResult(
                    profile: candidate,
                    score: score,
                    sharedInterests: myInterests.intersection(theirInterests).sorted(),
                    sharedActivities: myActivities.intersection(theirActivities).sorted()
                )
            }
            .sorted { $0.score > $1.score }
    }

    /// Returns the stored `Profile` for `id`, or nil if none exists.
    public func find(id: String) -> Profile? {
        return profiles[id]
    }

    /// Deletes the profile for `id` and returns true if one was removed.
    /// Returns false (rather than throwing) when the id was never stored.
    @discardableResult
    public func deleteAccount(id: String) -> Bool {
        return profiles.removeValue(forKey: id) != nil
    }

    /// Removes the photo from the stored profile for `id` without replacing it,
    /// returning true if a profile was found and updated. The profile is kept;
    /// only its photo is cleared, which leaves the profile incomplete (see
    /// `Profile.isComplete`). Returns false (rather than throwing) when the id
    /// was never stored, mirroring `deleteAccount(id:)`.
    @discardableResult
    public func removePhoto(id: String) -> Bool {
        guard let profile = profiles[id] else { return false }
        profiles[id] = Profile(
            id: profile.id,
            displayName: profile.displayName,
            photo: nil,
            biography: profile.biography,
            interests: profile.interests,
            activities: profile.activities,
            openToFriends: profile.openToFriends
        )
        return true
    }

    /// Sets the `openToFriends` flag for the profile with `id` to `open`.
    /// Returns true if the profile was found and updated; returns false
    /// (rather than throwing) when the id was never stored.
    ///
    /// AC#2: turning the flag off removes the person from every other
    /// person's discovery results immediately at this layer (see
    /// `findOpen()`). The one-minute SLA in AC#2 is an infrastructure
    /// concern outside the scope of this in-process repository.
    @discardableResult
    public func setOpenToFriends(id: String, open: Bool) -> Bool {
        guard profiles[id] != nil else { return false }
        profiles[id]?.openToFriends = open
        return true
    }

    /// Returns all stored profiles whose `openToFriends` flag is true.
    ///
    /// AC#2: discovery surfaces only people who have deliberately turned the
    /// flag on. This is the domain-layer gate; the SLA that the change
    /// propagates within one minute is an infrastructure concern handled
    /// outside this repository.
    public func findOpen() -> [Profile] {
        return profiles.values.filter { $0.openToFriends }
    }

    // MARK: - Constants

    /// Maximum allowed display-name length, measured after trimming, in
    /// Unicode scalar values (code points).
    ///
    /// Placeholder value pending a product decision. The same limit is
    /// declared in the Kotlin lane as `MAX_DISPLAY_NAME_LENGTH`. Keep it as
    /// the single source of truth for this platform so the length rule lives
    /// in exactly one place.
    public static let maxDisplayNameLength: Int = 50

    /// Maximum allowed biography length, measured in extended grapheme
    /// clusters after trimming.
    ///
    /// Placeholder value pending a product decision. The Kotlin equivalent is
    /// `MAX_BIOGRAPHY_LENGTH`, measured in UTF-16 code units — the unit
    /// question is still open per `docs/product-decisions.md`. For ASCII test
    /// inputs both units are identical. Keep this as the single source of
    /// truth for this platform.
    public static let maxBiographyLength: Int = 500

    /// Supported profile photo formats, as normalised (trimmed, lowercased)
    /// format names. Mirrors `SUPPORTED_PHOTO_FORMATS` in the Kotlin lane.
    ///
    /// Placeholder value pending a product decision.
    public static let supportedPhotoFormats: Set<String> = ["jpeg", "png"]

    /// Maximum allowed profile photo size, measured in bytes.
    /// Mirrors `MAX_PHOTO_SIZE_BYTES` in the Kotlin lane.
    ///
    /// Placeholder value pending a product decision.
    public static let maxPhotoSizeBytes: Int = 5 * 1024 * 1024

    /// Maximum allowed number of interests on a profile.
    /// Mirrors `MAX_INTERESTS` in the Kotlin lane.
    ///
    /// Placeholder value pending a product decision.
    public static let maxInterests: Int = 10

    /// Maximum allowed number of activities on a profile.
    /// Mirrors `MAX_ACTIVITIES` in the Kotlin lane.
    ///
    /// Placeholder value pending a product decision.
    public static let maxActivities: Int = 10
}
