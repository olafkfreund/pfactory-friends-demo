/**
 * The shared match score. One definition, per constitution P9.
 *
 * The score is the fraction of the searcher's interests that the candidate
 * also holds. An empty interest set scores 0 rather than dividing by zero.
 */
object MatchScore {
    fun score(mine: Set<String>, theirs: Set<String>): Double {
        if (mine.isEmpty()) return 0.0
        return mine.intersect(theirs).size.toDouble() / mine.size
    }
}
