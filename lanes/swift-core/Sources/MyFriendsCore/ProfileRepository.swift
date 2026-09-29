/// In-process storage for `Profile` records.
///
/// Discovery gate, per AC#2: only profiles with `openToFriends == true` are
/// returned by `findOpen()`. Turning the flag off removes the person from
/// discovery immediately at this layer; the one-minute SLA is an
/// infrastructure concern (cache TTL or push propagation) outside the scope
/// of this in-process repository.
public final class ProfileRepository {

    private var profiles: [String: Profile] = [:]

    public init() {}

    /// Persists `profile`, overwriting any existing record with the same id
    /// (update semantics, not duplicate-create).
    public func save(_ profile: Profile) {
        profiles[profile.id] = profile
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
}
