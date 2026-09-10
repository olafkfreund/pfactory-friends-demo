/**
 * In-process storage for [Profile] records.
 *
 * Data ownership, per constitution P1: the only personal data kept here is the
 * display name, the required photo and the optional biography. All three are
 * kept for as long as the account exists and are deleted the moment the person
 * calls [deleteAccount] — the photo, like the biography, is part of the same
 * [Profile] record, so it needs no separate cleanup. There is no other copy and
 * no background retention.
 *
 * Deletion path, per constitution P2: [deleteAccount] is the in-app deletion
 * path, shipped in this same change rather than deferred. A person can remove
 * their profile without contacting anyone.
 *
 * Persistence is a MutableMap keyed by id, so this is a single-process,
 * non-durable store; it is enough to prove the save/find/delete round-trip.
 */
class ProfileRepository {

    private val profiles: MutableMap<String, Profile> = mutableMapOf()

    /**
     * Persists [profile], overwriting any existing record with the same id
     * (update semantics, not duplicate-create).
     *
     * Rejects a blank/whitespace-only display name and one longer than
     * [MAX_DISPLAY_NAME_LENGTH], throwing before anything is stored.
     *
     * The biography is optional (a blank one is allowed) but, when present, is
     * rejected if it is longer than [MAX_BIOGRAPHY_LENGTH], measured after
     * trimming.
     *
     * The photo format is normalized (trimmed and lowercased) and rejected
     * unless it names one of [SUPPORTED_PHOTO_FORMATS]; the photo bytes are
     * rejected if larger than [MAX_PHOTO_SIZE_BYTES]. Both checks throw before
     * anything is stored.
     *
     * The interests and activities lists are optional (empty is allowed) but
     * are rejected if they hold more than [MAX_INTERESTS] and [MAX_ACTIVITIES]
     * entries respectively; each check throws before anything is stored.
     */
    fun save(profile: Profile) {
        val trimmed = profile.displayName.trim()
        require(trimmed.isNotEmpty()) {
            "displayName must not be blank"
        }
        require(trimmed.length <= MAX_DISPLAY_NAME_LENGTH) {
            "displayName must be at most $MAX_DISPLAY_NAME_LENGTH characters"
        }
        val trimmedBiography = profile.biography.trim()
        require(trimmedBiography.length <= MAX_BIOGRAPHY_LENGTH) {
            "biography must be at most $MAX_BIOGRAPHY_LENGTH characters"
        }
        val normalizedPhotoFormat = profile.photo.format.trim().lowercase()
        require(normalizedPhotoFormat in SUPPORTED_PHOTO_FORMATS) {
            "photo format must be one of ${SUPPORTED_PHOTO_FORMATS.joinToString(", ")}"
        }
        require(profile.photo.bytes.size <= MAX_PHOTO_SIZE_BYTES) {
            "photo must be at most $MAX_PHOTO_SIZE_BYTES bytes"
        }
        require(profile.interests.size <= MAX_INTERESTS) {
            "interests must be at most $MAX_INTERESTS entries"
        }
        require(profile.activities.size <= MAX_ACTIVITIES) {
            "activities must be at most $MAX_ACTIVITIES entries"
        }
        // Store what was validated. Storing `profile` unchanged here meant the
        // check and the record disagreed: "  Ada  " was measured as 3
        // characters and kept as 7, and a name padded to the limit persisted
        // over it. The same rule applies to the biography and to the photo
        // format, which is kept in its normalized form.
        profiles[profile.id] = profile.copy(
            displayName = trimmed,
            biography = trimmedBiography,
            photo = profile.photo.copy(format = normalizedPhotoFormat),
        )
    }

    /** Returns the stored [Profile] for [id], or null if none exists. */
    fun find(id: String): Profile? = profiles[id]

    /**
     * Deletes the profile for [id] and returns true if one was removed.
     * Returns false (rather than throwing) when the id was never stored.
     */
    fun deleteAccount(id: String): Boolean = profiles.remove(id) != null

    companion object {
        /**
         * Maximum allowed display-name length, measured after trimming.
         *
         * Placeholder value pending a product decision: no validated product
         * requirement has fixed this limit yet. Keep it as the single source of
         * truth so the length rule lives in exactly one place.
         *
         * The unit is Kotlin's `String.length` — UTF-16 code units, not
         * user-perceived characters. A name of 50 emoji is 100 units and is
         * rejected, as is a shorter CJK name than a Latin one. Whether the
         * product limit means code units, code points or grapheme clusters is
         * part of the same open decision and should be settled with the number.
         */
        const val MAX_DISPLAY_NAME_LENGTH: Int = 50

        /**
         * Maximum allowed biography length, measured after trimming.
         *
         * Placeholder value pending a product decision: the "Maximum About Me
         * biography length" item is still listed under "Still undecided" in
         * `docs/product-decisions.md`, which asks that code needing a limit use
         * a single named constant, mark it as a placeholder, and say so in its
         * PR. Keep it as the single source of truth so the length rule lives in
         * exactly one place.
         *
         * The unit is Kotlin's `String.length` — UTF-16 code units, not
         * user-perceived characters — with the same open code-unit / code-point
         * / grapheme-cluster question as [MAX_DISPLAY_NAME_LENGTH], to be
         * settled together with the number.
         */
        const val MAX_BIOGRAPHY_LENGTH: Int = 500

        /**
         * Supported profile photo formats, as normalized (trimmed, lowercase)
         * format names.
         *
         * Placeholder value pending a product decision: the "Supported profile
         * photo formats and maximum file size" item is still listed under
         * "Still undecided" in `docs/product-decisions.md`, which asks that code
         * needing a limit use a single named constant, mark it as a placeholder,
         * and say so in its PR. Keep it as the single source of truth so the
         * accepted-format rule lives in exactly one place.
         *
         * Membership is tested against the incoming format after the same
         * normalization (trim + lowercase), so "JPEG" and " png " are accepted
         * and stored in their normalized form.
         */
        val SUPPORTED_PHOTO_FORMATS: Set<String> = setOf("jpeg", "png")

        /**
         * Maximum allowed profile photo size, measured in bytes.
         *
         * Placeholder value pending a product decision: the "Supported profile
         * photo formats and maximum file size" item is still listed under
         * "Still undecided" in `docs/product-decisions.md`, which asks that code
         * needing a limit use a single named constant, mark it as a placeholder,
         * and say so in its PR. Keep it as the single source of truth so the
         * size rule lives in exactly one place.
         *
         * The unit is raw bytes of the image payload — not kilobytes and not a
         * decoded-pixel budget. The exact number is part of the same open
         * decision and should be settled together with the accepted formats.
         */
        const val MAX_PHOTO_SIZE_BYTES: Int = 5 * 1024 * 1024

        /**
         * Maximum allowed number of interests on a profile.
         *
         * Placeholder value pending a product decision: no validated product
         * requirement has fixed this limit yet. Per `docs/product-decisions.md`,
         * code needing a limit should use a single named constant, mark it as a
         * placeholder, and say so in its PR. Keep it as the single source of
         * truth so the count rule lives in exactly one place.
         *
         * The unit is entry count — the number of items in the list, with no
         * per-entry length or content rule implied here.
         */
        const val MAX_INTERESTS: Int = 10

        /**
         * Maximum allowed number of activities on a profile.
         *
         * Placeholder value pending a product decision: no validated product
         * requirement has fixed this limit yet. Per `docs/product-decisions.md`,
         * code needing a limit should use a single named constant, mark it as a
         * placeholder, and say so in its PR. Keep it as the single source of
         * truth so the count rule lives in exactly one place.
         *
         * The unit is entry count — the number of items in the list, with no
         * per-entry length or content rule implied here.
         */
        const val MAX_ACTIVITIES: Int = 10
    }
}
