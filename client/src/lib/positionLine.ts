// The one line the header gives to where the hiker is (#312).
//
// It used to be a ternary on the mile: a number, or "Looking for GPS…". That
// second string covered six different situations, and three of them will never
// resolve - permission denied, geolocation unsupported, and the location step
// skipped during onboarding, which writes the preference once and had no other
// way back. Telling someone to keep waiting for something that is never coming
// is the same failure as a stale position drawn like a live one: the screen is
// confident and wrong, and the hiker has no way to tell.
//
// `useGeolocation` has modelled every one of these states from the beginning.
// The header simply never saw them.
//
// WHY THIS IS A MODULE AND NOT A TERNARY IN THE HEADER
//
// Two reasons, and the second is the one that matters. It is a decision with
// eight outcomes and a precedence between them - "off" outranks "no signal",
// which outranks "off the trail" - and that is worth stating once where it can
// be read and tested. And the header is the wrong place to own it: what is
// wrong with the fix is the shell's knowledge, not the chrome's.
//
// EVERY LINE HERE IS SHORT ON PURPOSE
//
// It renders in the mono position slot beside the trail name, on a phone, in
// sunlight. Nothing below is longer than "Looking for GPS…" was, so nothing
// reflows the header - and each says what is wrong rather than what the app
// happens to be doing about it.

import type { GeolocationState } from './useGeolocation'
import type { HikeDirection } from '../chrome/Header'
import { followPosition, type FollowState } from './dayHikeFollow'
import type { UnitSystem } from './units'

export interface PositionLineInputs {
  /** What the watch is actually doing (lib/useGeolocation.ts). */
  gps: GeolocationState
  /**
   * Whether the hiker has location switched on at all.
   *
   * Separate from `gps.status === 'idle'`, which is what the hook reports
   * while disabled, because the two need opposite copy: "off" is a setting
   * the hiker can flip back and "idle" is a hook that has not started. It is
   * also the state a skipped onboarding step leaves behind, which had no
   * words of its own and no way out before this.
   */
  enabled: boolean
  /** Where the fix falls along the trail, when it can be placed at all. */
  mile?: number
  /** Omitted until enough walking has happened to tell which way. */
  direction?: HikeDirection
  /**
   * Whether the centerline index is loaded.
   *
   * Without it there is no mile to compute, and saying "off the trail" to a
   * hiker standing squarely on it - because their trail data has not
   * downloaded - would be a confident false statement about the one thing
   * this line exists to answer.
   */
  trailReady: boolean
  /**
   * The day hike being followed, when there is one (lib/dayHikeFollow.ts).
   *
   * It outranks the mile because on that ground the mile is not an answer:
   * #928's finding is that a park has no single axis to number, so
   * `locateOnTrail` either refuses the fix outright - printing "Off the
   * trail" at somebody walking a blazed loop - or, in the corridor where the
   * A.T. and a park network overlap, prints a Springer mile at somebody who
   * is not walking to Springer. Both are worse than saying nothing.
   *
   * It does NOT outrank the GPS states above it. Every one of those is a
   * reason the position is unknown, and following a route does not make a
   * denied permission or a lost fix any less true.
   */
  follow?: FollowState | null
  /** Which units the follow reading converts to. Defaulted like every other
   *  units prop here, and read ONLY by that reading - see followPosition for
   *  why the A.T. mile stays a mile. */
  units?: UnitSystem
}

/**
 * Always one decimal place, with a thousands separator: "1,407.2".
 *
 * Fixed precision keeps the number from changing width as the hiker walks,
 * which would otherwise make the whole header twitch.
 */
function formatMile(mile: number): string {
  return mile.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
}

export function positionLine({
  gps,
  enabled,
  mile,
  direction,
  trailReady,
  follow = null,
  units = 'imperial',
}: PositionLineInputs): string {
  // First, because it is the only one of these the hiker chose, and the only
  // one with a fix that is one tap away in Settings. It also outranks the
  // hook's own status: with the watch never started, `idle` says nothing
  // about why.
  if (!enabled) return 'Location is off'

  switch (gps.status) {
    // Settled, both of them. Neither will resolve by waiting, which is the
    // whole reason they are not "Looking for GPS…".
    case 'unsupported':
      return 'No GPS on this phone'
    case 'denied':
      return 'Location blocked'
    // Not settled: a timeout or a lost fix is weather, and the watch is still
    // running - so this says what is true now without implying it is
    // permanent, and the next fix flips it back on its own.
    case 'unavailable':
      return 'No GPS signal'
    case 'idle':
    case 'locating':
      return 'Looking for GPS…'
    case 'located':
      break
  }

  // A fix on a route the hiker chose, which is a better answer than any mile
  // - and reachable even where the centerline index below has not loaded,
  // because a day hike routes over the junction graph and needs no
  // centerline at all.
  if (follow !== null) return followPosition(follow, units)

  // A fix, and nowhere to put it. Two different reasons, and they are not
  // interchangeable: one is the app missing data, the other is a claim about
  // where the hiker is standing.
  if (!trailReady) return 'No trail data'
  if (mile === undefined) return 'Off the trail'

  return `mi ${formatMile(mile)}${direction === undefined ? '' : ` · ${direction}`}`
}
