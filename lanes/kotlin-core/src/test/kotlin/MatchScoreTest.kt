import kotlin.test.Test
import kotlin.test.assertEquals

class MatchScoreTest {
    @Test
    fun `half the interests overlap`() {
        assertEquals(0.5, MatchScore.score(setOf("climbing", "jazz"), setOf("jazz", "chess")))
    }

    @Test
    fun `empty interests score zero rather than crashing`() {
        assertEquals(0.0, MatchScore.score(emptySet(), setOf("jazz")))
    }

    // AC#1: combined score including availability

    @Test
    fun `combined score with no availability falls back to the interest score`() {
        // When the searcher has no stated availability the availability component
        // is absent and the result equals the interest-only score.
        assertEquals(
            0.5,
            MatchScore.score(
                myInterests = setOf("climbing", "jazz"),
                theirInterests = setOf("jazz", "chess"),
                myAvailability = emptySet(),
                theirAvailability = setOf("weekday-evenings"),
            ),
        )
    }

    @Test
    fun `combined score is the mean of interest and availability scores`() {
        // interests: mine={jazz,climbing}, theirs={jazz,chess} => 1/2 = 0.5
        // availability: mine={weekday-evenings}, theirs={weekday-evenings} => 1/1 = 1.0
        // combined = (0.5 + 1.0) / 2 = 0.75
        assertEquals(
            0.75,
            MatchScore.score(
                myInterests = setOf("jazz", "climbing"),
                theirInterests = setOf("jazz", "chess"),
                myAvailability = setOf("weekday-evenings"),
                theirAvailability = setOf("weekday-evenings"),
            ),
        )
    }

    @Test
    fun `combined score with no availability overlap reduces the overall score`() {
        // interests: 1/2 = 0.5, availability: 0/1 = 0.0, combined = 0.25
        assertEquals(
            0.25,
            MatchScore.score(
                myInterests = setOf("jazz", "climbing"),
                theirInterests = setOf("jazz", "chess"),
                myAvailability = setOf("weekday-evenings"),
                theirAvailability = setOf("weekends"),
            ),
        )
    }

    @Test
    fun `combined score with empty interests and availability scores zero`() {
        // Neither side has any signal; nothing to match against.
        assertEquals(
            0.0,
            MatchScore.score(
                myInterests = emptySet(),
                theirInterests = setOf("jazz"),
                myAvailability = emptySet(),
                theirAvailability = setOf("weekends"),
            ),
        )
    }
}
