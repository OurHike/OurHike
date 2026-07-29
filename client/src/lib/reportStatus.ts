// Translates the backend's moderation-queue vocabulary into the four words a
// reporter actually sees (WIREFRAMES.md, "Load-bearing values": Waiting,
// Confirmed, Fixed, Not confirmed).
//
// The two vocabularies differ on purpose. `submitted / verified / resolved /
// dismissed` describes what a moderator is doing; `Waiting / Confirmed /
// Fixed / Not confirmed` describes what happened to your report. This module
// is the single place they meet.
//
// "Not confirmed" is deliberately not "rejected". WIREFRAMES.md §6 states the
// state "carries no penalty, deliberately" - someone who reports a blowdown a
// maintainer then cannot find has done nothing wrong, and an app that implies
// otherwise simply receives fewer reports next time. So there is no
// penalty/strike concept here at all, and `isPenalised` exists to make that a
// thing a test can hold onto rather than an absence someone has to notice.

export type BackendReportStatus = 'submitted' | 'verified' | 'resolved' | 'dismissed'

export type ReportStateWord = 'Waiting' | 'Confirmed' | 'Fixed' | 'Not confirmed'

export const REPORT_STATE_WORDS: Record<BackendReportStatus, ReportStateWord> = {
  submitted: 'Waiting',
  verified: 'Confirmed',
  resolved: 'Fixed',
  dismissed: 'Not confirmed',
}

export function reportStateFor(status: BackendReportStatus): ReportStateWord {
  return REPORT_STATE_WORDS[status]
}

/** Always false. Kept as a function so the rule is asserted, not assumed. */
export function isPenalised(_status: BackendReportStatus): boolean {
  return false
}
