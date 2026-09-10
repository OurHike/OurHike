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
import { mileMarker } from './planDisplay'

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
   * The short name of the trail whose hike this build cannot measure, or
   * null when it can (#1357).
   *
   * A THIRD REASON THE MILE IS MISSING, and it is neither of the two below
   * it. `trailReady` is the app missing data and "Off the trail" is a claim
   * about where the hiker is standing; this is the app holding the data,
   * the hiker standing squarely on their trail, and the download carrying
   * no mile axis for it. Saying either of the other two here would be
   * false - the first about the phone, the second about the hiker.
   *
   * It is the same refusal `lib/hikeText.ts`'s `setupRefusal` already makes
   * at hike creation ("a figure on any other trail would be an A.T. mileage
   * wearing somebody else's name"), carried past creation to the figures -
   * and the same one the `follow` branch below already makes for a day
   * hike, whose note about printing "a Springer mile at somebody who is not
   * walking to Springer" describes this case exactly.
   *
   * The NAME rather than a boolean, because the line has room for it and
   * "No miles on the L.P." tells a hiker which of their two answers is
   * missing where "No miles here" does not. lib/trails.ts's `shortName`
   * (#1307) is where it comes from.
   */
  unmeasuredTrail?: string | null
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
  /**
   * Whether any trail is taken at all - a long hike's, or one tapped on the
   * map (lib/takenTrail.ts) - since the maintainer's review of #1374. Below
   * the GPS states, which are true whatever is taken, and below a followed
   * walk, which measures its own ground; above the mile, because the mile
   * is a reading against a trail and "Off the trail" is a claim about one.
   * With nothing taken there is no trail to be off, so the slot says where
   * the fix stands and what would give it a mile. Defaults to true so every
   * caller that never asks - the follow header, the Today read-out - is
   * unaffected.
   */
  trailTaken?: boolean
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
/** A trail mile marker as the position line prints it: lib/planDisplay.ts's
 *  `mileMarker`, the one home for the trail's own axis - never a converted
 *  distance, which is why neither is in lib/units.ts. */
const formatMile = mileMarker

export function positionLine({
  gps,
  enabled,
  mile,
  direction,
  trailReady,
  unmeasuredTrail = null,
  follow = null,
  trailTaken = true,
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

  if (!trailTaken) return 'Located · tap a trail to take it'

  // A fix, and nowhere to put it. Two different reasons, and they are not
  // interchangeable: one is the app missing data, the other is a claim about
  // where the hiker is standing.
  // Above both of the next two, because it is true of the app AND of the
  // hiker at once: the data is here and the hiker is somewhere real, and
  // neither "No trail data" nor "Off the trail" would be a true sentence.
  if (unmeasuredTrail !== null) return `No miles on the ${unmeasuredTrail}`

  if (!trailReady) return 'No trail data'
  if (mile === undefined) return 'Off the trail'

  return `mi ${formatMile(mile)}${direction === undefined ? '' : ` · ${direction}`}`
}
