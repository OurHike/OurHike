// How far ahead a waypoint is, for the card a hiker opened by tapping its pin
// (#953, WIREFRAMES.md §5 and the design pass behind #941).
//
// The card's second line drawn by that pass reads `0.3 mi ahead`. It shipped
// without it, and #942's body said the number "would have to be invented".
// Half of that was true and the half that was not is what this module is: the
// distance is a subtraction, and it is the WORD that has to be earned.
//
// AHEAD IS A CLAIM ABOUT DIRECTION, NOT DISTANCE. A card telling a southbound
// hiker that a spring is "0.3 mi ahead" while they walk away from it has said
// the opposite of the truth, on the one subject this app can least afford to be
// wrong about. So the word tracks the direction the app has actually observed,
// and where it has observed none the sentence says "away" and claims nothing -
// which is exactly the discipline chrome/NextUpRail.tsx's `railHeading` already
// applies one surface over ("NEXT UP without a settled direction would be a
// coin flip printed as a claim").
//
// THE OBSERVED DIRECTION, NOT THE PLANNED ONE, and that is a choice. App.tsx's
// `heading` falls back to a declared hike's direction where the tracker has not
// committed, and the closure banner uses it: a closure a quarter mile up the
// trail matters more than the risk of naming the wrong end. This line is the
// other trade. It is read at rest, about a place the hiker chose to look at,
// and its cost of being wrong is somebody walking the wrong way to water - so
// it takes the more conservative of the two and degrades to "away", which is
// still a useful sentence. That is why this reads chrome/MapScreen.tsx's
// `direction` prop, which is the observed one, rather than a second prop.
//
// WHAT THIS LINE STILL CANNOT SAY is the other half of the drawn mock-up:
// "20 ft off trail". That is a distance from the centerline rather than along
// it, `PoiDetail` carries no such field, and nothing in the pipeline publishes
// one - #953 splits it off for that reason, and `wrongWay.ts`'s measured note
// that 72% of shelters sit past OFF_TRAIL_THRESHOLD_FT suggests "20 ft" is a
// mock-up's round number rather than a typical value.

import type { HikeDirection } from '../chrome/Header'
import { formatDistance, type UnitSystem } from './units'

export interface WaypointDistanceInputs {
  /**
   * The waypoint's mile along the centerline, or undefined where it has none.
   *
   * `PoiDetail.mile` is optional because the mile comes from the centerline
   * index, a separate download that can legitimately be missing - so this line
   * is absent for those places, like every other mile-derived fact on the card.
   */
  waypointMile?: number
  /**
   * The hiker's own mile, or undefined wherever `positionLine` would not print
   * one either.
   *
   * Undefined covers every state that module has a wording for - location off,
   * denied, no signal, still looking, no trail data, a fix that will not place
   * on the centerline - because all of them arrive here as the same absence.
   * The header says which one it is, in its own words; this line's only honest
   * response to all six is to say nothing.
   */
  hikerMile?: number
  /** The settled walking direction, or undefined while the tracker has not
   *  committed. See the header for why this is the observed one. */
  direction?: HikeDirection
  units?: UnitSystem
}

/**
 * `0.3 mi ahead`, `0.3 mi behind`, `0.3 mi away` - or null for no line at all.
 *
 * Null in three cases and they are all "say nothing": no mile for the hiker, no
 * mile for the place, or a distance that rounds to zero in the units on screen.
 *
 * THE ZERO CASE IS THE INTERESTING ONE. `0.0 mi ahead` puts a directional claim
 * on a number that is not there to support it, and at a tenth of a mile the
 * word would be a coin flip anyway. The tempting alternative is "Here", and
 * this must not say that: a zero distance ALONG the trail says nothing about
 * how far off it the place sits, and that is precisely the fact this card does
 * not have. Omitting is what chrome/PoiCard.tsx already does with the part
 * distance on the pin's own part - "0 ft away from the thing you are standing
 * on is noise".
 *
 * Asked of the formatter rather than of a threshold, so there is no distance
 * written down here to go stale: whatever `formatDistance` prints for zero is
 * what counts as zero. That makes the case unit-dependent - metric drops to
 * metres under a kilometre and so keeps the line down to about 10 m, where
 * imperial stays in miles and loses it under about 0.05 - and that asymmetry is
 * `formatDistance`'s, inherited deliberately rather than papered over here.
 * lib/units.ts records it as "a copy change to argue on its own evidence rather
 * than one to smuggle in", and this is not the place to smuggle it in.
 *
 * The precision is the default tenths, which is the resolution every other mile
 * on this card and in the header already carries. `'fine'` would print
 * `0.04 mi` and claim more about a GPS fix than `mi 1,407.2` beside it does.
 */
export function waypointDistance({
  waypointMile,
  hikerMile,
  direction,
  units = 'imperial',
}: WaypointDistanceInputs): string | null {
  if (waypointMile === undefined || hikerMile === undefined) return null
  if (!Number.isFinite(waypointMile) || !Number.isFinite(hikerMile)) return null

  const delta = waypointMile - hikerMile
  const distance = formatDistance(Math.abs(delta), units)
  if (distance === formatDistance(0, units)) return null

  // Which way somebody would have to be walking for this place to be in front
  // of them. Written out rather than folded into the comparison because the
  // whole risk this module exists to manage is getting that sign backwards, and
  // `(direction === 'NOBO') === delta > 0` is not a line anybody can check by
  // reading it. `delta === 0` cannot reach here - it prints as zero and has
  // already returned - so which branch it would fall into does not matter.
  const towardsIt: HikeDirection = delta > 0 ? 'NOBO' : 'SOBO'
  const word =
    direction === undefined ? 'away' : direction === towardsIt ? 'ahead' : 'behind'

  return `${distance} ${word}`
}
