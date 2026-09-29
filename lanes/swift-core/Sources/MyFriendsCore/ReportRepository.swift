import Foundation

/// In-process repository for `Report`s.
///
/// AC#8: a person can report another person or a message, choosing from a
/// fixed list of reasons and optionally adding free text.
///
/// P5 (constitution, enforceable): every person-to-person surface ships with
/// reporting in the same phase as the feature that creates the data. This
/// repository is the domain-layer record for the trust-and-safety obligation
/// in P5.
///
/// Persistence is an array, so this is a single-process, non-durable store;
/// it is enough to prove the report round-trip.
///
/// The same logic exists verbatim in the Kotlin lane (ReportRepository.kt)
/// so that both platforms share one set of rules (constitution P9).
public final class ReportRepository {

    private var reports: [Report] = []
    private var nextReportId: Int = 0

    public init() {}

    /// Submits a report filed by `reporterId` against `targetId`, where
    /// `targetKind` says whether the target is a user or a message.
    ///
    /// Returns the persisted `Report` on success. Returns `nil` when any of
    /// the following are true:
    /// - `reporterId` is blank or whitespace-only;
    /// - `targetId` is blank or whitespace-only;
    /// - `additionalText` (after trimming) exceeds `maxFreeTextLength`
    ///   characters.
    ///
    /// `additionalText` is optional: an empty or blank string is accepted and
    /// stored trimmed. Multiple reports with identical field values are
    /// permitted; de-duplication is an operational concern for moderation
    /// tooling, not a restriction at this layer.
    @discardableResult
    public func submitReport(
        reporterId: String,
        targetId: String,
        targetKind: ReportTargetKind,
        reason: ReportReason,
        additionalText: String = ""
    ) -> Report? {
        guard !reporterId.trimmingCharacters(in: .whitespaces).isEmpty else { return nil }
        guard !targetId.trimmingCharacters(in: .whitespaces).isEmpty else { return nil }
        let trimmedText = additionalText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmedText.count <= ReportRepository.maxFreeTextLength else { return nil }
        let reportId = "report-\(nextReportId)"
        nextReportId += 1
        let report = Report(
            id: reportId,
            reporterId: reporterId,
            targetId: targetId,
            targetKind: targetKind,
            reason: reason,
            additionalText: trimmedText
        )
        reports.append(report)
        return report
    }

    /// Returns all reports filed against `targetId` in the order they were
    /// submitted (chronological insertion order).
    ///
    /// Returns an empty array when no reports have been filed against `targetId`.
    public func getReportsAgainst(targetId: String) -> [Report] {
        return reports.filter { $0.targetId == targetId }
    }

    /// Returns all reports filed by `reporterId` in the order they were
    /// submitted (chronological insertion order).
    ///
    /// Returns an empty array when `reporterId` has filed no reports.
    public func getReportsByReporter(reporterId: String) -> [Report] {
        return reports.filter { $0.reporterId == reporterId }
    }

    // MARK: - Constants

    /// Maximum allowed free-text length in a report, measured in extended
    /// grapheme clusters (Swift's `String.count`), after trimming.
    ///
    /// Placeholder value pending a product decision. Mirrors
    /// `ReportRepository.MAX_FREE_TEXT_LENGTH` in the Kotlin lane. Keep it as
    /// the single source of truth for this platform so the length rule lives
    /// in exactly one place.
    public static let maxFreeTextLength: Int = 1000
}
