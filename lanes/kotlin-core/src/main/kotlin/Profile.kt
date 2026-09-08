/**
 * A user profile. The minimal shape: an identity, a name to show, and an
 * optional short biography.
 *
 * [biography] is optional: a profile can be created without one, in which case
 * it defaults to the empty string. Other attributes (photo, age, location,
 * interests) are intentionally out of scope here.
 */
data class Profile(
    val id: String,
    val displayName: String,
    val biography: String = "",
)
