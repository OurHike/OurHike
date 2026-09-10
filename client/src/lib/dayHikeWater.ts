// The water a day hike passes (#1373, step 3's "Water on route").
//
// A hiker deciding whether to carry two litres or four wants to know where
// the route crosses water, and until step 3 nothing on the phone answered
// that for a day hike: the waypoint card knows a spring's distance from a
// SHELTER (lib/waterDistance.ts, #529), and the builder knows the shelters
// and campsites a hiker picked as stops, but no surface projected the water
// points themselves onto the walk being built.
//
// THE SAME PROJECTION THE STOPS USE, on the same axis. `projectOnCourse`
// (lib/dayHikeCourse.ts) answers where a point sits along the walk - miles
// from the first tap - and how far off the line it is; a water point close
// enough to the line is on the route, at that mile. The axis is the walk's
// own, never the pipeline's NOBO mile (#1045's lesson), so "0.8 mi in" is a
// fact about this walk.
//
// EVERY PASS, NOT THE NEAREST VERTEX. An out-and-back walks the same line
// twice, and a loop can re-cross a stretch; the spring at mile 1.2 out is
// the spring at mile 4.8 back, and a hiker past the turnaround with a
// litre left is served by the second row, not the first. So a point is
// listed once per pass of the walk - a run of vertices within reach,
// separated from the next run by more than the reach walked along the line
// - at the nearest vertex of that pass. The first version of this took the
// single nearest vertex, which on an out-and-back put every water point on
// the outbound leg only; the follow card's "what's left" then listed no
// water at all once the hiker turned round (#1374 review).
//
// WHAT IT DOES NOT CLAIM. An empty list means the published waypoints hold
// no water point near this walk, which is not the same as no water: the
// water layer is thin (measured 2026-08 for #529: 97% of shelters have no
// mapped water within 250 m), and a stream the map has no point for is not
// a stream that is not there. So a surface prints the rows it has and
// prints NOTHING - no "no water on this route" - when it has none. Omit
// rather than guess, on the one path that is about running dry.

import { straightLineMetres } from './dayHikeShelf'
import { metresToMiles } from './trailGraph'
import { feetFromMetres } from './units'
import type { DayHikeCourse } from './dayHikeCourse'
import type { StoredPoi } from './trailData'

/**
 * How far off the walk a water point may sit and still be listed as on it.
 *
 * @unvalidated. Picked at 500 ft - a spring a short scramble below the
 * trail is water a hiker would use; one a quarter-mile down a side trail is
 * a detour they would have to decide on, and this list is not the place to
 * decide it for them. Not derived from anything: nobody has measured how far
 * published water points actually sit from the lines they serve.
 *
 * What would settle it: the distribution of distances from every published
 * water waypoint to the nearest vertex of the published trail graph, which
 * `pipeline/build_water_distance.py` already computes shelter-to-water and
 * could compute trail-to-water; the threshold should be a percentile of
 * that rather than a round figure. Until then the row says how far off the
 * walk each point is, so the number a hiker reads is the measurement and
 * not the threshold.
 */
export const WATER_ON_ROUTE_FEET = 500

/**
 * Below this, the off-walk distance is not printed: a point a few strides
 * from the line is on it for every purpose a hiker has, and "12 ft off the
 * walk" is a claim of precision the vertex-nearest projection does not have
 * (projectOnCourse's own note). A display rule, not a fact about the data.
 *
 * @unvalidated. 100 ft is picked, not measured: roughly the half-vertex
 * spacing the projection's own error bound names, rounded to a figure a
 * reader recognises. What would settle it is the same distribution
 * `WATER_ON_ROUTE_FEET` waits on - how far published water points sit from
 * the lines they serve - read for where "on the line" stops being true.
 */
export const WATER_SAID_OFF_FEET = 100

export interface RouteWater {
  poiId: string
  name: string
  /**
   * Trail miles from the walk's first tap - a DISTANCE along this walk,
   * never a mile marker on the pipeline's axis, and named so a units
   * formatter may take it (test/unitDisplay.test.ts's rule).
   */
  alongMi: number
  /** Straight-line feet from the point to the nearest vertex of this pass. */
  offCourseFeet: number
}

/** Degrees of latitude per metre, for the prefilter's box; longitude is
 *  this over the cosine of the latitude. */
const DEGREES_PER_METRE = 1 / 111_320

/**
 * The passes `course` makes within `reachMetres` of `at`: for each, the
 * nearest vertex's mile and distance. One pass is a run of vertices within
 * reach; the run ends when the walk has gone more than twice the reach
 * along the line since the last vertex within it - far enough that coming
 * back is a second visit, not the same bend.
 */
function passesNear(
  course: DayHikeCourse,
  at: { lon: number; lat: number },
  reachMetres: number,
): Array<{ mile: number; metres: number }> {
  const passes: Array<{ mile: number; metres: number }> = []
  const rejoinMiles = metresToMiles(2 * reachMetres)
  let current: { mile: number; metres: number; lastMile: number } | null = null
  for (const point of course.points) {
    const metres = straightLineMetres({ lon: point.lon, lat: point.lat }, at)
    if (metres > reachMetres) continue
    if (current !== null && point.mile - current.lastMile > rejoinMiles) {
      passes.push({ mile: current.mile, metres: current.metres })
      current = null
    }
    if (current === null) {
      current = { mile: point.mile, metres, lastMile: point.mile }
    } else {
      current.lastMile = point.mile
      // Strictly nearer, so a tie keeps the earlier vertex - the same rule
      // projectOnCourse keeps, for the same reason: a stable row order.
      if (metres < current.metres) {
        current.mile = point.mile
        current.metres = metres
      }
    }
  }
  if (current !== null) passes.push({ mile: current.mile, metres: current.metres })
  return passes
}

/** The published water points along `course`, in the order the walk
 *  reaches them - once per pass of the walk (see the header). Empty when
 *  there are none, and only then; the header says what that does and does
 *  not mean. */
export function waterOnCourse(
  course: DayHikeCourse,
  pois: readonly StoredPoi[],
  within = WATER_ON_ROUTE_FEET,
): RouteWater[] {
  if (course.points.length === 0) return []
  const reachMetres = within / feetFromMetres(1)
  // The walk's box, padded by the reach: a point outside it cannot be
  // within reach of any vertex, and the whole waypoint list is scanned
  // here, on every tap while the route is built.
  let west = Infinity
  let east = -Infinity
  let south = Infinity
  let north = -Infinity
  for (const point of course.points) {
    west = Math.min(west, point.lon)
    east = Math.max(east, point.lon)
    south = Math.min(south, point.lat)
    north = Math.max(north, point.lat)
  }
  const padLat = reachMetres * DEGREES_PER_METRE
  const padLon = padLat / Math.max(0.1, Math.cos((((south + north) / 2) * Math.PI) / 180))
  const found: RouteWater[] = []
  for (const poi of pois) {
    if (poi.type !== 'water') continue
    if (
      poi.lon < west - padLon ||
      poi.lon > east + padLon ||
      poi.lat < south - padLat ||
      poi.lat > north + padLat
    ) {
      continue
    }
    for (const pass of passesNear(course, { lon: poi.lon, lat: poi.lat }, reachMetres)) {
      found.push({
        poiId: poi.id,
        name: poi.name,
        alongMi: pass.mile,
        offCourseFeet: feetFromMetres(pass.metres),
      })
    }
  }
  // By mile, then by id, for lib/dayHikeStops.ts's reason: two points the
  // projection lands on one vertex must not swap rows under a finger.
  return found.sort((a, b) => a.alongMi - b.alongMi || (a.poiId < b.poiId ? -1 : 1))
}
