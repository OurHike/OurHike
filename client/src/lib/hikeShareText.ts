// A finished hike as plain text (#1317).
//
// `lib/dayHikePlanText.ts`'s idiom at the other end of a walk: the app's
// figures print in the app's own words, and the card survives a phone with
// no OurHike on it. That is the whole point of the plain-text path - the
// in-app share is mutual-accounts-only by design
// (features/COMMUNITY_BUILDING.md), and everyone else in a hiker's life is
// reached by text they can paste anywhere.
//
// NO LOCATION, EVER. The card holds what was walked and when. It does not
// hold where the hiker is, and sharing a hike must never become a location
// channel - check-ins are their own opt-in-per-session feature with their
// own unmistakable indicator, and that separation is the reason both exist.
//
// FIGURES ARE THE SAME TWO. Miles walked and miles to go, and for a finished
// hike the second is zero and says so. No percentage, no rank, no
// comparison - the card leaves the app and cannot be corrected afterwards,
// which makes it the worst possible place to invent a claim.

import type { UnitSystem } from './units'
import { formatDistance } from './units'
import { longDate } from './hikeText'

export interface HikeCardFacts {
  name: string
  trailName: string
  walkedMi: number
  toGoMi: number
  /** ISO days, or null where nothing is dated. */
  startedOn: string | null
  finishedOn: string | null
  daysWalking: number
  sections: number
  /** Per-leg, in walk order - never one direction for the whole hike. */
  directions: readonly ('NOBO' | 'SOBO' | null)[]
}

/**
 * The card.
 *
 * Lines are omitted rather than printed empty: a card saying "Dates: —" is
 * worse than one that simply does not mention dates, because the dash reads
 * as a fact the app lost rather than one nobody entered.
 */
export function hikeShareText(facts: HikeCardFacts, units: UnitSystem): string {
  const lines: string[] = [facts.name, facts.trailName, '']

  lines.push(
    `${formatDistance(facts.walkedMi, units)} walked · ${formatDistance(
      facts.toGoMi,
      units,
    )} to go`,
  )

  if (facts.startedOn !== null || facts.finishedOn !== null) {
    lines.push(
      [
        facts.startedOn === null ? null : longDate(facts.startedOn),
        facts.finishedOn === null ? null : longDate(facts.finishedOn),
      ]
        .filter((part) => part !== null)
        .join(' – '),
    )
  }

  if (facts.daysWalking > 0) {
    lines.push(`${facts.daysWalking} days walking`)
  }
  lines.push(`${facts.sections} ${facts.sections === 1 ? 'section' : 'sections'}`)

  // The directions the hike was actually walked in, in order - so a
  // flip-flop reads as one, rather than as whichever end happened to be
  // furthest north. A leg covering no ground contributes nothing.
  const walked = facts.directions.filter((leg) => leg !== null)
  if (walked.length > 0) {
    lines.push(
      walked.map((leg) => (leg === 'NOBO' ? 'northbound' : 'southbound')).join(', then '),
    )
  }

  return lines.join('\n')
}
