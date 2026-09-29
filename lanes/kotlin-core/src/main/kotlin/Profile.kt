/**
 * A user profile. The minimal shape: an identity, a name to show, an optional
 * photo, and an optional short biography.
 *
 * [displayName] is a required attribute: a profile cannot be created without
 * it. [photo] is optional: a profile can be created without one, in which case
 * it defaults to `null` and the profile is considered incomplete (see
 * [isComplete]). [biography] is optional: a profile can be created without one,
 * in which case it defaults to the empty string. [interests] and [activities]
 * are optional lists that default to empty.
 *
 * [age] is the person's self-reported age in whole years (AC#1). It is stored
 * as entered; the domain layer enforces the minimum-age floor at save time
 * (see [ProfileRepository.MIN_AGE]). [age] defaults to 18 (the primary
 * audience per the product brief) so that callers that do not yet pass an
 * explicit age still produce a valid profile; production callers must always
 * supply a real age collected from the person.
 *
 * Age data is personal data. It is kept for as long as the account exists and
 * deleted together with the profile on [ProfileRepository.deleteAccount]
 * (constitution P1, enforceable).
 */
data class Profile(
    val id: String,
    val displayName: String,
    val photo: ProfilePhoto? = null,
    val biography: String = "",
    val interests: List<String> = emptyList(),
    val activities: List<String> = emptyList(),
    /**
     * The person's self-reported age in whole years (AC#1).
     *
     * Must be at least [ProfileRepository.MIN_AGE] (16). The minimum covers
     * the "Older teenagers aged 16 and 17" segment stated in the product
     * brief and the age-assurance requirement in constitution P3 (enforceable).
     *
     * Collecting a birth date is not an age-assurance mechanism (P3). The
     * age stored here is the self-reported value the domain layer can
     * validate; a full assurance flow is a separate UI-layer concern.
     */
    val age: Int = 18,
    /**
     * Whether this person is currently open to meeting new friends.
     *
     * Defaults to false: a person must deliberately turn the toggle on before
     * they surface in anyone else's discovery results (AC#2). Turning it off
     * removes them from discovery immediately at the domain layer; the
     * one-minute SLA stated in AC#2 is an infrastructure concern (cache TTL
     * or push-propagation latency) outside the scope of this model.
     */
    val openToFriends: Boolean = false,
    /**
     * The profile's physical location for proximity-based discovery (AC#3).
     *
     * Stored at the precision needed for 1–25 km radius filtering. This value
     * is used only internally and is never shown to other users — only a
     * town/city label is exposed, per docs/product-decisions.md decision 3.
     * It is read only while the person is actively using the app (AC#12 /
     * constitution P4, enforceable). Kept for as long as the account exists
     * and deleted together with the profile on account deletion (constitution
     * P1, enforceable).
     *
     * Null means location access has not been granted or the location is not
     * yet known; profiles without a location are excluded from radius-filtered
     * discovery results.
     */
    val location: GeoLocation? = null,
) {
    /**
     * Whether the profile is complete. A profile is complete only when it has
     * a [photo].
     */
    val isComplete: Boolean
        get() = photo != null
}

/**
 * A profile photo: the raw image [bytes] and the image [format] (e.g. "jpeg",
 * "png").
 *
 * Note: [equals]/[hashCode] are overridden to compare [bytes] by content. A
 * Kotlin data class would otherwise give a [ByteArray] property reference
 * equality, so two photos built from equal-content-but-distinct arrays would
 * not be considered equal.
 */
data class ProfilePhoto(val bytes: ByteArray, val format: String) {
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is ProfilePhoto) return false
        return bytes.contentEquals(other.bytes) && format == other.format
    }

    override fun hashCode(): Int {
        var result = bytes.contentHashCode()
        result = 31 * result + format.hashCode()
        return result
    }
}
