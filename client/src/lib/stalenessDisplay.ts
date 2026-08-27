// How staleness and confidence are shown (WIREFRAMES.md §11).
//
// They are two separate channels and are kept as two separate functions on
// purpose:
//   - staleness  = when a human last said this was fine   -> ring + fade
//   - confidence = was it ever verified to exist          -> dashed outline
//
// A dashed pin that is Fresh means "we're not certain this spring exists, but
// someone checked recently." A solid pin that is Stale means "it definitely
// exists, but nobody has looked in months." Those are different things to
// tell a hiker who is deciding whether to carry two more litres, and merging
// the channels would collapse them into one vague signal.
//
// PROMINENCE IS REAL NOW, AND BOUNDED. This file used to say "staleness is
// described, never amplified" because raising stale pins' visibility was
// DATA_NUDGES.md territory and Post-MVP. That feature ships with #759, so
// the treatments below ARE the passive invitation that design specifies -
// a distinct pin treatment inviting a tap, nothing more. The bound is the
// maintainer's day-one decision (2026-08-20, recorded on #256):
//
//   - never confirmed, water         -> a subtle "no recent word" invite,
//                                       for everyone, from day one. OSM/USGS
//                                       water is unverified by FEATURES.md's
//                                       own admission, and water is where an
//                                       unknown costs a hiker most.
//   - never confirmed, anything else -> neutral. The fresh/ageing/stale
//                                       ladder applies only once a place has
//                                       a confirmation that aged out, so
//                                       "stale" keeps meaning "was
//                                       confirmed, went quiet" instead of
//                                       painting day one untrustworthy.
//
// And only the types the ask is scoped to wear any of it - water, shelter,
// campsite, resupply and, since #1122, parking (lib/fieldNotes.ts's
// NOTE_SCOPED_TYPES). A viewpoint has no condition to be stale about.
//
// This file does not decide that list and must not grow its own copy of it:
// a type the card asks a question about and the map draws as timeless would
// be two surfaces disagreeing about whether the answer mattered. Reading
// `isNoteScopedType` is what makes parking's arrival here a consequence
// rather than a second decision somebody had to remember to make.

import { stalenessTier, type StalenessTier } from './staleness'
import { isNoteScopedType } from './fieldNotes'

export interface StalenessTreatment {
  ring: 'green' | 'none' | 'grey-dotted' | 'faint-invite'
  opacity: number
  borderStyle: 'solid' | 'dotted'
}

export interface ConfidenceTreatment {
  outline: 'solid' | 'dashed'
}

const TREATMENTS: Record<StalenessTier, StalenessTreatment> = {
  fresh: { ring: 'green', opacity: 1, borderStyle: 'solid' },
  // No ring at all - the absence is the middle state, so the map doesn't
  // acquire a third ring colour that has to be learned.
  ageing: { ring: 'none', opacity: 1, borderStyle: 'solid' },
  stale: { ring: 'grey-dotted', opacity: 0.5, borderStyle: 'dotted' },
  // Neutral - indistinguishable from ageing's absence on purpose. The one
  // exception, water's invite, is per-type and lives in
  // stalenessPresentation below; this table does not know types.
  never: { ring: 'none', opacity: 1, borderStyle: 'solid' },
}

export function stalenessTreatment(tier: StalenessTier): StalenessTreatment {
  return TREATMENTS[tier]
}

/**
 * The whole rendering decision for one waypoint: which treatment, and which
 * words - or null for a type that carries no condition channel at all.
 *
 * This is the one place the maintainer's water exception lives. Everything
 * that draws a tier (the pin ring, the lanes, the card) asks here, so the
 * exception cannot drift into three slightly different exceptions.
 */
export function stalenessPresentation(
  poiType: string,
  tier: StalenessTier,
): { treatment: StalenessTreatment; words: string } | null {
  if (!isNoteScopedType(poiType)) return null

  if (tier === 'never' && poiType === 'water') {
    return {
      treatment: { ring: 'faint-invite', opacity: 1, borderStyle: 'solid' },
      // "No recent word" rather than "Never confirmed": the second reads as
      // a data glitch on day one, when it is true of every spring on the
      // map. This is an honest statement about an unverified source, and
      // the invitation is the styling, never a count or an ask in words.
      words: 'No recent word',
    }
  }

  return {
    treatment: stalenessTreatment(tier),
    words: tier === 'never' ? 'Never confirmed' : lastConfirmedWord(tier),
  }
}

function lastConfirmedWord(tier: StalenessTier): string {
  // The one-word state the lanes have room for; the card prints the full
  // dated sentence via lastConfirmedText below.
  if (tier === 'fresh') return 'Confirmed recently'
  if (tier === 'ageing') return 'Confirmed a while back'
  return 'Gone quiet'
}

export function confidenceTreatment(confidence: 'high' | 'low'): ConfidenceTreatment {
  return { outline: confidence === 'low' ? 'dashed' : 'solid' }
}

/**
 * The map-pin form of the decision above: which ring a waypoint wears and
 * whether its pin fades, from when a human last said it was fine.
 *
 * Returns a lookup rather than answering directly because the map rebuilds
 * ~2,800 features in one pass (map/poiLayers.ts) and each asks this - the
 * shape MapView can hand straight to `attachPoiData`. The policy stays
 * entirely in {@link stalenessPresentation}; this just flattens a treatment
 * into the two properties a paint expression can match on.
 */
export function pinConditionFor(
  lastConfirmedFor: (poiId: string) => Date | null,
): (poiId: string, poiType: string) => { ring: string; faded: boolean } {
  return (poiId, poiType) => {
    const presentation = stalenessPresentation(
      poiType,
      stalenessTier(lastConfirmedFor(poiId)),
    )
    if (presentation === null) return { ring: 'none', faded: false }
    return {
      ring: presentation.treatment.ring,
      faded: presentation.treatment.opacity < 1,
    }
  }
}

const DAY_MS = 24 * 60 * 60 * 1000

/**
 * The words that accompany the visual channel - WIREFRAMES.md insists the
 * state is always stated in text too, since a ring alone is not readable in
 * glare or by someone who has never been told what it means.
 */
export function lastConfirmedText(lastConfirmed: Date | null, now: Date): string {
  if (lastConfirmed === null) return 'Never confirmed'

  const month = lastConfirmed.toLocaleDateString('en-US', {
    month: 'long',
    timeZone: 'UTC',
  })
  const days = Math.floor((now.getTime() - lastConfirmed.getTime()) / DAY_MS)

  if (days === 0) return `Last confirmed in ${month} · today`
  if (days === 1) return `Last confirmed in ${month} · yesterday`
  return `Last confirmed in ${month} · ${days} days ago`
}
