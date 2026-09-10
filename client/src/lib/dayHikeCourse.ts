// The walked line with a mile on every vertex - the spine three surfaces in
// the redesigned builder share (#1194).
//
// WHY THIS EXISTS AT ALL. lib/trailGraph.ts already draws the walk
// (`routeLines`) and already totals it (`GraphRoute.miles`), but nothing
// between those two answers "how far along is THIS point". Three things in
// frame `1j`'s redesign need exactly that and would otherwise each grow their
// own copy of it:
//
//   - a stop's position in the route order (lib/dayHikeStops.ts)
//   - the mile ticks on the map (map/dayHikeLayers.ts)
//   - where a leg starts and ends in the route list (lib/dayHikeRows.ts)
//
// Three copies of "walk the vertices adding haversine" is three chances to
// disagree about how long the walk is, on the one screen whose figures a hiker
// reads before deciding whether they beat the dark.
//
// THE MILE AXIS IS TRAIL MILES, AND GAPS DO NOT ADVANCE IT
//
// A draft is several stretches (#935) with ground between them the app
// declined to route. `DraftStatus.miles` excludes those gaps, and so does
// this: crossing from one stretch to the next carries the cumulative mile
// over unchanged. So the last vertex's `mile` equals `DraftStatus.miles`
// exactly, by construction rather than by both happening to be right.
//
// AND THE CONSTRUCTION IS THE SCALING BELOW, WHICH IT DID NOT USED TO BE.
// This walked the drawn vertices adding haversine metres, and asserted the
// equality above without buying it. The two are different measurements of
// the same ground: `build_trail_graph.py` publishes `length_m` as the line's
// length in EPSG:5070 - an equal-AREA projection - and the vertices in
// WGS84. Measured with pyproj at Harriman's latitude, Albers reads an
// east-west metre 0.8% short and a north-south metre 0.8% long, so the two
// axes cannot agree and did not.
//
// lib/dayHikeFollow.ts had already met this and written the rule down:
// "`length_m` is EPSG:5070 and these vertices are lon/lat, and every other
// mile in this app comes from the former. One axis, so the header and the
// turn list agree." It scales its projection back onto the published metres
// for exactly this reason. This module is that rule applied where it was
// missed.
//
// That is the honest axis and it is worth saying which honesty it buys. "Mile
// 3.4" on this axis means "3.4 miles of maintained trail from the first tap",
// not "3.4 miles of walking" - a hiker crossing a gap walks further than the
// axis says. The alternative was adding a straight-line guess at ground
// nobody has walked for us into the number every other surface prints, which
// is the one thing dayHikeDraft.ts's whole model exists to refuse.
//
// THIS IS NOT A MILE FROM SPRINGER and must never be compared to one.
// features/HIKE_PLANNING.md's Finding 1 is about two mile scales that were
// close enough to be confused; this is a third, deliberately local, and it
// has no meaning outside the walk it was built from. It is zero at the
// hiker's first tap and that is the whole of its definition.

import { straightLineMetres } from './dayHikeShelf'
import {
  bearingDegrees,
  metresToMiles,
  routeLines,
  walkedMetresPerEdge,
  type LonLat,
  type TrailGraph,
} from './trailGraph'
import type { DraftStretch } from './dayHikeDraft'

/** A vertex of the walk, and how far along it sits. */
export interface CoursePoint {
  lon: number
  lat: number
  /** Cumulative trail miles from the walk's first tap. Gaps do not advance it. */
  mile: number
}

export interface DayHikeCourse {
  /**
   * Every vertex of every stretch, in walking order.
   *
   * Stretches are concatenated, which is safe HERE and nowhere else: this
   * array is read for positions along the walk, never handed to a drawing
   * layer. `dayHikeLayers.ts` still draws stretch by stretch, so nothing
   * built from this can put a line across a gap. {@link stretchStarts} is
   * how a reader that does care tells the joins apart.
   */
  points: CoursePoint[]
  /** Index into {@link points} at which each stretch begins. Always starts `[0]`. */
  stretchStarts: number[]
  /** Trail miles over the whole walk - the last point's `mile`. */
  miles: number
}

const EMPTY_COURSE: DayHikeCourse = { points: [], stretchStarts: [], miles: 0 }

/**
 * The walk as a mile-stamped line, or an empty course when it cannot be drawn.
 *
 * REFUSES ON THE SAME TERMS `routeLines` DOES, which is the reason this takes
 * stretches rather than a finished polyline: a stretch whose geometry has not
 * landed on this phone yet returns null there, and a course built from the
 * stretches that DID draw would be a mile axis for a shorter walk than the
 * hiker is looking at. Every consumer here prints numbers next to that walk,
 * so a silently-short axis is worse than no axis - the ticks would still
 * march up the map, just wrong.
 */
export function buildCourse(
  graph: TrailGraph,
  stretches: readonly DraftStretch[],
): DayHikeCourse {
  if (stretches.length === 0) return EMPTY_COURSE

  const points: CoursePoint[] = []
  const stretchStarts: number[] = []
  let mile = 0

  for (const stretch of stretches) {
    const lines = routeLines(graph, stretch.route)
    if (lines === null) return EMPTY_COURSE

    // What the pipeline measured for each edge this stretch walks, in the
    // order `routeLines` drew them. `routeLines` emits one polyline per edge
    // across the route's sections, so these line up positionally - EXCEPT
    // that `routeGeometry` drops an edge whose cut yields fewer than two
    // vertices, which a zero-length traversal does. `scaleFor` below checks
    // the counts rather than trusting them.
    const walkedMetres = stretch.route.sections.flatMap((section) =>
      walkedMetresPerEdge(graph, section.edgeIndices, section.from, section.to),
    )

    stretchStarts.push(points.length)
    // Carried across the join within a stretch too: `routeLines` returns one
    // array per leg, and consecutive legs share their meeting vertex. Adding
    // the first vertex of every leg would put a zero-length step in the axis
    // at each leg join - harmless arithmetically, and a duplicate point that
    // a tick or a stop could land on twice.
    let firstOfStretch = true
    const scale = scaleFor(lines, walkedMetres)
    lines.forEach((line, at) => {
      // Each edge's drawn run stretched onto the metres the pipeline
      // published for it, so the axis lands exactly on the published total at
      // every edge boundary - and therefore at every LEG boundary, which is
      // where lib/dayHikeRows.ts places a stop against a leg. Per edge rather
      // than per stretch because the distortion varies along a walk: measured
      // on a 6.3-mile winding route, scaling the stretch as a whole still
      // left 32 ft of drift at the worst edge boundary, and a shelter sitting
      // AT a junction is exactly 0 ft from one.
      const factor = scale(at)
      for (const [lon, lat] of line) {
        const previous = points[points.length - 1]
        if (previous !== undefined && !firstOfStretch) {
          if (previous.lon === lon && previous.lat === lat) continue
          mile +=
            metresToMiles(
              straightLineMetres({ lon: previous.lon, lat: previous.lat }, { lon, lat }),
            ) * factor
        }
        points.push({ lon, lat, mile })
        firstOfStretch = false
      }
    })
  }

  if (points.length === 0) return EMPTY_COURSE
  return { points, stretchStarts, miles: points[points.length - 1].mile }
}

/**
 * How much to stretch each drawn line so its miles are the published ones.
 *
 * Per line when the drawn lines and the walked edges correspond one to one,
 * which is the ordinary case. When they do not - `routeGeometry` dropped an
 * edge too short to draw - every line gets the stretch's own single factor
 * instead: the total still lands exactly on `route.miles`, and only the
 * placement WITHIN the stretch keeps the drift this function exists to
 * remove. Degrading to the old behaviour's accuracy on a case that used to
 * be wrong everywhere is the right direction to fail in.
 *
 * A factor of 1 wherever there is nothing to scale against - a line with no
 * length, or a published length of zero - because multiplying a real distance
 * by a ratio derived from nothing is how a mile axis acquires a number nobody
 * measured.
 */
function scaleFor(
  lines: ReadonlyArray<ReadonlyArray<readonly [number, number]>>,
  walkedMetres: readonly number[],
): (at: number) => number {
  const drawn = lines.map(drawnMetres)
  const perLine = lines.length === walkedMetres.length

  if (perLine) {
    const factors = drawn.map((metres, at) =>
      metres > 0 && walkedMetres[at] > 0 ? walkedMetres[at] / metres : 1,
    )
    return (at) => factors[at] ?? 1
  }

  const drawnTotal = drawn.reduce((sum, metres) => sum + metres, 0)
  const walkedTotal = walkedMetres.reduce((sum, metres) => sum + metres, 0)
  const whole = drawnTotal > 0 && walkedTotal > 0 ? walkedTotal / drawnTotal : 1
  return () => whole
}

/** A drawn line's own length, by the same measure the axis accumulates. */
function drawnMetres(line: ReadonlyArray<readonly [number, number]>): number {
  let total = 0
  for (let at = 1; at < line.length; at += 1) {
    total += straightLineMetres(
      { lon: line[at - 1][0], lat: line[at - 1][1] },
      { lon: line[at][0], lat: line[at][1] },
    )
  }
  return total
}

/** Where a point sits on the course: its mile, and how far off the line it was. */
export interface CourseProjection {
  mile: number
  /** Straight-line feet from the queried point to the nearest course vertex. */
  offCourseFeet: number
  /** Index of that vertex in {@link DayHikeCourse.points}. */
  pointIndex: number
}

const FEET_PER_METRE = 3.280839895013123

/**
 * The nearest point of the walk to `at`, as a mile along it.
 *
 * VERTEX-NEAREST RATHER THAN SEGMENT-NEAREST, which is a real approximation
 * and is stated rather than hidden. The exact answer projects onto each
 * segment between vertices; this picks the closest vertex. The error is
 * bounded by half the vertex spacing, and `build_trail_graph.py` publishes
 * NYNJTC's own geometry - vertices tens of metres apart, not hundreds - so
 * the mile a stop lands on moves by a few hundredths at worst.
 *
 * What that buys: this runs on every render while a hiker taps, over every
 * shelter and campsite near the walk, on a phone. Segment projection is the
 * same loop with a dot product and a clamp inside it, and nothing on this
 * screen can tell the difference. If a surface ever needs the exact answer -
 * ordering two stops that sit within a vertex spacing of each other on the
 * same trail - this is the function to sharpen, not to work around.
 */
export function projectOnCourse(
  course: DayHikeCourse,
  at: LonLat,
): CourseProjection | null {
  if (course.points.length === 0) return null

  let bestIndex = 0
  let bestMetres = Infinity
  for (let index = 0; index < course.points.length; index += 1) {
    const point = course.points[index]
    const metres = straightLineMetres({ lon: point.lon, lat: point.lat }, at)
    if (metres < bestMetres) {
      bestMetres = metres
      bestIndex = index
    }
  }

  return {
    mile: course.points[bestIndex].mile,
    offCourseFeet: bestMetres * FEET_PER_METRE,
    pointIndex: bestIndex,
  }
}

/** A whole-mile mark on the walk, with the bearing of the trail under it. */
export interface MileTick {
  mile: number
  lon: number
  lat: number
  /** Degrees clockwise from north, along the direction of travel. */
  bearing: number
}

/**
 * A tick at every whole mile of the walk, with the trail's bearing there.
 *
 * WHY THE BEARING IS PART OF THE TICK rather than something the map layer
 * works out: the crossbar is drawn perpendicular to the path, so it needs the
 * path's direction, and the only place that direction is known cheaply is
 * here, where the neighbouring vertices are already in hand. A map layer
 * recovering it from a rendered feature would be reading the answer back out
 * of the picture.
 *
 * NO TICK AT ZERO AND NONE AT THE FINISH. Mile 0 is the first tap, which
 * already wears a numbered mark, and a tick on top of it is two marks saying
 * one thing. The end of the walk is the total the panel prints in 20px type;
 * a "3" tick a hundred feet short of a mark reading 3.4 mi reads as a
 * contradiction rather than a scale.
 */
export function mileTicks(course: DayHikeCourse, everyMiles = 1): MileTick[] {
  if (everyMiles <= 0 || course.points.length < 2) return []

  const ticks: MileTick[] = []
  let next = everyMiles

  for (let index = 1; index < course.points.length; index += 1) {
    const before = course.points[index - 1]
    const point = course.points[index]
    while (next <= point.mile && next < course.miles) {
      // The vertex the mile falls at or just past. Not interpolated onto the
      // exact mile: the tick is a scale mark, and a few metres of placement
      // error on it is invisible where the number beside it is what a hiker
      // reads. Interpolating would be arithmetic nobody could see the result
      // of.
      ticks.push({
        mile: next,
        lon: point.lon,
        lat: point.lat,
        bearing: bearingDegrees(
          { lon: before.lon, lat: before.lat },
          { lon: point.lon, lat: point.lat },
        ),
      })
      next += everyMiles
    }
  }

  return ticks
}
