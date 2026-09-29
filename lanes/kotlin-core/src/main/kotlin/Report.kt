/**
 * The fixed list of reasons a person can choose when filing a report (AC#8).
 *
 * The same values exist in the Swift lane (`ReportReason`) so that both
 * platforms share one model (constitution P9).
 */
enum class ReportReason {
    /** The reported content is spam or unwanted advertising. */
    SPAM,

    /** The reported person is harassing or threatening the reporter. */
    HARASSMENT,

    /** The reported content is offensive or explicit. */
    INAPPROPRIATE_CONTENT,

    /** The reported profile appears to be fake or impersonating someone. */
    FAKE_PROFILE,

    /** The reported person appears to be under the minimum age. */
    UNDERAGE_USER,

    /** A reason not covered by the other options (see [Report.additionalText]). */
    OTHER,
}

/**
 * Whether the report targets a person or a specific message.
 *
 * The same values exist in the Swift lane (`ReportTargetKind`) so that both
 * platforms share one model (constitution P9).
 */
enum class ReportTargetKind {
    /** The report targets a user profile. */
    USER,

    /** The report targets a specific message. */
    MESSAGE,
}

/**
 * A report filed by [reporterId] against a target.
 *
 * AC#8: a person can report another person or a message, choosing from a
 * fixed list of [reasons][ReportReason] and optionally adding free text.
 *
 * P5 (constitution, enforceable): every person-to-person surface ships with
 * reporting in the same phase. This model is the domain record for that
 * obligation.
 *
 * P1: report data is personal data. It is kept for as long as the report
 * record exists and is the caller's responsibility to purge on account
 * deletion.
 *
 * The same shape exists verbatim in the Swift lane (Report.swift) so that
 * both platforms share one model (constitution P9).
 */
data class Report(
    val id: String,
    val reporterId: String,
    /**
     * The id of the reported entity — either a user id or a message id,
     * depending on [targetKind].
     */
    val targetId: String,
    val targetKind: ReportTargetKind,
    val reason: ReportReason,
    /**
     * Optional free text supplied by the reporter. Empty when the person did
     * not provide any; never null (absent and present-but-empty are treated
     * identically at the domain layer).
     */
    val additionalText: String = "",
)
