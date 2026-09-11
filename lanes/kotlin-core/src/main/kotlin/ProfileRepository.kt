/**
 * Thrown by [ProfileRepository.save] when one or more mandatory profile fields
 * (the display name and/or the photo) are missing or invalid.
 *
 * Where a sequential `require()` chain stops at the first offending field, this
 * reports every affected mandatory field at once (issue #23 / AC-PROF-011-01):
 * [invalidFields] names each one, so a caller can highlight all of them rather
 * than just the first encountered. [message] concatenates the individual
 * per-field reasons and therefore still contains the substrings existing tests
 * assert on (e.g. a supported photo format and [ProfileRepository.MAX_PHOTO_SIZE_BYTES]).
 *
 * Subclasses [IllegalArgumentException] so existing
 * `assertFailsWith<IllegalArgumentException>` call sites keep passing unchanged.
 */
class ProfileValidationException(
    val invalidFields: List<String>,
    message: String,
) : IllegalArgumentException(message) {
    companion object {
        // Field-name tokens for the mandatory fields. No product decision fixes
        // the exact string format (issue #23 does not specify one), so these
        // mirror the corresponding [Profile] property names -- a defensible,
        // stable choice a UI layer can map back to a field without a separate
        // lookup table.

        /** Field-name token for the mandatory display name. */
        const val FIELD_DISPLAY_NAME: String = "displayName"

        /** Field-name token for the mandatory photo. */
        const val FIELD_PHOTO: String = "photo"
    }
}

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
     * The mandatory fields -- the display name and the photo -- are all
     * evaluated before failing, rather than short-circuiting on the first bad
     * one (issue #23 / AC-PROF-011-01). A blank/whitespace-only display name,
     * one containing a control character (including a newline), or one longer
     * than [MAX_DISPLAY_NAME_LENGTH] Unicode code points makes the display name
     * invalid; a photo whose normalized (trimmed, lowercased) format is not one
     * of [SUPPORTED_PHOTO_FORMATS], or whose bytes are larger than
     * [MAX_PHOTO_SIZE_BYTES], makes the photo invalid. If either or both are
     * invalid a single [ProfileValidationException] is thrown, naming every
     * affected field, before anything is stored.
     *
     * The biography is optional (a blank one is allowed) but, when present, is
     * rejected if it is longer than [MAX_BIOGRAPHY_LENGTH], measured after
     * trimming.
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
        // Evaluate every mandatory field (display name, photo) before failing,
        // so a caller can be told about all of them at once instead of one per
        // rejected save (issue #23 / AC-PROF-011-01). Each field contributes at
        // most one entry to invalidFields; the accumulated per-field reasons
        // become the exception message (and still contain the substrings other
        // tests assert on, e.g. a supported format and MAX_PHOTO_SIZE_BYTES).
        val invalidFields = mutableListOf<String>()
        val reasons = mutableListOf<String>()

        val trimmed = profile.displayName.trim()
        // Control characters (including newlines and carriage returns) are
        // rejected outright. docs/product-decisions.md lists "Permitted
        // characters in a display name" as still undecided, but a newline in a
        // name that gets rendered in lists, notifications and logs is a
        // display-spoofing / log-injection surface regardless of where the
        // final character-set policy lands (issue #36, item 2). This is a
        // minimal, defensible floor -- it does not attempt the fuller policy
        // the issue also flags (e.g. bidi override characters), which needs a
        // product decision on the complete permitted-character set.
        val displayNameReason = when {
            trimmed.isEmpty() ->
                "displayName must not be blank"
            trimmed.any { it.isISOControl() } ->
                "displayName must not contain control characters"
            trimmed.codePointCount(0, trimmed.length) > MAX_DISPLAY_NAME_LENGTH ->
                "displayName must be at most $MAX_DISPLAY_NAME_LENGTH characters"
            else -> null
        }
        if (displayNameReason != null) {
            invalidFields += ProfileValidationException.FIELD_DISPLAY_NAME
            reasons += displayNameReason
        }

        val normalizedPhotoFormat = profile.photo.format.trim().lowercase()
        val photoReason = when {
            normalizedPhotoFormat !in SUPPORTED_PHOTO_FORMATS ->
                "photo format must be one of ${SUPPORTED_PHOTO_FORMATS.joinToString(", ")}"
            profile.photo.bytes.size > MAX_PHOTO_SIZE_BYTES ->
                "photo must be at most $MAX_PHOTO_SIZE_BYTES bytes"
            else -> null
        }
        if (photoReason != null) {
            invalidFields += ProfileValidationException.FIELD_PHOTO
            reasons += photoReason
        }

        if (invalidFields.isNotEmpty()) {
            throw ProfileValidationException(
                invalidFields = invalidFields.toList(),
                message = reasons.joinToString("; "),
            )
        }

        // The biography is optional, so it is not a mandatory field for the
        // collect-every-invalid-field rule above; its length check stays a
        // plain require() as before (AC-PROF-003-02).
        val trimmedBiography = profile.biography.trim()
        require(trimmedBiography.length <= MAX_BIOGRAPHY_LENGTH) {
            "biography must be at most $MAX_BIOGRAPHY_LENGTH characters"
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
