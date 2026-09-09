// Tests for lib/dayHikeCourse.ts - the walked line with a mile on every
// vertex (#1194).
//
// Three rules a caller could quietly break, and the reason each is here:
//
//   THE AXIS DOES NOT ADVANCE ACROSS A GAP. `DraftStatus.miles` excludes the
//   ground the app declined to route, and this has to agree with it exactly
//   or the panel's mile column and its distance figure describe different
//   walks.
//
//   AN UNDRAWABLE WALK PRODUCES NO AXIS AT ALL. `routeLines` refuses a walk
//   whose geometry has not landed; a course built from the stretches that DID
//   draw would be a mile axis for a shorter walk than the hiker is looking
//   at, with ticks still marching up the map.
//
//   NO TICK AT ZERO AND NONE AT THE FINISH. Both would be a second mark
//   saying something already said - see the function's own note.

import { describe, expect, it } from 'vitest'

import { buildCourse, mileTicks, projectOnCourse } from './dayHikeCourse'
import { orderStops } from './dayHikeStops'
import { routeRows } from './dayHikeRows'
import type { StoredPoi } from './trailData'
import { draftStatus, tapAt, EMPTY_DRAFT, startStretch } from './dayHikeDraft'
import { buildGraphIndex, type TrailGraph } from './trailGraph'

//   0 --- 836 m --- 1 --- 836 m --- 2      Pine Meadow Trail
//   3 --- 836 m --- 4                      Kakiat Trail, a separate island
const GRAPH: TrailGraph = {
  nodes: [
    [-74.1, 41.25],
    [-74.09, 41.25],
    [-74.08, 41.25],
    [-74.0, 41.3],
    [-73.99, 41.3],
  ],
  edges: [
    {
      from: 0,
      to: 1,
      length_m: 836,
      trail_id: 'oprhp_trails:1',
      source: 'oprhp_trails',
      name: 'Pine Meadow Trail',
      blaze_color: 'blue',
    },
    {
      from: 1,
      to: 2,
      length_m: 836,
      trail_id: 'oprhp_trails:1',
      source: 'oprhp_trails',
      name: 'Pine Meadow Trail',
      blaze_color: 'blue',
    },
    {
      from: 3,
      to: 4,
      length_m: 836,
      trail_id: 'oprhp_trails:9',
      source: 'oprhp_trails',
      name: 'Kakiat Trail',
      blaze_color: 'yellow',
    },
  ],
}

/** Every published graph carries per-edge vertices; a fixture without them is
 *  a phone mid-download. Same helper as dayHikeDraft.test.ts, same reason. */
function published(graph: TrailGraph): TrailGraph {
  return {
    nodes: graph.nodes,
    edges: graph.edges.map((edge) => ({
      ...edge,
      geometry: [graph.nodes[edge.from], graph.nodes[edge.to]],
    })),
  }
}

const PUBLISHED = published(GRAPH)
const index = buildGraphIndex(PUBLISHED)
/** The same graph with no vertices anywhere - a download that has not landed. */
const bareIndex = buildGraphIndex(GRAPH)

const START = { lon: -74.1, lat: 41.25 }
const END = { lon: -74.08, lat: 41.25 }
const ISLAND_START = { lon: -74.0, lat: 41.3 }
const ISLAND_END = { lon: -73.99, lat: 41.3 }

/** A routed two-tap walk down Pine Meadow. */
function pineMeadow() {
  const draft = tapAt(index, tapAt(index, EMPTY_DRAFT, START), END)
  const status = draftStatus(index, draft)
  if (status.kind !== 'routed') throw new Error('fixture should route')
  return status
}

/** Pine Meadow, then a gap, then the Kakiat island. */
function twoStretches() {
  let draft = tapAt(index, tapAt(index, EMPTY_DRAFT, START), END)
  draft = startStretch(draft)
  draft = tapAt(index, tapAt(index, draft, ISLAND_START), ISLAND_END)
  const status = draftStatus(index, draft)
  if (status.kind !== 'routed') throw new Error('fixture should route')
  return status
}

describe('building the course', () => {
  it('stamps a mile on every vertex, starting at zero', () => {
    const course = buildCourse(PUBLISHED, pineMeadow().stretches)

    expect(course.points.length).toBeGreaterThan(1)
    expect(course.points[0].mile).toBe(0)
    for (let at = 1; at < course.points.length; at += 1) {
      expect(course.points[at].mile).toBeGreaterThanOrEqual(course.points[at - 1].mile)
    }
  })

  it('ends at the walk’s own total, so the axis and the figure agree', () => {
    const status = pineMeadow()
    const course = buildCourse(PUBLISHED, status.stretches)

    // EXACT, and it was not. This used to assert `toBeCloseTo(..., 2)` under
    // a comment conceding the point - "the totals come from the graph's
    // published `length_m` and the course re-measures the drawn vertices,
    // which is a haversine over the same ground rather than the same
    // arithmetic" - while the module's own header claimed the two agreed
    // "exactly, by construction". They did not: `length_m` is EPSG:5070, an
    // equal-AREA projection that reads an east-west metre 0.8% short at this
    // latitude, and the vertices are WGS84. The course is now scaled onto the
    // published metres, so the claim is true and this asserts it.
    expect(course.miles).toBeCloseTo(status.miles, 10)
  })

  it('carries the mile across a gap rather than adding it', () => {
    const status = twoStretches()
    const course = buildCourse(PUBLISHED, status.stretches)

    expect(course.stretchStarts).toHaveLength(2)
    const lastOfFirst = course.points[course.stretchStarts[1] - 1]
    const firstOfSecond = course.points[course.stretchStarts[1]]

    // THE WHOLE RULE: the gap between these two points is real ground the
    // hiker crosses and it advances the axis by nothing, because the app has
    // no measurement of it and `DraftStatus.miles` excludes it too.
    expect(firstOfSecond.mile).toBe(lastOfFirst.mile)
    expect(course.miles).toBeCloseTo(status.miles, 2)
  })

  it('refuses entirely when a stretch cannot be drawn', () => {
    // Same taps, a graph with no vertices: `routeLines` returns null, and a
    // course over the stretches that DID draw would be an axis for a
    // different walk.
    const draft = tapAt(bareIndex, tapAt(bareIndex, EMPTY_DRAFT, START), END)
    const status = draftStatus(bareIndex, draft)
    if (status.kind !== 'routed') return

    const course = buildCourse(GRAPH, status.stretches)

    expect(course.points).toEqual([])
    expect(course.miles).toBe(0)
  })

  it('is empty for a walk with no stretches', () => {
    expect(buildCourse(PUBLISHED, []).points).toEqual([])
  })
})

describe('projecting onto the course', () => {
  it('finds the mile of a point beside the walk', () => {
    const course = buildCourse(PUBLISHED, pineMeadow().stretches)
    // Just north of the midpoint of the walk.
    const found = projectOnCourse(course, { lon: -74.09, lat: 41.2505 })

    expect(found).not.toBeNull()
    expect(found?.mile).toBeGreaterThan(0)
    expect(found?.mile).toBeLessThan(course.miles)
    expect(found?.offCourseFeet).toBeGreaterThan(0)
  })

  it('measures how far off the walk a point is', () => {
    const course = buildCourse(PUBLISHED, pineMeadow().stretches)
    const near = projectOnCourse(course, { lon: -74.09, lat: 41.2505 })
    const far = projectOnCourse(course, { lon: -74.09, lat: 41.26 })

    expect(far?.offCourseFeet).toBeGreaterThan(near?.offCourseFeet ?? 0)
  })

  it('answers null for a course with nothing in it', () => {
    expect(projectOnCourse(buildCourse(PUBLISHED, []), START)).toBeNull()
  })
})

describe('mile ticks', () => {
  it('marks each whole mile once, in order', () => {
    const course = buildCourse(PUBLISHED, pineMeadow().stretches)
    const ticks = mileTicks(course)

    expect(ticks.map((tick) => tick.mile)).toEqual(
      ticks.map((_tick, at) => at + 1).slice(0, ticks.length),
    )
  })

  it('never marks mile zero, which already wears the hiker’s own tap', () => {
    const course = buildCourse(PUBLISHED, pineMeadow().stretches)

    expect(mileTicks(course).some((tick) => tick.mile === 0)).toBe(false)
  })

  it('never marks the finish, which the panel prints as the total', () => {
    const course = buildCourse(PUBLISHED, pineMeadow().stretches)

    for (const tick of mileTicks(course)) {
      expect(tick.mile).toBeLessThan(course.miles)
    }
  })

  it('draws nothing on a walk shorter than a mile', () => {
    const course = buildCourse(PUBLISHED, pineMeadow().stretches)
    // The fixture is ~1.04 mi, so a 10-mile spacing has nothing to mark.
    expect(mileTicks(course, 10)).toEqual([])
  })

  it('carries the trail’s bearing, which is what a crossbar would need', () => {
    const course = buildCourse(PUBLISHED, pineMeadow().stretches)
    const ticks = mileTicks(course)

    for (const tick of ticks) {
      expect(Number.isFinite(tick.bearing)).toBe(true)
      // Due east along this fixture's latitude line.
      expect(tick.bearing).toBeGreaterThan(80)
      expect(tick.bearing).toBeLessThan(100)
    }
  })

  it('refuses a spacing of zero rather than looping for ever', () => {
    const course = buildCourse(PUBLISHED, pineMeadow().stretches)

    expect(mileTicks(course, 0)).toEqual([])
  })
})

describe('one axis, so a stop and a leg can be compared (#1194 fallout)', () => {
  // Two DIFFERENTLY NAMED trails meeting at a junction, so `sameTrail` splits
  // the walk into two legs and the junction is a leg boundary. The shared
  // fixture above names both edges Pine Meadow, which is one leg and has no
  // boundary to misplace anything against - which is why nothing caught this.
  const FORK: TrailGraph = {
    nodes: [
      [-74.09, 41.25],
      [-74.078, 41.25],
      [-74.066, 41.25],
    ],
    edges: [
      {
        from: 0,
        to: 1,
        // What build_trail_graph.py publishes: this ground measured in
        // EPSG:5070. At 41.25N Albers reads an east-west metre 0.792% short,
        // so the 1,005.8 m of real trail below publishes as 997.8.
        length_m: 997.8,
        trail_id: 'nynjtc:1',
        source: 'nynjtc',
        name: 'Pine Meadow Trail',
        blaze_color: 'blue',
      },
      {
        from: 1,
        to: 2,
        length_m: 997.8,
        trail_id: 'nynjtc:2',
        source: 'nynjtc',
        name: 'Seven Hills Trail',
        blaze_color: 'white',
      },
    ],
  }
  const forkGraph = published(FORK)
  const forkIndex = buildGraphIndex(forkGraph)

  const shelterAtJunction: StoredPoi = {
    id: 'tom-jones',
    type: 'shelter',
    name: 'Tom Jones Shelter',
    lon: -74.078,
    lat: 41.25,
    confidence: 'high',
  } as unknown as StoredPoi

  function acrossTheFork() {
    const draft = tapAt(
      forkIndex,
      tapAt(forkIndex, EMPTY_DRAFT, { lon: -74.09, lat: 41.25 }),
      { lon: -74.066, lat: 41.25 },
    )
    const status = draftStatus(forkIndex, draft)
    if (status.kind !== 'routed') throw new Error('fixture should route')
    return status
  }

  it('puts a shelter standing AT a junction after the leg that reached it', () => {
    // The defect this pins. A stop's mile came off the course (haversine over
    // the drawn WGS84 vertices) and a leg's came off `length_m` (EPSG:5070),
    // and lib/dayHikeRows.ts compares the two directly - `stops[placed].mile
    // <= mile`. Measured before the fix on this fixture: the shelter sat at
    // course-mile 0.6234 while leg one ended at 0.6200, so the comparison
    // failed at every leg and the last-leg sweep collected it at the END of
    // the walk. The panel then printed "mile 0.6" on a row listed after a leg
    // running 0.6-1.2 - a list contradicting its own numbers.
    const status = acrossTheFork()
    const course = buildCourse(forkGraph, status.stretches)
    const stops = orderStops(course, new Set(['tom-jones']), [shelterAtJunction])
    expect(stops).toHaveLength(1)

    const rows = routeRows(status.legs, stops, status.gaps)
    const shape = rows.map((row) => (row.kind === 'leg' ? row.name : row.kind))
    expect(shape).toEqual(['Pine Meadow Trail', 'stop', 'Seven Hills Trail'])
  })

  it('lands the course exactly on each leg boundary, which is what makes that work', () => {
    const status = acrossTheFork()
    const course = buildCourse(forkGraph, status.stretches)
    const stops = orderStops(course, new Set(['tom-jones']), [shelterAtJunction])

    // The stop is at the junction, so its course mile IS the first leg's end.
    // Equality here is the whole property: any drift at all puts a stop
    // standing on a boundary onto the wrong side of it.
    expect(stops[0].mile).toBeCloseTo(status.legs[0].miles, 10)
    expect(course.miles).toBeCloseTo(status.miles, 10)
  })
})
