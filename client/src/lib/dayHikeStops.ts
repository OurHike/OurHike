// Shelters and campsites a hiker adds to a day hike as stops (#1194).
//
// The design handoff's second functional addition: tapping a shelter or
// campsite marker puts it in the route, in the right place, with its mile.
// Everything here is the arithmetic of that, with no React and no MapLibre in
// it, for lib/dayHikeDraft.ts's reason - these are rules a hiker's plan
// depends on and they should be testable without rendering anything.
//
// A STOP IS NOT A TAP, AND THE DIFFERENCE IS THE WHOLE MODEL
//
// A tap (`GraphPoint`) says "route through here" and changes where the walk
// goes. A stop says "I am stopping at this shelter" and changes NOTHING about
// the route - it is an annotation on a walk that was already decided. Two
// consequences that would be bugs if this were not stated:
//
//   - Adding a stop never re-routes. A hiker who adds Tom Jones Shelter to a
//     walk that passes it gets the same line they had, and one more row.
//   - A stop's ORDER is derived, never stored. It is where the stop falls
//     along the walk, recomputed whenever the walk changes, so a stop cannot
//     end up listed between two legs it does not sit between. The design's
//     `stopIds: string[]` kept insertion order and then sorted for display;
//     keeping only the set is the same thing with one fewer way to be wrong.
//
// WHY A STOP OFF THE LINE IS ACCEPTED RATHER THAN REFUSED
//
// The obvious guard - refuse a stop more than N feet from the walk - would
// refuse most real shelters. CLAUDE.md's own worked example is that 72% of
// A.T. shelters sit past `OFF_TRAIL_THRESHOLD_FT`, and a shelter is off the
// centerline by design: it is up a blue-blazed spur, at the water, out of the
// wind. So a stop carries {@link DayHikeStop.offCourseFeet} and the surfaces
// say when it is a long way off, rather than this module deciding a hiker did
// not mean it.
//
// WHAT IS DELIBERATELY NOT PRICED. The walk to a stop and back. The app knows
// the shelter is 900 ft from the nearest point of the route and knows nothing
// whatever about the ground between - whether there is a spur, how steep it
// is, whether it is passable. Adding 1,800 ft of made-up walking to the
// hiker's time would be exactly the confidently-wrong number FEATURES.md
// warns is more dangerous than an honest unknown. The detour is shown as a
// distance and left as the hiker's to judge.

import { projectOnCourse, type DayHikeCourse } from './dayHikeCourse'
import type { StoredPoi } from './trailData'

/** The waypoint types a day hike may stop at. */
export const STOPPABLE_TYPES: readonly string[] = ['shelter', 'campsite']

export function isStoppable(poi: { type: string }): boolean {
  return STOPPABLE_TYPES.includes(poi.type)
}

/**
 * A stop, resolved against the walk it sits on.
 *
 * `mile` is the local trail-mile axis of lib/dayHikeCourse.ts - zero at the
 * hiker's first tap - and NOT `StoredPoi.mile`, which is NOBO miles from
 * Springer and means nothing on a Harriman loop. The two must never be shown
 * in the same column.
 */
export interface DayHikeStop {
  poiId: string
  type: string
  name: string
  lat: number
  lon: number
  /** Trail miles from the walk's first tap. */
  mile: number
  /** Straight-line feet from the walk to the stop. */
  offCourseFeet: number
  /**
   * How many the shelter sleeps, and how far its water is (#1198).
   *
   * THE TWO FACTS A HIKER PICKS A STOP ON, carried onto the stop so the row
   * can print them. Until #1198 they were on the waypoint card and the card
   * is unreachable while the builder owns the tap - so choosing where to
   * spend the night meant choosing blind, on the one screen built for
   * choosing.
   *
   * OPTIONAL, AND ABSENT MEANS NOBODY PUBLISHED ONE. Both inherit
   * `StoredPoi`'s rule verbatim: `capacity` is absent for the shelters
   * ATC's layer covers in pairs or writes as "xxx", and `waterDistanceFt`
   * is absent where nobody measured - "never 'no water'". A row that
   * rendered a missing capacity as 0, or a missing water distance as "no
   * water nearby", would be the invention FEATURES.md's omit-rather-than-
   * guess rule exists to stop, and it would be inventing it about the two
   * things a hiker is deciding on.
   */
  capacity?: number
  waterDistanceFt?: number
}

/**
 * How far off the walk a stop has to be before a surface says so.
 *
 * @unvalidated. Picked as roughly a fifth of a mile - far enough that a
 * shelter at the end of a normal blue-blazed spur does not trip it, close
 * enough that a hiker who tapped the wrong pin two ridges over is told. It is
 * not derived from anything and nobody has checked it against real spur
 * lengths.
 *
 * What would settle it: the distribution of spur lengths from a trail to its
 * shelter across the parks OurHike holds, which `pipeline/export_spurs.py`
 * already computes for the A.T. and which nobody has run against NYNJTC's
 * network. The number should be a percentile of that, not a round figure.
 */
export const STOP_FAR_OFF_COURSE_FEET = 1000

/**
 * Minutes a stop adds to a walk's estimate.
 *
 * @unvalidated, and inherited rather than derived: the design handoff prices a
 * stop at 15 minutes and says so as a round number. It is the design's guess
 * at how long somebody spends at a shelter, not a measurement of anybody
 * doing it.
 *
 * What would settle it: nothing this repository holds. It is a fact about
 * hikers rather than about ground, and the honest instrument is the hiker's
 * own recorded walks - which lib/pace.ts already collects for walking speed
 * and could collect for time-not-walking the same way.
 *
 * Why it is applied at all, given that: a hiker who plans four shelter stops
 * into a day and is handed a walking time with no stopping in it has been
 * told they finish an hour before they will. Rounding toward the later
 * arrival is the direction CLAUDE.md asks for, and the surfaces print it as
 * its own line rather than folding it into the walking figure, so a hiker can
 * see which part of the estimate is the trail and which is the guess.
 */
export const STOP_MINUTES = 15

/**
 * The chosen stops, in the order the walk reaches them.
 *
 * Stops the walk cannot place - no course yet, because the geometry has not
 * landed or the walk is one tap long - come back as an EMPTY list rather
 * than as unplaced rows. A stop with no mile is a row that cannot say where
 * it goes, and the panel showing "Shelter stop · mile ?" while a hiker is
 * building teaches them the figure is unreliable at the moment they most need
 * to trust it.
 */
export function orderStops(
  course: DayHikeCourse,
  chosen: ReadonlySet<string>,
  pois: readonly StoredPoi[],
): DayHikeStop[] {
  if (chosen.size === 0 || course.points.length === 0) return []

  const stops: DayHikeStop[] = []
  for (const poi of pois) {
    if (!chosen.has(poi.id)) continue
    const found = projectOnCourse(course, { lon: poi.lon, lat: poi.lat })
    if (found === null) continue
    stops.push({
      poiId: poi.id,
      type: poi.type,
      name: poi.name,
      lat: poi.lat,
      lon: poi.lon,
      mile: found.mile,
      offCourseFeet: found.offCourseFeet,
      // Spread rather than assigned, so a POI with no published figure has
      // no key at all rather than one holding `undefined` - the same
      // omit-don't-write shape `StoredPoi` itself uses, and what keeps
      // "nobody published this" distinguishable from "this is zero".
      ...(poi.capacity !== undefined ? { capacity: poi.capacity } : {}),
      ...(poi.waterDistanceFt !== undefined
        ? { waterDistanceFt: poi.waterDistanceFt }
        : {}),
    })
  }

  // By mile, then by id - a stable order for two stops the projection puts at
  // the same vertex, so a re-render cannot swap two rows under a finger.
  return stops.sort((a, b) => a.mile - b.mile || (a.poiId < b.poiId ? -1 : 1))
}

/** Add or remove a stop. The set is the state; the order is derived. */
export function toggleStop(chosen: ReadonlySet<string>, poiId: string): Set<string> {
  const next = new Set(chosen)
  if (!next.delete(poiId)) next.add(poiId)
  return next
}

/**
 * The stopping time a walk carries, in minutes, or null when it has no stops.
 *
 * Null rather than 0 so a caller cannot print "+0 min" for a walk with
 * nothing to stop at - an absent line and a line reading zero say different
 * things, and only one of them is true here.
 */
export function stoppingMinutes(stops: readonly DayHikeStop[]): number | null {
  if (stops.length === 0) return null
  return stops.length * STOP_MINUTES
}
