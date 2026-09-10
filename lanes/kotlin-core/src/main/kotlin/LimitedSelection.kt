/**
 * The outcome of attempting to [LimitedSelection.select] an item.
 *
 * A sealed result type rather than a bare boolean, so the caller both learns
 * whether the item was taken and, on rejection, is told the [LimitReached.limit]
 * that was hit — satisfying the acceptance criterion's "the limit is reported"
 * requirement without a second lookup.
 */
sealed interface SelectionOutcome {
    /**
     * The item is now part of the selection: it was newly added while under the
     * limit, or it was already selected (a re-selection is a no-op, not a
     * rejection).
     */
    object Selected : SelectionOutcome

    /**
     * The item was rejected because adding a new one would exceed the cap.
     * [limit] carries the value that was reached, so the caller can report it.
     */
    data class LimitReached(val limit: Int) : SelectionOutcome
}

/**
 * A set of selected strings capped at [limit] items.
 *
 * Enforcement, per AC-PROF-021-01: the maximum lives on the model as the
 * instance property [limit], not as a check duplicated at each call site.
 * [select] is the single place the cap is applied, so every caller enforces the
 * same rule the same way.
 *
 * Independence, per `docs/product-decisions.md` decision #4: Interests and
 * Activities are two separate fields, each with its own limit. [forInterests]
 * and [forActivities] each build a fully independent instance with its own
 * mutable state, so exceeding one field's limit has no effect on the other.
 *
 * State is an in-memory MutableSet; this is a single-process, non-durable model
 * enough to prove the selection-limit behaviour.
 */
class LimitedSelection(val limit: Int) {

    private val selected: MutableSet<String> = mutableSetOf()

    /** The items currently selected, as an unmodifiable snapshot. */
    val items: Set<String>
        get() = selected.toSet()

    /**
     * Attempts to add [item] to the selection.
     *
     * Returns [SelectionOutcome.Selected] when [item] is already selected (a
     * no-op re-selection) or when the selection is still under [limit]. Returns
     * [SelectionOutcome.LimitReached] carrying [limit] when [item] is new and
     * the selection is already at the limit, in which case nothing is added.
     */
    fun select(item: String): SelectionOutcome {
        if (item in selected) {
            return SelectionOutcome.Selected
        }
        if (selected.size >= limit) {
            return SelectionOutcome.LimitReached(limit)
        }
        selected.add(item)
        return SelectionOutcome.Selected
    }

    companion object {
        /**
         * Maximum number of interests a profile may select.
         *
         * Placeholder value pending a product decision: the interest/activity
         * selection limit is still listed as undecided in
         * `docs/product-decisions.md`, which asks that code needing a limit use
         * a single named constant, mark it as a placeholder, and say so in its
         * PR — the same disclosure pattern as
         * [ProfileRepository.MAX_DISPLAY_NAME_LENGTH]. Keep it as the single
         * source of truth so the interests cap lives in exactly one place.
         *
         * Separate from [MAX_ACTIVITIES] on purpose: Interests and Activities
         * are two independent fields (decision #4), so their limits are named
         * and set separately even where the placeholder number matches.
         */
        const val MAX_INTERESTS: Int = 10

        /**
         * Maximum number of activities a profile may select.
         *
         * Placeholder value pending a product decision: the interest/activity
         * selection limit is still listed as undecided in
         * `docs/product-decisions.md`, which asks that code needing a limit use
         * a single named constant, mark it as a placeholder, and say so in its
         * PR — the same disclosure pattern as
         * [ProfileRepository.MAX_DISPLAY_NAME_LENGTH]. Keep it as the single
         * source of truth so the activities cap lives in exactly one place.
         *
         * Separate from [MAX_INTERESTS] on purpose: Interests and Activities
         * are two independent fields (decision #4), so their limits are named
         * and set separately even where the placeholder number matches.
         */
        const val MAX_ACTIVITIES: Int = 10

        /**
         * Builds a fresh [LimitedSelection] capped at [MAX_INTERESTS]. Each call
         * returns an independent instance with its own state.
         */
        fun forInterests(): LimitedSelection = LimitedSelection(MAX_INTERESTS)

        /**
         * Builds a fresh [LimitedSelection] capped at [MAX_ACTIVITIES]. Each
         * call returns an independent instance with its own state.
         */
        fun forActivities(): LimitedSelection = LimitedSelection(MAX_ACTIVITIES)
    }
}
