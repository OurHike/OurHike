// How long a closure is, and the span above which it stops being a band.
//
// A band's job is to say "do not walk down there, go around". That sentence
// only means something while the closure is a stretch of trail rather than a
// region: a hiker has to be able to see where it starts, where it ends, and
// what is on either side of it.
//
// features/ATC_TRAIL_UPDATES.md measured the case that makes this necessary.
// ATC's Hurricane Helene update spans NOBO 239.4 to 637.8 - 398 miles, a fifth
// of the Appalachian Trail. Drawn the way map/closureLayers.ts draws a closure
// that is red barrier tape across a fifth of the map, at every zoom, and it
// would visually swamp the nine-mile Creeper Trail closure a hiker actually has
// to walk around. The more urgent warning buried under the broader one. ATC's
// own text says the damage is patchy: "The worst of the damage occurred along
// the section between...".
//
// This is the same instinct as features/HIKER_SAFETY.md's deliberately
// conservative wrong-way alert. A warning that fires too broadly trains people
// to ignore warnings, and a safety surface cannot afford to be ignored.
//
// IT IS NOT ONLY ATC'S PROBLEM. Nothing in the data model or the moderation
// path stops an OurHike moderator entering a 300-mile range today, which is why
// the rule lives here against `Closure` rather than beside whatever reads ATC's
// feed. ATC's data only made a hypothetical certain.

import type { Closure } from './closureBanner'

/**
 * The longest closure that is still drawn as a band, in miles.
 *
 * **PROVISIONAL, and deliberately so.** #462 is explicit that the honest way to
 * find this line is to look at the map at real zoom levels with real bands on
 * it, not to argue a number into a design document - and that issue carries a
 * `needs-field-testing` pass for exactly that. This constant is what that pass
 * changes; it is the only place the number appears.
 *
 * What the evidence actually constrains. Every mile range ATC published on
 * 2026-08-09: 0 (three point closures), 4.2, 9.2, and 398.4. The gap between
 * 9.2 and 398.4 is the whole of the uncertainty, and no number inside it is
 * contradicted by the data - which is why measuring more updates would not
 * settle it either.
 *
 * So the reasoning is about what a hiker does, and it errs toward drawing:
 * a closure is walked around by reaching a road crossing and going wide, which
 * is a two-to-three-day problem at AT walking speeds, so up to roughly fifty
 * miles is still a stretch of trail somebody detours. Past that it is a
 * multi-state logistics decision rather than a walk-around, and a band that
 * long stops describing something with visible ends. Fifty miles is also about
 * 2% of the trail, so a band remains a feature on the map rather than a region.
 *
 * Erring toward drawing is the safer of the two mistakes available here: a band
 * that should have been suppressed buries a more specific warning, while a band
 * that should have been drawn still leaves the hiker the banner, which needs
 * only a mile number (lib/closureBanner.ts). One failure loses the warning that
 * matters most; the other loses a drawing of a warning still being given.
 */
export const MAX_BAND_MILES = 50

/**
 * How much trail a closure covers, in miles.
 *
 * Absolute, because a range is a span whichever order its ends arrive in, and
 * a reversed pair is a data problem rather than a reason to call a closure
 * infinitely short. Zero for a point closure - ATC publishes several, and a
 * shelter or a footbridge is a single mile marker repeated.
 */
export function closureSpanMiles(closure: Closure): number {
  return Math.abs(closure.end_mile_marker - closure.start_mile_marker)
}

/**
 * Whether a closure covers too much trail to be drawn as a band.
 *
 * A closure this returns true for is still a real warning and still reaches the
 * hiker through the header banner - it simply is not painted along the
 * centerline. Non-finite mile markers answer false: that is a broken record
 * rather than a broad one, and map/closureLayers.ts already declines to draw a
 * closure it cannot place.
 */
export function isBroadAdvisory(closure: Closure): boolean {
  const span = closureSpanMiles(closure)
  return Number.isFinite(span) && span > MAX_BAND_MILES
}
