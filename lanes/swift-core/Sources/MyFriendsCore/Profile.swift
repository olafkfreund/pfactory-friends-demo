/// A profile photo: the raw image `bytes` and the image `format` (e.g. "jpeg",
/// "png").
///
/// Two `ProfilePhoto` values are equal when their `bytes` contents and `format`
/// are equal, matching the Kotlin `ProfilePhoto.equals` behaviour which overrides
/// the default reference-based `ByteArray` equality.
public struct ProfilePhoto: Equatable {
    public let bytes: [UInt8]
    public let format: String

    public init(bytes: [UInt8], format: String) {
        self.bytes = bytes
        self.format = format
    }
}

/// A user profile. The minimal shape: an identity, a name to show, an optional
/// photo, and an optional short biography.
///
/// `displayName` is a required attribute: a profile cannot be created without
/// it. `photo` is optional: a profile can be created without one, in which case
/// it defaults to `nil` and the profile is considered incomplete (see
/// `isComplete`). `biography` is optional: a profile can be created without one,
/// in which case it defaults to the empty string. `interests` and `activities`
/// are optional lists that default to empty.
///
/// `openToFriends` defaults to false: a person must deliberately turn it on
/// before they surface in anyone else's discovery results (AC#2). Turning it
/// off removes them from discovery immediately at the domain layer; the
/// one-minute SLA stated in AC#2 is an infrastructure concern (cache TTL or
/// push-propagation latency) outside the scope of this model.
///
/// `age` is the person's self-reported age in whole years (AC#1). It is stored
/// as entered; the domain layer enforces the minimum-age floor at save time
/// (see `ProfileRepository.minAge`). `age` defaults to 18 (the primary
/// audience per the product brief) so that callers that do not yet pass an
/// explicit age still produce a valid profile; production callers must always
/// supply a real age collected from the person.
///
/// The same shape exists verbatim in the Kotlin lane (Profile.kt) so that both
/// platforms share one model of a profile (constitution P9).
public struct Profile {
    public let id: String
    public let displayName: String
    public let photo: ProfilePhoto?
    public let biography: String
    public let interests: [String]
    public let activities: [String]
    /// Whether this person is currently open to meeting new friends.
    ///
    /// Starts false by default. Must be set to true explicitly before the
    /// profile appears in `ProfileRepository.findOpen()` results.
    public var openToFriends: Bool

    /// The profile's physical location for proximity-based discovery (AC#3).
    ///
    /// Stored at the precision needed for 1–25 km radius filtering. This value
    /// is used only internally and is never shown to other users — only a
    /// town/city label is exposed, per `docs/product-decisions.md` decision 3.
    /// It is read only while the person is actively using the app (AC#12 /
    /// constitution P4, enforceable). Kept for as long as the account exists
    /// and deleted together with the profile on account deletion (constitution
    /// P1, enforceable).
    ///
    /// `nil` means location access has not been granted or the location is not
    /// yet known; profiles without a location are excluded from radius-filtered
    /// discovery results.
    public let location: GeoLocation?

    /// The person's self-reported age in whole years (AC#1).
    ///
    /// Must be at least `ProfileRepository.minAge` (16). The minimum covers
    /// the "Older teenagers aged 16 and 17" segment stated in the product
    /// brief and the age-assurance requirement in constitution P3 (enforceable).
    ///
    /// Age data is personal data, kept for as long as the account exists and
    /// deleted together with the profile on account deletion (constitution P1).
    public let age: Int

    /// Whether the profile is complete. A profile is complete only when it has
    /// a `photo`.
    public var isComplete: Bool {
        return photo != nil
    }

    public init(
        id: String,
        displayName: String,
        photo: ProfilePhoto? = nil,
        biography: String = "",
        interests: [String] = [],
        activities: [String] = [],
        openToFriends: Bool = false,
        location: GeoLocation? = nil,
        age: Int = 18
    ) {
        self.id = id
        self.displayName = displayName
        self.photo = photo
        self.biography = biography
        self.interests = interests
        self.activities = activities
        self.openToFriends = openToFriends
        self.location = location
        self.age = age
    }
}
