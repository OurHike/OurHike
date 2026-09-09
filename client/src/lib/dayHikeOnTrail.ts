// Which of a day hike's miles are on a long hike's trail (#1317).
//
// THE QUESTION IS NOT "IS THIS DAY HIKE ON THE A.T.", it is "how much of it
// is". A day hike is built across a junction network and routinely uses side
// trails, road walks and a spur to a car park; a hiker who walked four miles
// of the A.T. and two miles out to a trailhead walked four miles of the A.T.
// So this reports the stretch that IS on the trail rather than a yes or no,
// and a walk that touched the trail at all can join a hike.
//
// ONLY THE MILES ON THIS TRAIL COUNT, which is the hike roll-up's existing
// rule met one level up: `clipSpans` already clips every section to the
// hike's own ends, so a day hike that wandered contributes exactly its
// overlap and nothing else. Nothing here has to enforce that a second time -
// it only has to decide whether there is an overlap worth offering.
//
// PROJECTION, NOT A STORED FIGURE. `DayHike.figures` caches miles and climb
// for the list rows, deliberately without positions - "a route re-resolved
// against a newer data release should re-derive them rather than print last
// release's answer" (lib/dayHikes.ts). Same rule here: the trail mile of a
// coordinate is derived from the index in hand, every time.

import type { DayHike } from './dayHikes'
import { mileOnTrail, type TrailIndex } from './trailPosition'

/** The stretch of a hike's trail a day hike covers, or null for none. */
export interface OnTrailStretch {
  fromMile: number
  toMile: number
}

/**
 * The stretch of `trailIndex`'s trail this day hike covers, or null.
 *
 * Null when the walk is nowhere near the corridor - `mileOnTrail` already
 * refuses a point more than `MAX_OFF_TRAIL_MILES` from any centerline
 * vertex, so a park two states away resolves to nothing rather than to a
 * mile measured across the map.
 *
 * A SINGLE SPAN, low to high, rather than every piece: a day hike that
 * leaves the trail and rejoins it has a gap in the middle, and reporting the
 * pieces would be a precision the offer does not use. The hike's own
 * arithmetic clips whatever joins, so this span is an offer's bounds and
 * never a claim about miles walked.
 */
export function dayHikeOnTrail(
  hike: DayHike,
  trailIndex: TrailIndex,
): OnTrailStretch | null {
  let low: number | null = null
  let high: number | null = null

  for (const segment of hike.segments) {
    for (const point of segment) {
      // A day hike's points carry [lon, lat] pairs; the trail index takes
      // the named pair. Converted here rather than either store changing
      // shape for the other.
      const mile = mileOnTrail(trailIndex, {
        lon: point.coord[0],
        lat: point.coord[1],
      })
      if (mile === null) continue
      if (low === null || mile < low) low = mile
      if (high === null || mile > high) high = mile
    }
  }

  if (low === null || high === null) return null
  return { fromMile: low, toMile: high }
}

/** Whether a stretch overlaps a hike's own extent at all. Touching at a
 *  single mile counts: a day hike that started at the shelter a section
 *  ended at is on this hike's trail. */
export function overlaps(
  stretch: OnTrailStretch,
  bounds: { from: number; to: number },
): boolean {
  return stretch.toMile >= bounds.from && stretch.fromMile <= bounds.to
}
