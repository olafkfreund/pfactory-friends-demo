/**
 * A user profile. The minimal shape: an identity, a name to show, an optional
 * photo, and an optional short biography.
 *
 * [displayName] is a required attribute: a profile cannot be created without
 * it. [photo] is optional: a profile can be created without one, in which case
 * it defaults to `null` and the profile is considered incomplete (see
 * [isComplete]). [biography] is optional: a profile can be created without one,
 * in which case it defaults to the empty string. Other attributes (age,
 * location, interests) are intentionally out of scope here.
 */
data class Profile(
    val id: String,
    val displayName: String,
    val photo: ProfilePhoto? = null,
    val biography: String = "",
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
