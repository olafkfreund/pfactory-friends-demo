/// The fixed list of reasons a person can choose when filing a report (AC#8).
///
/// The same values exist in the Kotlin lane (`ReportReason`) so that both
/// platforms share one model (constitution P9).
public enum ReportReason: Equatable {
    /// The reported content is spam or unwanted advertising.
    case spam

    /// The reported person is harassing or threatening the reporter.
    case harassment

    /// The reported content is offensive or explicit.
    case inappropriateContent

    /// The reported profile appears to be fake or impersonating someone.
    case fakeProfile

    /// The reported person appears to be under the minimum age.
    case underageUser

    /// A reason not covered by the other options (see `Report.additionalText`).
    case other
}

/// Whether the report targets a person or a specific message.
///
/// The same values exist in the Kotlin lane (`ReportTargetKind`) so that both
/// platforms share one model (constitution P9).
public enum ReportTargetKind: Equatable {
    /// The report targets a user profile.
    case user

    /// The report targets a specific message.
    case message
}

/// A report filed by `reporterId` against a target.
///
/// AC#8: a person can report another person or a message, choosing from a
/// fixed list of reasons (`ReportReason`) and optionally adding free text.
///
/// P5 (constitution, enforceable): every person-to-person surface ships with
/// reporting in the same phase. This model is the domain record for that
/// obligation.
///
/// P1: report data is personal data. It is kept for as long as the report
/// record exists and is the caller's responsibility to purge on account
/// deletion.
///
/// The same shape exists verbatim in the Kotlin lane (Report.kt) so that
/// both platforms share one model (constitution P9).
public struct Report: Equatable {
    public let id: String
    public let reporterId: String
    /// The id of the reported entity — either a user id or a message id,
    /// depending on `targetKind`.
    public let targetId: String
    public let targetKind: ReportTargetKind
    public let reason: ReportReason
    /// Optional free text supplied by the reporter. Empty when the person did
    /// not provide any; never nil (absent and present-but-empty are treated
    /// identically at the domain layer).
    public let additionalText: String

    public init(
        id: String,
        reporterId: String,
        targetId: String,
        targetKind: ReportTargetKind,
        reason: ReportReason,
        additionalText: String = ""
    ) {
        self.id = id
        self.reporterId = reporterId
        self.targetId = targetId
        self.targetKind = targetKind
        self.reason = reason
        self.additionalText = additionalText
    }
}
