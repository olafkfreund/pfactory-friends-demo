/**
 * A user profile. The minimal shape: an identity and a name to show.
 *
 * Other attributes (photo, bio, age, location, interests) are intentionally
 * out of scope here.
 */
data class Profile(
    val id: String,
    val displayName: String,
)
