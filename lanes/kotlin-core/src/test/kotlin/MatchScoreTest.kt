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
}
