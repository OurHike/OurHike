// Where an earned item happened, on this phone only (#1963, features/
// CHALLENGES_BLAZE_CARD.md, slice 3; the frame is
// features/design/blaze-card/Where.dc.html).
//
// WHAT LEAVES THE PHONE DOES NOT CHANGE. A tag's cargo is still the item id,
// the authored time and `gps`/`hand` (lib/challengeDrafts.ts); the place is
// kept beside the tag in `ourhike:challenge-state` and read by the Where
// view and the poster, never by the outbox. useChallenges.test.ts holds the
// cargo byte-for-byte to what it was before a place existed.
//
// ASKED ONLY WHEN IT CAN MEAN SOMETHING (the brief's second hard
// requirement). Never for a `gps` tag - the day's walk is the place. Never
// for an at-home item the reviewer marked `on_trail: false`. For a named
// place the place is the answer already. What is left is an at-home item
// the ATC's own wording puts on the trail ("Watch the sunrise from the
// Trail") and "any shelter" earned by hand, where the sheet asks which.
//
// "HERE" ONLY WITH A FIX INSIDE THE CORRIDOR - the shell's snapped mile
// (lib/trailPosition.ts, within MAX_OFF_TRAIL_MILES), never a raw
// coordinate. With no fix the sheet opens on "On the trail, somewhere" with a
// state, for the hiker with no signal and no download, and no challenge
// screen ever asks to turn location on (the brief's "Second look").

import type { ChallengeItem } from './challenges'
import type { MileRange } from './walkedMiles'

/** The fourteen trail states, south to north - the order a thru-hiker
 *  meets them. Codes only: the mile each one starts at is a pipeline
 *  question (slice 5 derives it from the published centerline and the
 *  state outlines), and nothing here guesses one. */
export const TRAIL_STATES = [
  { code: 'GA', name: 'Georgia' },
  { code: 'NC', name: 'North Carolina' },
  { code: 'TN', name: 'Tennessee' },
  { code: 'VA', name: 'Virginia' },
  { code: 'WV', name: 'West Virginia' },
  { code: 'MD', name: 'Maryland' },
  { code: 'PA', name: 'Pennsylvania' },
  { code: 'NJ', name: 'New Jersey' },
  { code: 'NY', name: 'New York' },
  { code: 'CT', name: 'Connecticut' },
  { code: 'MA', name: 'Massachusetts' },
  { code: 'VT', name: 'Vermont' },
  { code: 'NH', name: 'New Hampshire' },
  { code: 'ME', name: 'Maine' },
] as const

export type TrailStateCode = (typeof TRAIL_STATES)[number]['code']

export function isTrailStateCode(value: unknown): value is TrailStateCode {
  return TRAIL_STATES.some((state) => state.code === value)
}

export function stateName(code: TrailStateCode): string {
  return TRAIL_STATES.find((state) => state.code === code)?.name ?? code
}

/** Where an earned item happened, as the hiker said. Device-only. */
export type TagPlace =
  /** The fix's snapped mile when it was earned. */
  | { kind: 'here'; mile: number }
  /** Somewhere in the miles walked today - the day's extent, no finer. */
  | { kind: 'walked'; fromMile: number; toMile: number }
  /** A place picked by name from the phone's own waypoints. */
  | { kind: 'poi'; poi: string; name: string; mile: number | null }
  /** On the trail, somewhere in one state. */
  | { kind: 'state'; state: TrailStateCode }
  /** At home, in town, on another trail. */
  | { kind: 'off' }

/** A stored place, or null for anything that is not one - a malformed
 *  place costs the place, never the tag (lib/challengeProgress.ts). */
export function readTagPlace(value: unknown): TagPlace | null {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return null
  const place = value as Record<string, unknown>
  switch (place.kind) {
    case 'here':
      return Number.isFinite(place.mile)
        ? { kind: 'here', mile: place.mile as number }
        : null
    case 'walked':
      return Number.isFinite(place.fromMile) && Number.isFinite(place.toMile)
        ? {
            kind: 'walked',
            fromMile: place.fromMile as number,
            toMile: place.toMile as number,
          }
        : null
    case 'poi':
      return typeof place.poi === 'string' && typeof place.name === 'string'
        ? {
            kind: 'poi',
            poi: place.poi,
            name: place.name,
            mile: Number.isFinite(place.mile) ? (place.mile as number) : null,
          }
        : null
    case 'state':
      return isTrailStateCode(place.state) ? { kind: 'state', state: place.state } : null
    case 'off':
      return { kind: 'off' }
    default:
      return null
  }
}

/**
 * Whether earning this item this way asks where it happened.
 *
 * A `gps` tag never asks: the day's walked miles are the place. A named
 * place never asks: the place is the answer. An at-home item asks only when
 * its reviewer said it happens on the trail; "any shelter" earned by hand
 * asks which.
 */
export function asksWhere(item: ChallengeItem, how: 'gps' | 'hand'): boolean {
  if (how === 'gps') return false
  switch (item.match.kind) {
    case 'self_report':
      return item.match.onTrail
    case 'poi_type':
      return true
    default:
      return false
  }
}

export interface WhereInput {
  /** The shell's fix snapped to the trail, or null: no fix, off the corridor,
   *  or no trail index on the phone. Never a raw coordinate. */
  fixMile: number | null
  /** Today's walked miles, merged (lib/passedToday.ts). */
  todayRanges: readonly MileRange[]
}

export interface WhereOptions {
  /** "Here · mi 714.9", only with a fix inside the corridor. */
  here: { mile: number } | null
  /** "Somewhere I walked today", only on a day something was walked: the
   *  day's whole extent, because the record keeps intervals and no order. */
  walked: { fromMile: number; toMile: number } | null
  /** Which option the sheet opens on: Here when there is one, else On the
   *  trail somewhere - the honest default for no signal and no download. */
  initial: 'here' | 'state'
}

export function whereOptions({ fixMile, todayRanges }: WhereInput): WhereOptions {
  const here = fixMile !== null && Number.isFinite(fixMile) ? { mile: fixMile } : null
  let walked: WhereOptions['walked'] = null
  if (todayRanges.length > 0) {
    walked = {
      fromMile: Math.min(...todayRanges.map((range) => range.startMile)),
      toMile: Math.max(...todayRanges.map((range) => range.endMile)),
    }
  }
  return { here, walked, initial: here !== null ? 'here' : 'state' }
}
