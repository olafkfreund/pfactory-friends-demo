/**
 * In-process repository for [Report]s.
 *
 * AC#8: a person can report another person or a message, choosing from a
 * fixed list of reasons and optionally adding free text.
 *
 * P5 (constitution, enforceable): every person-to-person surface ships with
 * reporting in the same phase as the feature that creates the data. This
 * repository is the domain-layer record for the trust-and-safety obligation
 * in P5.
 *
 * Persistence is a [MutableList], so this is a single-process, non-durable
 * store; it is enough to prove the report round-trip.
 *
 * The same logic exists verbatim in the Swift lane (ReportRepository.swift)
 * so that both platforms share one set of rules (constitution P9).
 */
class ReportRepository {

    private val reports: MutableList<Report> = mutableListOf()
    private var nextReportId: Int = 0

    /**
     * Submits a report filed by [reporterId] against [targetId], where
     * [targetKind] says whether the target is a user or a message.
     *
     * Returns the persisted [Report] on success. Returns `null` when any of
     * the following are true:
     * - [reporterId] is blank or whitespace-only;
     * - [targetId] is blank or whitespace-only;
     * - [additionalText] (after trimming) exceeds [MAX_FREE_TEXT_LENGTH]
     *   characters.
     *
     * [additionalText] is optional: an empty or blank string is accepted and
     * stored trimmed. Multiple reports with identical field values are
     * permitted; de-duplication is an operational concern for moderation
     * tooling, not a restriction at this layer.
     */
    fun submitReport(
        reporterId: String,
        targetId: String,
        targetKind: ReportTargetKind,
        reason: ReportReason,
        additionalText: String = "",
    ): Report? {
        if (reporterId.isBlank()) return null
        if (targetId.isBlank()) return null
        val trimmedText = additionalText.trim()
        if (trimmedText.length > MAX_FREE_TEXT_LENGTH) return null
        val report = Report(
            id = "report-${nextReportId++}",
            reporterId = reporterId,
            targetId = targetId,
            targetKind = targetKind,
            reason = reason,
            additionalText = trimmedText,
        )
        reports.add(report)
        return report
    }

    /**
     * Returns all reports filed against [targetId] in the order they were
     * submitted (chronological insertion order).
     *
     * Returns an empty list when no reports have been filed against [targetId].
     */
    fun getReportsAgainst(targetId: String): List<Report> =
        reports.filter { it.targetId == targetId }

    /**
     * Returns all reports filed by [reporterId] in the order they were
     * submitted (chronological insertion order).
     *
     * Returns an empty list when [reporterId] has filed no reports.
     */
    fun getReportsByReporter(reporterId: String): List<Report> =
        reports.filter { it.reporterId == reporterId }

    companion object {
        /**
         * Maximum allowed free-text length in a report, measured in
         * characters (UTF-16 code units, i.e. [String.length]), after
         * trimming.
         *
         * Placeholder value pending a product decision: no validated product
         * requirement has fixed this limit yet. Per `docs/product-decisions.md`,
         * code needing a limit should use a single named constant, mark it as a
         * placeholder, and say so in its PR. Keep it as the single source of
         * truth so the length rule lives in exactly one place.
         *
         * The same constant exists in the Swift lane as
         * `ReportRepository.maxFreeTextLength` (constitution P9).
         */
        const val MAX_FREE_TEXT_LENGTH: Int = 1000
    }
}
