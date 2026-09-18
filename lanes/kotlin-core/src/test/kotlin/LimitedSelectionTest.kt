import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

class LimitedSelectionTest {
    /**
     * Fills [selection] with [count] distinct items, asserting each one is
     * accepted. Keeps the limit-boundary tests focused on the item that hits the
     * cap rather than repeating the same fill loop in every case.
     */
    private fun fillUpTo(selection: LimitedSelection, count: Int) {
        repeat(count) { index ->
            assertIs<SelectionOutcome.Selected>(selection.select("item-$index"))
        }
    }

    @Test
    fun `selecting items up to the limit is allowed`() {
        val selection = LimitedSelection(limit = 3)

        fillUpTo(selection, 3)

        assertEquals(setOf("item-0", "item-1", "item-2"), selection.items)
    }

    @Test
    fun `selecting one past the limit is rejected and reports the limit`() {
        val selection = LimitedSelection(limit = 3)
        fillUpTo(selection, 3)

        val outcome = selection.select("item-3")

        val rejection = assertIs<SelectionOutcome.LimitReached>(outcome)
        assertEquals(3, rejection.limit)
        // The rejected item was not stored: the selection stayed at the limit.
        assertEquals(setOf("item-0", "item-1", "item-2"), selection.items)
    }

    @Test
    fun `re-selecting an already-selected item at the limit is a no-op not a rejection`() {
        val selection = LimitedSelection(limit = 3)
        fillUpTo(selection, 3)

        assertIs<SelectionOutcome.Selected>(selection.select("item-0"))
        assertEquals(setOf("item-0", "item-1", "item-2"), selection.items)
    }

    @Test
    fun `interests can be filled to their own limit without affecting activities`() {
        // AC-PROF-021-01 independence: exhausting the interests selection leaves
        // a freshly built activities selection completely unaffected.
        val interests = LimitedSelection.forInterests()
        val activities = LimitedSelection.forActivities()

        fillUpTo(interests, LimitedSelection.MAX_INTERESTS)

        val overInterests = interests.select("one-too-many")
        assertIs<SelectionOutcome.LimitReached>(overInterests)

        // Activities is untouched: it still accepts a selection.
        assertIs<SelectionOutcome.Selected>(activities.select("hiking"))
        assertEquals(setOf("hiking"), activities.items)
    }

    @Test
    fun `activities being exhausted has no effect on interests`() {
        val interests = LimitedSelection.forInterests()
        val activities = LimitedSelection.forActivities()

        fillUpTo(activities, LimitedSelection.MAX_ACTIVITIES)
        assertIs<SelectionOutcome.LimitReached>(activities.select("one-too-many"))

        assertIs<SelectionOutcome.Selected>(interests.select("astronomy"))
        assertEquals(setOf("astronomy"), interests.items)
    }

    @Test
    fun `each factory call produces an independent instance that never shares state`() {
        val first = LimitedSelection.forInterests()
        val second = LimitedSelection.forInterests()

        assertIs<SelectionOutcome.Selected>(first.select("astronomy"))

        assertTrue(second.items.isEmpty())
    }

    @Test
    fun `the interests limit is reported against its own placeholder constant`() {
        val interests = LimitedSelection.forInterests()
        fillUpTo(interests, LimitedSelection.MAX_INTERESTS)

        val rejection = assertIs<SelectionOutcome.LimitReached>(interests.select("overflow"))
        assertEquals(LimitedSelection.MAX_INTERESTS, rejection.limit)
    }
}
