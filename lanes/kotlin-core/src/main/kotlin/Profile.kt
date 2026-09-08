/**
 * A user profile. The minimal shape: an identity, a name to show, a required
 * photo, and an optional short biography.
 *
 * [displayName] and [photo] are required attributes: a profile cannot be
 * created without them. [biography] is optional: a profile can be created
 * without one, in which case it defaults to the empty string. Other attributes
 * (age, location, interests) are intentionally out of scope here.
 */
data class Profile(
    val id: String,
    val displayName: String,
    val photo: ProfilePhoto,
    val biography: String = "",
)

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
