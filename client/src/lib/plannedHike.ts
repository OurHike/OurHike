// The hike a person says they are on: where they started, where they are
// going, and nothing else (#335).
//
// Two numbers. Everything the app needs from them - which way is "ahead",
// where a route ends - falls out of the pair, and every field beyond them is
// features/HIKE_PLANNING.md arguing its way into v1 early. That doc is v2's
// first feature and this is deliberately not a small version of it: there is
// no route builder here, no days, no resupply, no timeline.
//
// WHY THIS IS NOT A PREFERENCE
//
// `UserPreferences` syncs to backend/app/schemas/preferences.py, which is
// `extra="forbid"` - so a key invented on the client becomes a 422 the moment
// somebody signs in. That was #242, fixed and now guarded by
// backend/tests/test_preferences_contract.py, which round-trips the client's
// real DEFAULT_PREFERENCES through the schema so the two field lists cannot
// drift silently again. A hike is not a display setting anyway; it gets its
// own key.
//
// WHY THE DIRECTION IS NOT STORED
//
// backend/app/models/hike.py made this call first and the reasoning carries
// over unchanged: "No `direction` column, deliberately. Whether a hike is NOBO
// or SOBO is fully determined by comparing overall_start_reference to
// overall_end_reference - storing a separate `direction` value would just be a
// second source of truth that could drift from the references it's derived
// from."
//
// WHERE THIS SYNCS, AND WHAT IT STILL DOES NOT TOUCH
//
// It follows the account since #892: the two numbers ride in the same
// exchange as the trips (`lib/tripsSync.ts`, features/ACCOUNT_SYNC.md phase
// B), which is where "which device wins" finally got written down. It is the
// one payload in that exchange that does NOT keep both on a conflict - a
// hiker is on one hike, and offering them two would be the app asking a
// question it invented - so it is last write wins, and being wrong costs
// re-entering two numbers.
//
// `POST /hikes` is still uncalled and is still not this. That table is the
// durable start/end reference the wrong-way alert reads SERVER-side, and it
// is complete CRUD over a collection with ids - syncing a singleton through
// it would mean every device remembering which row is "the" one, a second
// identifier to keep in step for no gain. #247 is the feature that needs the
// server to know a hike; #892 was the feature that needed two devices to
// agree on one.

import { get, set, del } from 'idb-keyval'
import { recordHikeEdit } from './tripSyncState'
import type { HikeDirection } from '../chrome/Header'

export const PLANNED_HIKE_KEY = 'ourhike:hike'

export interface PlannedHike {
  /** Miles from the southern terminus, where this hike begins. */
  startMile: number
  /** Where it ends. Smaller than `startMile` for a southbound hike - that is
   *  the whole of how direction is known. */
  endMile: number
}

/**
 * Which way this hike runs.
 *
 * Total, with no undefined arm, and that is the point of validating on the way
 * in: `plannedHike` refuses a pair that cannot answer this, so nothing
 * downstream has to carry a third case that only a rejected value could
 * produce.
 */
export function plannedDirection(hike: PlannedHike): HikeDirection {
  return hike.endMile > hike.startMile ? 'NOBO' : 'SOBO'
}

/**
 * A hike, or null if these two numbers cannot describe one.
 *
 * Refused rather than corrected. A start equal to its end has no direction and
 * covers no trail, and a hiker who typed the same number twice meant
 * something this cannot guess - silently nudging one end by a tenth of a mile
 * would invent a heading and then use it to decide which closures to warn
 * about.
 *
 * `trailMiles` bounds them where it is known. It comes from the centerline
 * index rather than a constant (lib/trailPosition.ts's `totalMiles`), so a
 * phone that has not finished downloading the trail yet passes undefined and
 * gets range checking only against zero - which is the honest amount of
 * checking available at that moment.
 */
export function plannedHike(
  startMile: number,
  endMile: number,
  trailMiles?: number,
): PlannedHike | null {
  if (!Number.isFinite(startMile) || !Number.isFinite(endMile)) return null
  if (startMile === endMile) return null
  if (startMile < 0 || endMile < 0) return null
  if (trailMiles !== undefined && (startMile > trailMiles || endMile > trailMiles)) {
    return null
  }

  return { startMile, endMile }
}

/** The whole trail, in the given direction. */
export function wholeTrail(direction: HikeDirection, trailMiles: number): PlannedHike {
  return direction === 'NOBO'
    ? { startMile: 0, endMile: trailMiles }
    : { startMile: trailMiles, endMile: 0 }
}

/**
 * What is stored, or null.
 *
 * Re-validated on the way out rather than trusted, the same call
 * lib/preferences.ts makes about a stored background it no longer recognises:
 * this is a value an earlier build wrote, and a pair that cannot describe a
 * hike must not reach the code that decides which way "ahead" is. Null is
 * already the state every screen handles - it is what a hiker who has not set
 * one has.
 */
export async function loadPlannedHike(): Promise<PlannedHike | null> {
  const stored = (await get(PLANNED_HIKE_KEY)) as Partial<PlannedHike> | undefined
  if (stored === undefined || stored === null) return null

  return plannedHike(stored.startMile as number, stored.endMile as number)
}

/**
 * Write what the ACCOUNT says, without recording it as a local edit (#892).
 *
 * `savePlannedHike`'s opposite number, for `adoptTrips`' reason: adopting
 * through the marking path would have this device push back what it just
 * pulled on every sync.
 */
export async function adoptPlannedHike(hike: PlannedHike | null): Promise<void> {
  if (hike === null) {
    await del(PLANNED_HIKE_KEY)
    return
  }
  await set(PLANNED_HIKE_KEY, hike)
}

export async function savePlannedHike(hike: PlannedHike): Promise<void> {
  await set(PLANNED_HIKE_KEY, hike)
  // Marked at the moment the hiker sets it (#892), the same way
  // lib/trips.ts records a trip edit and lib/preferences.ts records a
  // preference one. See lib/tripSyncState.ts.
  await recordHikeEdit()
}

/**
 * Forget it.
 *
 * A first-class action rather than an omission: finishing a hike, or changing
 * plans on the trail, must not mean clearing the app's data. Everything in
 * this app works without a hike - that is the state a hiker starts in, and it
 * has to be one they can get back to.
 */
export async function clearPlannedHike(): Promise<void> {
  await del(PLANNED_HIKE_KEY)
  // Clearing is a decision with a date on it, not an absence - and it has
  // to travel, or a second device hands the hike straight back (#892).
  await recordHikeEdit()
}

/**
 * The hike in one line, for the row that opens the picker.
 *
 * Here rather than in the screen because two things will want it - the More
 * row today, and whatever surfaces a hike on the map later - and a summary
 * written twice is a summary that eventually disagrees with itself.
 */
export function hikeSummary(hike: PlannedHike): string {
  const way = plannedDirection(hike) === 'NOBO' ? 'Northbound' : 'Southbound'
  const [low, high] = [hike.startMile, hike.endMile].sort((a, b) => a - b)
  const miles = (value: number) =>
    value.toLocaleString('en-US', { maximumFractionDigits: 1 })

  return `${way} · mi ${miles(low)} – ${miles(high)}`
}
