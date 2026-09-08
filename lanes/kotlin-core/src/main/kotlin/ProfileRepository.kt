/**
 * In-process storage for [Profile] records.
 *
 * Data ownership, per constitution P1: the only personal data kept here is the
 * display name and the optional biography. Both are kept for as long as the
 * account exists and are deleted the moment the person calls [deleteAccount] —
 * the biography is part of the same [Profile] record, so it needs no separate
 * cleanup. There is no other copy and no background retention.
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
        // Store what was validated. Storing `profile` unchanged here meant the
        // check and the record disagreed: "  Ada  " was measured as 3
        // characters and kept as 7, and a name padded to the limit persisted
        // over it. The same rule applies to the biography.
        profiles[profile.id] = profile.copy(
            displayName = trimmed,
            biography = trimmedBiography,
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
    }
}
