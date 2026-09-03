/// The shared match score. One definition, per constitution P9.
///
/// The score is the fraction of the searcher's interests that the candidate
/// also holds. An empty interest set scores 0 rather than dividing by zero.
public enum MatchScore {
    public static func score(mine: Set<String>, theirs: Set<String>) -> Double {
        guard !mine.isEmpty else { return 0 }
        return Double(mine.intersection(theirs).count) / Double(mine.count)
    }
}
