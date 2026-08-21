// What stretch of the centerline the map is currently showing (#910 review).
//
// The maintainer's ask was that "what the map shows and the ribbon has are
// always in sync". Sync needs a shared quantity, and the only one the two
// surfaces both understand is a mile: the map holds a bounding box, the ribbon
// holds a span of the elevation profile. This turns the first into the second.
//
// The answer is the SPAN, first mile to last, not the set of miles actually
// inside the box. Those differ wherever the trail leaves the viewport and comes
// back - a switchbacked ridge crossing a corner, or the corridor wandering out
// of a portrait phone's narrow box and returning ten miles later. A span is
// what a ribbon can draw (its x axis is continuous by construction) and it is
// the honest superset: every mile on screen is inside it, and it never claims a
// mile is on screen that the profile does not cover.
//
// Cost, because this runs on every settled map move: the search is over the
// index's own latitude buckets rather than all ~600,000 centerline vertices, so
// a phone-sized viewport touches the handful of 0.05-degree bands it spans -
// the same structure and the same reasoning as locateOnTrail's.

import type { BoundingBox } from './legendContents'
import type { TrailIndex } from './trailPosition'

/** A span of the CLIENT index's mile axis. Callers carry it onto the
 *  pipeline's axis with lib/route.ts's anchors before comparing it to
 *  anything the profile said - the two scales are not interchangeable
 *  (HIKE_PLANNING.md Finding 1). */
export interface MileSpan {
  startMile: number
  endMile: number
}

/** Matches the bucketing in lib/trailPosition.ts. Restated rather than
 *  exported from there because it is that module's private business, and a
 *  shared constant would imply the two must always agree - they need only
 *  agree while this reads that index, which the test asserts. */
const BUCKET_DEGREES = 0.05

/**
 * The centerline's mile span inside `bbox`, or null when no centerline vertex
 * is in view at all.
 *
 * Null is the honest answer for a map looking at open ocean or two states east
 * of the corridor, and the ribbon's cue to fall back rather than draw a span
 * it invented. It is also what an antimeridian-crossing box gets: the AT does
 * not cross it, and a wrap-around test would be untestable machinery guarding
 * a case this app cannot reach.
 */
export function viewportMiles(index: TrailIndex, bbox: BoundingBox): MileSpan | null {
  const { lons, lats, miles, buckets } = index

  const south = Math.min(bbox.south, bbox.north)
  const north = Math.max(bbox.south, bbox.north)
  const west = Math.min(bbox.west, bbox.east)
  const east = Math.max(bbox.west, bbox.east)

  let low = Infinity
  let high = -Infinity

  const first = Math.floor(south / BUCKET_DEGREES)
  const last = Math.floor(north / BUCKET_DEGREES)

  for (let key = first; key <= last; key += 1) {
    const bucket = buckets.get(key)
    if (bucket === undefined) continue
    // The band is a latitude slice, so its vertices still have to be tested
    // against the box's own edges - all four of them.
    for (const i of bucket.indices) {
      const lat = lats[i]
      if (lat < south || lat > north) continue
      const lon = lons[i]
      if (lon < west || lon > east) continue
      const mile = miles[i]
      if (mile < low) low = mile
      if (mile > high) high = mile
    }
  }

  if (low > high) return null
  return { startMile: low, endMile: high }
}
