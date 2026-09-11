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
     * Rejects a blank/whitespace-only id (see [save]'s implementation comment
     * for why -- this is a floor, not the full id-format decision).
     *
     * Rejects a blank/whitespace-only display name, one containing a control
     * character (including a newline), and one longer than
     * [MAX_DISPLAY_NAME_LENGTH] Unicode code points, throwing before anything
     * is stored.
     *
     * The biography is optional (a blank one is allowed) but, when present, is
     * rejected if it is longer than [MAX_BIOGRAPHY_LENGTH], measured after
     * trimming.
     *
     * The photo is optional. When present, its format is normalized (trimmed
     * and lowercased) and rejected unless it names one of
     * [SUPPORTED_PHOTO_FORMATS], and its bytes are rejected if larger than
     * [MAX_PHOTO_SIZE_BYTES]; both checks throw before anything is stored. When
     * absent (null), the photo is stored as null and the profile is simply not
     * yet complete (see [Profile.isComplete]).
     */
    fun save(profile: Profile) {
        // The id is not covered by any product decision (issue #36, item 1):
        // nothing in the plan or in docs/product-decisions.md says whether the
        // domain layer validates it or trusts it as an already-authenticated
        // value from the auth layer. Rejecting a blank/whitespace-only id is a
        // minimal, uncontroversial floor either way -- it prevents every
        // profile from silently colliding on the same "" or "   " map key --
        // and does not attempt to decide id *format* (opaque token vs UUID vs
        // something else), which is the actual open question and still needs a
        // product/eng answer.
        require(profile.id.isNotBlank()) {
            "id must not be blank"
        }
        val trimmed = profile.displayName.trim()
        require(trimmed.isNotEmpty()) {
            "displayName must not be blank"
        }
        // Control characters (including newlines and carriage returns) are
        // rejected outright. docs/product-decisions.md lists "Permitted
        // characters in a display name" as still undecided, but a newline in a
        // name that gets rendered in lists, notifications and logs is a
        // display-spoofing / log-injection surface regardless of where the
        // final character-set policy lands (issue #36, item 2). This is a
        // minimal, defensible floor -- it does not attempt the fuller policy
        // the issue also flags (e.g. bidi override characters), which needs a
        // product decision on the complete permitted-character set.
        require(trimmed.none { it.isISOControl() }) {
            "displayName must not contain control characters"
        }
        require(trimmed.codePointCount(0, trimmed.length) <= MAX_DISPLAY_NAME_LENGTH) {
            "displayName must be at most $MAX_DISPLAY_NAME_LENGTH characters"
        }
        val trimmedBiography = profile.biography.trim()
        require(trimmedBiography.length <= MAX_BIOGRAPHY_LENGTH) {
            "biography must be at most $MAX_BIOGRAPHY_LENGTH characters"
        }
        // The photo is optional: a profile with no photo is stored as-is (its
        // photo left null) and is simply not yet complete (see [Profile.isComplete]).
        // A person can reach this state either by saving a profile without a
        // photo or by calling [removePhoto]. The format/size validation only
        // makes sense for an actual photo, so it is guarded behind a null check
        // rather than dereferencing a possibly-null photo.
        val validatedPhoto = profile.photo?.let { photo ->
            val normalizedPhotoFormat = photo.format.trim().lowercase()
            require(normalizedPhotoFormat in SUPPORTED_PHOTO_FORMATS) {
                "photo format must be one of ${SUPPORTED_PHOTO_FORMATS.joinToString(", ")}"
            }
            require(photo.bytes.size <= MAX_PHOTO_SIZE_BYTES) {
                "photo must be at most $MAX_PHOTO_SIZE_BYTES bytes"
            }
            photo.copy(format = normalizedPhotoFormat)
        }
        // Store what was validated. Storing `profile` unchanged here meant the
        // check and the record disagreed: "  Ada  " was measured as 3
        // characters and kept as 7, and a name padded to the limit persisted
        // over it. The same rule applies to the biography and to the photo
        // format, which is kept in its normalized form (or left null when there
        // is no photo).
        profiles[profile.id] = profile.copy(
            displayName = trimmed,
            biography = trimmedBiography,
            photo = validatedPhoto,
        )
    }

    /** Returns the stored [Profile] for [id], or null if none exists. */
    fun find(id: String): Profile? = profiles[id]

    /**
     * Deletes the profile for [id] and returns true if one was removed.
     * Returns false (rather than throwing) when the id was never stored.
     */
    fun deleteAccount(id: String): Boolean = profiles.remove(id) != null

    /**
     * Clears the photo on the profile for [id], leaving the rest of the record
     * intact, and returns true if a profile existed to update. Returns false
     * (rather than throwing) when the id was never stored — mirroring
     * [deleteAccount]'s "false only for an unknown id" semantics.
     *
     * This is the data-layer half of AC-PROF-019-02 ("remove an existing photo
     * without uploading a replacement"). Per docs/product-decisions.md a photo
     * is mandatory for a profile to be *complete*, not to *exist*, so clearing
     * it flips [Profile.isComplete] from true to false rather than being
     * rejected. The AC's "shows a default placeholder" is a presentation concern
     * with no UI layer in this codebase yet: storing null and letting a future
     * UI render the placeholder is the defensible split, flagged here rather
     * than silently assumed.
     *
     * Removing a photo on a profile that already has none is a valid no-op: the
     * id exists, so it returns true, and the record is written back unchanged.
     *
     * Retention/handling of the cleared photo bytes is out of scope (still an
     * open item in docs/product-decisions.md). Like the biography, the photo is
     * part of the same [Profile] record, so overwriting it with null is the only
     * cleanup needed here — there is no separate copy and no background
     * retention (same reasoning as [deleteAccount]).
     */
    fun removePhoto(id: String): Boolean {
        val profile = profiles[id] ?: return false
        profiles[id] = profile.copy(photo = null)
        return true
    }

    companion object {
        /**
         * Maximum allowed display-name length, measured after trimming, in
         * Unicode code points (see below).
         *
         * Placeholder value pending a product decision: no validated product
         * requirement has fixed this limit yet, and it is still listed under
         * "Still undecided" in docs/product-decisions.md. Keep it as the single
         * source of truth so the length rule lives in exactly one place.
         *
         * NEEDS PRODUCT CONFIRMATION -- unit choice (issue #36, item 3): this
         * was measured with `String.length` (UTF-16 code units), which rejected
         * a name of 50 simple emoji as 100 "characters" and cut CJK names
         * shorter, in user-perceived characters, than Latin ones. It is now
         * measured with `codePointCount`, counting Unicode code points instead:
         * an improvement (most emoji and all CJK characters are one code point
         * each, so a straightforward Latin/CJK/simple-emoji name of 50
         * characters is now accepted), chosen over grapheme clusters because
         * the JVM standard library has no built-in grapheme-cluster counter
         * (one exists via `java.text.BreakIterator`, but pulling that in is
         * itself a choice that should be made deliberately, not as a side
         * effect of a bug fix). The trade-off: a composed emoji built from
         * several code points joined by ZWJ (e.g. a family or flag emoji) still
         * counts as multiple units under this scheme, same as before. Code
         * points is a defensible middle ground, not the final answer -- the
         * product owner still needs to pick code points vs. grapheme clusters
         * explicitly, per docs/product-decisions.md.
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
    }
}
