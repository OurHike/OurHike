// The first-contribution flow (WIREFRAMES.md §6).
//
// "The report is written and saved first; then Google / Apple / email, then
// trail name + reporter type." The ordering is the design, not a detail.
//
// Picture the actual moment: someone is standing at a blowdown with one bar,
// they have written down what they saw, and the app responds by sending them
// off to authenticate with Google. If that round trip fails - and on a ridge
// it often will - they can end up with neither an account nor their report.
// Saving to the outbox before authentication is ever mentioned means the
// worst case is an unsent report instead of a lost one.
//
// Sign-in is asked here rather than during onboarding because contributing is
// the first thing that genuinely needs an identity. Reading the map never
// does, and asking up front would put an account between someone and a map
// they have not yet been given a reason to trust.

import { enqueue, type OutboxItem, type ReportDraft } from './outbox'

export interface ContributionState {
  hasAccount: boolean
  /** Whether a trail name and reporter type have been set. */
  hasIdentity: boolean
}

export type ContributionStep = 'sign-in' | 'identity' | 'send'

/**
 * Saves the report. Always the first thing that happens, before any question
 * about who the contributor is.
 */
export async function beginContribution(
  draft: ReportDraft,
  authoredAt: Date,
  photo?: Blob,
  /**
   * Hold it back until this moment, for the report window's Undo (#1133).
   *
   * Passed straight through rather than decided here. Whether a report is
   * retractable is a property of the SURFACE that filed it - the window files
   * on a tap and owes an undo; the long form files on a submit and does not -
   * and this function's job is only that saving happens before anything else
   * is asked.
   *
   * Note what it protects against, which is this file's own next line: the
   * caller flushes the outbox immediately after saving (#640), so without the
   * hold the report would routinely be gone before the countdown finished.
   */
  holdUntil?: Date,
): Promise<OutboxItem> {
  // The photo is saved here with everything else, for the reason above: it is
  // part of what the hiker wrote down, and it must not depend on the sign-in
  // round trip that has not been asked for yet.
  return enqueue(draft, authoredAt, photo, holdUntil)
}

export function stepAfterSaving({
  hasAccount,
  hasIdentity,
}: ContributionState): ContributionStep {
  // Account before identity, always: a trail name belongs to a profile, so
  // asking for one first would mean collecting something with nowhere to put
  // it.
  if (!hasAccount) return 'sign-in'
  if (!hasIdentity) return 'identity'
  return 'send'
}

export interface ReporterTypeOption {
  id: ReportDraft['reporter_type']
  label: string
  /**
   * True where the claim only means something once a club confirms it.
   * Anyone may select maintainer; it simply stays unverified until then,
   * which is what stops it being a self-assigned badge.
   */
  clubGranted: boolean
}

export const REPORTER_TYPES: ReporterTypeOption[] = [
  { id: 'thru', label: 'Thru-hiker', clubGranted: false },
  { id: 'section', label: 'Section hiker', clubGranted: false },
  { id: 'day', label: 'Day hiker', clubGranted: false },
  { id: 'maintainer', label: 'Maintainer', clubGranted: true },
]
