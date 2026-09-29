/**
 * The result of a discovery query for a single candidate profile.
 *
 * Wraps the candidate [Profile] with the pre-computed [score] and the lists of
 * [sharedInterests] and [sharedActivities] that explain why the candidate was
 * surfaced, satisfying AC#4's "the app shows the person why each result was
 * surfaced" requirement.
 *
 * [sharedInterests] is the intersection of the searcher's and candidate's
 * interest tags, sorted for stable, deterministic display.
 * [sharedActivities] is the intersection of the searcher's and candidate's
 * activity tags, sorted for stable, deterministic display.
 *
 * Both can be empty when there is no overlap, which is still a valid result:
 * a profile with a score of 0.0 can appear in results and the empty lists
 * honestly say "nothing matched".
 *
 * The same shape exists verbatim in the Swift lane (DiscoveryResult.swift)
 * so that both platforms share one model of a discovery result
 * (constitution P9).
 */
data class DiscoveryResult(
    val profile: Profile,
    val score: Double,
    val sharedInterests: List<String>,
    val sharedActivities: List<String>,
)
