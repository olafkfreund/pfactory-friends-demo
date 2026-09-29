/**
 * The shared match score. One definition, per constitution P9.
 *
 * The primary score is the fraction of the searcher's interests that the
 * candidate also holds. An empty interest set scores 0 rather than dividing
 * by zero.
 *
 * When the searcher also carries stated availability, the combined score is
 * the mean of the interest score and the availability score (see
 * [score(myInterests, theirInterests, myAvailability, theirAvailability)]).
 * When the searcher has no stated availability, only the interest score is
 * used — the profile is not penalised for an absent signal.
 *
 * The same formula exists verbatim in the Swift lane (MatchScore.swift) so
 * that the same two profiles produce the same score on both platforms (AC#1).
 */
object MatchScore {
    /**
     * Interest-only score: the fraction of [mine] that [theirs] also contains.
     * Returns 0.0 when [mine] is empty rather than dividing by zero.
     */
    fun score(mine: Set<String>, theirs: Set<String>): Double {
        if (mine.isEmpty()) return 0.0
        return mine.intersect(theirs).size.toDouble() / mine.size
    }

    /**
     * Combined score using both interest tags and stated availability.
     *
     * Each component applies the same "fraction of mine that the candidate
     * also holds" rule. When [myAvailability] is empty the availability
     * component is absent and the interest score is returned unchanged, so
     * that callers who have not yet collected availability data are not
     * penalised.
     *
     * When [myAvailability] is non-empty the result is the arithmetic mean
     * of the two component scores:
     *
     *   combinedScore = (interestScore + availabilityScore) / 2
     *
     * The same formula is in lanes/swift-core/Sources/MyFriendsCore/MatchScore.swift.
     */
    fun score(
        myInterests: Set<String>,
        theirInterests: Set<String>,
        myAvailability: Set<String>,
        theirAvailability: Set<String>,
    ): Double {
        val interestScore = score(myInterests, theirInterests)
        if (myAvailability.isEmpty()) return interestScore
        val availabilityScore = score(myAvailability, theirAvailability)
        return (interestScore + availabilityScore) / 2.0
    }
}
