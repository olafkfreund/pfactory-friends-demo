/// A user profile with an open-to-friends toggle.
///
/// `openToFriends` defaults to false: a person must deliberately turn it on
/// before they surface in anyone else's discovery results (AC#2). Turning it
/// off removes them from discovery immediately at the domain layer; the
/// one-minute SLA stated in AC#2 is an infrastructure concern (cache TTL or
/// push-propagation latency) outside the scope of this model.
public struct Profile {
    public let id: String

    /// Whether this person is currently open to meeting new friends.
    ///
    /// Starts false by default. Must be set to true explicitly before the
    /// profile appears in [ProfileRepository.findOpen] results.
    public var openToFriends: Bool

    public init(id: String, openToFriends: Bool = false) {
        self.id = id
        self.openToFriends = openToFriends
    }
}
