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

    // Not exact equality: the totals come from the graph's published
    // `length_m` and the course re-measures the drawn vertices, which is a
    // haversine over the same ground rather than the same arithmetic. Close
    // is the claim - a hundredth of a mile is 50 ft.
    expect(course.miles).toBeCloseTo(status.miles, 2)
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
