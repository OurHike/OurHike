// What a walked day was, from what the phone already knows (#966, wireframe
// 2c frame 1).
//
// BACKWARD-LOOKING ONLY, and this module is where that rule is kept or
// lost. Nothing here takes a target, a plan or a day's intended length as
// an argument, so nothing here can compare what happened against what was
// meant to - "you passed mile 500" is memory, "you're 2 days behind" is
// pressure, and the difference between the two surfaces is the difference
// between a paper log and a schedule that scolds (OurHikeValues.md #1).
// The functions below take a pair of miles and a POI list. There is no
// argument they could be given that would let them score anybody.
//
// EVERY TILE ON THAT CARD DOES NOT SHIP HERE, deliberately. The wireframe
// asks for four counts and annotates them "every number here already exists
// on the phone". Two do:
//
//   photos taken       lib/poiPhotos.ts dates every own photo, so any past
//                      day's count falls out of history that already exists
//                      (ownPhotosOn).
//   longest dry run    the water waypoints inside the day's miles, below.
//
// Two do not, and are omitted rather than approximated (#967): a field note
// is enqueued into `ourhike:outbox` and REMOVED on a successful flush, so
// "field notes filed" would count only the notes a hiker has not managed to
// send yet, and "water you drank at" needs that same absent record plus a
// claim - that somebody drank - which nothing on the phone observes.
// CLAUDE.md's rule, applied to a memory card rather than a safety path:
// omit rather than guess, and never let a display outrun its source.

import type { StoredPoi } from './trailData'

/**
 * The round mile a day crossed, or null.
 *
 * A hundred at a time. Fifties would fire on most days of a thru-hike and a
 * line that appears every other day is furniture rather than memory, which
 * is the whole reason this card gets one and not a list.
 *
 * @unvalidated 100 is picked, not measured. What would settle it: how often
 * the line actually appears across a generated thru-hike's days - a step
 * that fires on one day in seven is a nice surprise, one that fires on one
 * in two is a banner.
 *
 * Crossings are counted STRICTLY INSIDE the day: a day that ends exactly on
 * mile 500 has arrived at it, not passed it, and the card says "somewhere in
 * there you passed" - which would be a small lie about a hiker standing on
 * the marker. Direction-agnostic, because a southbound day walks the same
 * markers in the other order; the last one reached in walk order is the one
 * returned, since that is the one a hiker remembers as today's.
 */
export function milestoneCrossed(
  startMile: number,
  endMile: number,
  step = MILESTONE_STEP,
): number | null {
  if (!Number.isFinite(startMile) || !Number.isFinite(endMile)) return null
  if (step <= 0) return null

  const low = Math.min(startMile, endMile)
  const high = Math.max(startMile, endMile)
  // Strictly inside, hence floor/ceil onto the open interval.
  const first = Math.floor(low / step) * step + step
  const last = Math.ceil(high / step) * step - step
  if (first > last) return null

  // Walk order: northbound reaches the smallest marker first, southbound the
  // largest. Either way the LAST one reached is what today ended past.
  return endMile >= startMile ? last : first
}

export const MILESTONE_STEP = 100

/** The longest stretch of a day with no water waypoint on it. */
export interface DryRun {
  miles: number
  /** The stretch's own ends, on the pipeline's mile axis. */
  fromMile: number
  toMile: number
  /** Water waypoints inside the day - 0 means the whole day was one run. */
  waterCount: number
}

/**
 * The longest run of today's miles carrying no water waypoint.
 *
 * READ THE CLAIM EXACTLY, because the screen has to print it exactly: this
 * is the longest stretch of the day with **no water waypoint on the map**,
 * which is not the same sentence as "the longest stretch with no water".
 * Water coverage is known-incomplete - features/POI_VISIBILITY.md and the
 * water-distance pipeline both say so - and a hiker who read the second
 * sentence off a screen that could only support the first would be carrying
 * their planning decisions on somebody else's missing data.
 *
 * The day's own boundaries bound the run, so a day with no water waypoint
 * at all reports the whole day (waterCount 0). That is true as stated:
 * there is no water waypoint on any of it. What lies just outside the day is
 * not this card's business - it is the ribbon's, live, while walking.
 *
 * Null when the POI list carries no miles at all, which is what a download
 * from before #753 looks like. Absent miles cannot be told apart from
 * absent water, and guessing between them is the failure this returns null
 * to avoid.
 */
export function longestDryRun(
  pois: readonly StoredPoi[],
  startMile: number,
  endMile: number,
): DryRun | null {
  if (!Number.isFinite(startMile) || !Number.isFinite(endMile)) return null
  if (!pois.some((poi) => poi.mile !== undefined)) return null

  const low = Math.min(startMile, endMile)
  const high = Math.max(startMile, endMile)
  if (high <= low) return null

  const water = pois
    .filter(
      (poi): poi is StoredPoi & { mile: number } =>
        poi.type === 'water' && poi.mile !== undefined,
    )
    .map((poi) => poi.mile)
    // INCLUSIVE of the day's own ends (#986). A day that starts at a spring
    // and ends at one had both excluded by a strict comparison, so the card
    // said "no water waypoint on any of today" about a day with water at
    // both ends of it. Water is one of the four ways this app can hurt
    // somebody, and that sentence is the wrong one to get wrong.
    .filter((mile) => mile >= low && mile <= high)
    .sort((a, b) => a - b)

  // The day's ends close the first and last runs. A day with no water on it
  // is one run the length of the day, which is the honest answer and not an
  // absence to be hidden.
  // A spring exactly on a boundary is already in `water`, so it would appear
  // twice here - harmless for the maximum (a zero-length run never wins) and
  // wrong for the count, which is why the count comes off `water` deduped
  // rather than off this list.
  const marks = [low, ...water, high]
  let best = { miles: 0, fromMile: low, toMile: low }
  for (let i = 1; i < marks.length; i++) {
    const miles = marks[i] - marks[i - 1]
    if (miles > best.miles) {
      best = { miles, fromMile: marks[i - 1], toMile: marks[i] }
    }
  }

  return { ...best, waterCount: new Set(water).size }
}
