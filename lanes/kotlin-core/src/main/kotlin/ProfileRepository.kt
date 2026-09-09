/**
 * In-process storage for [Profile] records.
 *
 * Data ownership, per constitution P1: the only personal data kept here is the
 * display name, the required photo, the required age and the optional
 * biography. All of them are kept for as long as the account exists and are
 * deleted the moment the person calls [deleteAccount] — the age, like the photo
 * and the biography, is part of the same [Profile] record, so it needs no
 * separate cleanup. There is no other copy and no background retention: age is
 * retained exactly like the display name, biography and photo, with no separate
 * or background store of its own.
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
     * The age is rejected if below [MIN_AGE] (the confirmed 16+ product
     * decision) or above [MAX_AGE] (a placeholder plausibility bound), each
     * check throwing before anything is stored. Because [Profile.age] is a
     * Kotlin `Int`, non-numeric input cannot reach this method at all — that
     * constraint is enforced at compile time, so the only age validation left
     * to do here is the numeric range.
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
        require(profile.age >= MIN_AGE) {
            "age must be at least $MIN_AGE"
        }
        require(profile.age <= MAX_AGE) {
            "age must be at most $MAX_AGE"
        }
        // Store what was validated. Storing `profile` unchanged here meant the
        // check and the record disagreed: "  Ada  " was measured as 3
        // characters and kept as 7, and a name padded to the limit persisted
        // over it. The same rule applies to the biography and to the photo
        // format, which is kept in its normalized form. The age is already a
        // validated `Int`, so it is copied through as-is.
        profiles[profile.id] = profile.copy(
            displayName = trimmed,
            biography = trimmedBiography,
            photo = profile.photo.copy(format = normalizedPhotoFormat),
            age = profile.age,
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
         * Minimum age, in whole years, required to create a profile.
         *
         * CONFIRMED product decision — unlike the placeholder constants above
         * ([MAX_DISPLAY_NAME_LENGTH], [MAX_BIOGRAPHY_LENGTH],
         * [SUPPORTED_PHOTO_FORMATS], [MAX_PHOTO_SIZE_BYTES]), whose numbers are
         * still open, this value is fixed. `docs/product-decisions.md` (decided
         * 2026-09-08, item 1 of the five blocking questions) records the answer
         * as: "Minimum age to create a profile: 16+". The 16+ boundary is
         * inclusive, matching the "16+" wording, so exactly 16 is accepted.
         *
         * Note the deliberate, accepted gap recorded in the same document:
         * 16- and 17-year-olds are children in law and the ICO Age Appropriate
         * Design Code would apply, but the child-specific defaults (geolocation
         * and profiling off by default, explicit opt-in) are explicitly out of
         * scope here and are not implemented in this change.
         */
        const val MIN_AGE: Int = 16

        /**
         * Maximum age, in whole years, accepted as a plausibility upper bound.
         *
         * Placeholder value pending a product decision: the "Maximum age /
         * plausibility upper bound" item is still listed under "Still undecided"
         * in `docs/product-decisions.md`, which asks that code needing a limit
         * use a single named constant, mark it as a placeholder, and say so in
         * its PR. Keep it as the single source of truth so the upper-bound rule
         * lives in exactly one place.
         *
         * It exists so an implausibly large numeric age is rejected rather than
         * stored; the exact number is not a validated product requirement and
         * should be settled together with the "Maximum age" decision.
         */
        const val MAX_AGE: Int = 120
    }
}
