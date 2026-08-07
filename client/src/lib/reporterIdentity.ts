// What a report is signed as, when the hiker has and has not said (#233).
//
// `reporter_type` was a hardcoded `"thru"` at both call sites in App.tsx, so
// every report in the moderation queue claimed to be from a thru-hiker. That
// is not a cosmetic default. It is the ONE attribution that survives
// features/HIKER_SAFETY.md §2's anonymity window - the name is hidden and the
// date coarsened, and this is kept visible precisely because it carries
// information without identifying anyone - so a maintainer weighs a report by
// it, and a field that says the same thing about everybody weighs nothing.
//
// THE AWKWARD PART, WHICH IS A REAL CONSTRAINT RATHER THAN A CHOICE
//
// `Report.reporter_type` is non-nullable on the backend model, and its enum
// has no "unstated" member. So a report from someone who skipped the identity
// step still has to carry one of the four, and every one of them is a claim
// about a person who has not made it.
//
// Of the four, `day` is the floor: the least time on the trail, the least
// standing, the smallest thing a maintainer would weigh it as. Under-claiming
// is the safer error. Trusting a fabricated thru-hiker is the failure this
// closes; a real thru-hiker's first report being weighed as a day hiker's
// costs them one report's worth of standing and is fixed the moment they
// answer the screen that asks.
//
// Widening the contract - a nullable column, or an `unstated` member - is the
// better answer and is deliberately not taken here: it is a model change, a
// migration, and a decision about what the moderation queue shows for it,
// none of which belong in the change that stops the app inventing an answer.

import type { ReporterType } from './userPreferences'

/**
 * The floor, used only when nobody has said. Named rather than inlined so
 * that the one place it is decided is greppable from the queue it affects.
 */
export const UNSTATED_REPORTER_TYPE: ReporterType = 'day'

/**
 * How to sign a report, given what the hiker has told us.
 *
 * Takes the stored preference rather than the whole preferences object: this
 * is a decision about one field, and the narrower input is what lets the test
 * enumerate every case in five lines.
 */
export function signReportAs(stored: ReporterType | null): ReporterType {
  return stored ?? UNSTATED_REPORTER_TYPE
}

/**
 * Whether the hiker has actually answered.
 *
 * The screens need this apart from the value above, and that is the whole
 * reason it exists: Settings should say "Not set" rather than "Day hiker" to
 * someone who never chose, and the contribution flow asks only those who have
 * not. Reading `=== 'day'` at either call site would ask a real day hiker
 * again on every report.
 */
export function hasStatedReporterType(stored: ReporterType | null): boolean {
  return stored !== null
}
