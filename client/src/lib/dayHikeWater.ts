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
// WHAT IT DOES NOT CLAIM. An empty list means the published waypoints hold
// no water point near this walk, which is not the same as no water: the
// water layer is thin (measured 2026-08 for #529: 97% of shelters have no
// mapped water within 250 m), and a stream the map has no point for is not
// a stream that is not there. So a surface prints the rows it has and
// prints NOTHING - no "no water on this route" - when it has none. Omit
// rather than guess, on the one path that is about running dry.

import { projectOnCourse, type DayHikeCourse } from './dayHikeCourse'
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
 */
export const WATER_SAID_OFF_FEET = 100

export interface RouteWater {
  poiId: string
  name: string
  lat: number
  lon: number
  /**
   * Trail miles from the walk's first tap - a DISTANCE along this walk,
   * never a mile marker on the pipeline's axis, and named so a units
   * formatter may take it (test/unitDisplay.test.ts's rule).
   */
  alongMi: number
  /** Straight-line feet from the point to the nearest vertex of the walk. */
  offCourseFeet: number
}

/** The published water points along `course`, in the order the walk
 *  reaches them. Empty when there are none - and only then; see the header
 *  for what that does and does not mean. */
export function waterOnCourse(
  course: DayHikeCourse,
  pois: readonly StoredPoi[],
  within = WATER_ON_ROUTE_FEET,
): RouteWater[] {
  if (course.points.length === 0) return []
  const found: RouteWater[] = []
  for (const poi of pois) {
    if (poi.type !== 'water') continue
    const at = projectOnCourse(course, { lon: poi.lon, lat: poi.lat })
    if (at === null || at.offCourseFeet > within) continue
    found.push({
      poiId: poi.id,
      name: poi.name,
      lat: poi.lat,
      lon: poi.lon,
      alongMi: at.mile,
      offCourseFeet: at.offCourseFeet,
    })
  }
  // By mile, then by id, for lib/dayHikeStops.ts's reason: two points the
  // projection lands on one vertex must not swap rows under a finger.
  return found.sort((a, b) => a.alongMi - b.alongMi || (a.poiId < b.poiId ? -1 : 1))
}
