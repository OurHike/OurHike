// Pricing a day hike in walking time (#1008).
//
// The load-bearing assertions here are the REFUSALS. A day hike is routed
// across the junction graph, and this phone's elevation covers the A.T.
// centerline and nothing else - so the interesting question is not "does it
// add up" but "does it keep quiet when part of the walk has no profile under
// it". Every null below is a walk that would otherwise have printed a time
// short of the truth, which is the direction that gets somebody caught out.
//
// The fixture is an A.T. section, per the way this is meant to be exercised
// until the other layers have profiles: one centerline line running north,
// a graph whose edges lie on it, and a profile climbing over the same miles.

import { describe, expect, it } from 'vitest'
import type { Feature, FeatureCollection } from 'geojson'

import { dayHikeWalkingMinutes, type DayHikeGround } from './dayHikeTime'
import { resolveDayHike } from './dayHikeCard'
import type { DayHike, DayHikeEnd, DayHikeSegment } from './dayHikes'
import type { ElevationProfile } from './elevationProfile'
import { STANDARD_PACE } from './pace'
import { legFigures } from './route'
import { buildGraphIndex, type TrailGraph } from './trailGraph'
import { buildTrailIndex } from './trailPosition'

/** Roughly a mile of latitude. */
const MILE_LAT = 1 / 69.05
const LON = -77

// Four nodes a mile apart up the centerline, and the three edges between
// them. `centerline` is pipeline/build_trail_graph.py's own name for the
// A.T., and the only source this phone holds elevation for.
//
//   0 --- 1 --- 2 --- 3      mile 0, 1, 2, 3 on the client index
const NODES: Array<[number, number]> = [
  [LON, 39],
  [LON, 39 + MILE_LAT],
  [LON, 39 + 2 * MILE_LAT],
  [LON, 39 + 3 * MILE_LAT],
]

function atEdge(from: number, to: number, source = 'centerline') {
  return {
    from,
    to,
    length_m: 1609.344,
    trail_id: 'at:1',
    source,
    name: 'Appalachian Trail',
    blaze_color: 'white',
  }
}

const GRAPH: TrailGraph = {
  nodes: NODES,
  edges: [atEdge(0, 1), atEdge(1, 2), atEdge(2, 3)],
}

/** The same three miles, with a blue-blazed side trail off node 1 that no
 *  profile covers - `side_trails` is in the graph and walkable, and has no
 *  elevation. Its own trail_id, so it is its own leg rather than collapsing
 *  into the centerline run beside it. */
const GRAPH_WITH_SIDE_TRAIL: TrailGraph = {
  nodes: [...NODES, [LON + 0.02, 39 + MILE_LAT]],
  edges: [
    ...GRAPH.edges,
    {
      from: 1,
      to: 4,
      length_m: 1609.344,
      trail_id: 'side:1',
      source: 'side_trails',
      name: 'A blue-blazed way to water',
      blaze_color: 'blue',
    },
  ],
}

function line(coordinates: Array<[number, number]>): Feature {
  return {
    type: 'Feature',
    properties: { source: 'centerline' },
    geometry: { type: 'LineString', coordinates },
  }
}

function collection(features: Feature[]): FeatureCollection {
  return { type: 'FeatureCollection', features }
}

const TRAIL_INDEX = buildTrailIndex(collection([line(NODES)]))

/** 500 ft of climb per mile, sampled every tenth of a mile. Steady on
 *  purpose: the arithmetic below is then checkable by hand rather than by
 *  running the thing under test.
 *
 *  Runs a little PAST the graph's three miles, because `MILE_LAT` is a
 *  rounded degrees-per-mile and the index measures the line at 3.0019 - a
 *  profile stopping at exactly 3.0 would clip the last 0.0019 and make the
 *  hand arithmetic disagree for a reason that has nothing to do with what is
 *  being tested. */
function profile(): ElevationProfile {
  const miles: number[] = []
  const feet: number[] = []
  for (let tenth = 0; tenth <= 32; tenth += 1) {
    miles.push(tenth / 10)
    feet.push(1000 + (tenth / 10) * 500)
  }
  return {
    distanceMi: Float32Array.from(miles),
    elevationFt: Float32Array.from(feet),
  }
}

/** The client index and the pipeline agree here, so the anchors are the
 *  identity - the correction is exercised in lib/route.test.ts, and a
 *  fabricated offset in this file would only obscure the ascent arithmetic.
 *  The one thing worth asserting is that NO anchors means no answer. */
const ANCHORS = [
  { mile: 0, clientMile: 0 },
  { mile: 3, clientMile: 3 },
]

function ground(overrides: Partial<DayHikeGround> = {}): DayHikeGround {
  return {
    profile: profile(),
    trailIndex: TRAIL_INDEX,
    anchors: ANCHORS,
    ...overrides,
  }
}

const end = (lon: number, lat: number): DayHikeEnd => ({ coord: [lon, lat], poiId: null })

function hikeOf(segments: DayHikeSegment[], looped = false): DayHike {
  return {
    id: 'hike-1',
    name: 'Three miles up the A.T.',
    date: null,
    segments,
    figures: { miles: 99, legs: [] },
    looped,
    recorded: 'planned',
  }
}

/** Node 0 to node 3: the whole fixture, walked north. */
const THREE_MILES: DayHikeSegment[] = [[end(LON, 39), end(LON, 39 + 3 * MILE_LAT)]]

describe('dayHikeWalkingMinutes', () => {
  const index = buildGraphIndex(GRAPH)

  it('prices a walk that lies on the centerline', () => {
    const resolved = resolveDayHike(index, hikeOf(THREE_MILES))
    expect(resolved).not.toBeNull()

    const minutes = dayHikeWalkingMinutes(resolved!, index, ground(), STANDARD_PACE)

    // Arithmetic by hand, so this fails on a wrong answer rather than
    // agreeing with whatever the code produces. Per mile of this fixture:
    // 60 / (5/1.609344) = 19.31 min of walking, plus 500 ft = 152.4 m of
    // ascent at 600 m/h = 15.24 min. 34.55 min per mile.
    //
    // Multiplied by the index's OWN measure of the fixture rather than by
    // the 3 the coordinates were laid out to be: `MILE_LAT` is a rounded
    // degrees-per-mile and buildTrailIndex measures the real thing, so the
    // line comes out a few percent short of 3 and a hardcoded 103.66 would
    // be asserting the constant rather than the code.
    const perMile = 60 / (5 / 1.609344) + ((500 * 0.3048) / 600) * 60
    expect(TRAIL_INDEX.totalMiles).toBeCloseTo(3, 0)
    expect(minutes).not.toBeNull()
    expect(minutes!).toBeCloseTo(TRAIL_INDEX.totalMiles * perMile, 1)
  })

  it('loses no climb at the joins between edges', () => {
    // THE DEFECT THIS ARITHMETIC HAD. Priced edge by edge, each window ends
    // at the last profile sample at or before its end mile and the next
    // starts at the first at or after its start - so the climb between those
    // two samples is charged to neither, at every join. Three edges lost 100
    // ft and three minutes against the same three miles taken whole. Short is
    // the direction that gets somebody caught by the dark, and the walk that
    // triggers it is an ordinary one: any hike crossing a junction.
    const whole = legFigures(profile(), 0, TRAIL_INDEX.totalMiles, STANDARD_PACE)
    const acrossThreeEdges = dayHikeWalkingMinutes(
      resolveDayHike(index, hikeOf(THREE_MILES))!,
      index,
      ground(),
      STANDARD_PACE,
    )

    expect(acrossThreeEdges).not.toBeNull()
    expect(acrossThreeEdges!).toBeCloseTo(whole.minutes, 1)
  })

  it('charges the climb: the same miles uphill cost more than downhill', () => {
    // Naismith gives no descent credit and the standard pace charges no
    // descent penalty, so this is the ascent term alone, and it has to land
    // on the uphill direction rather than on both.
    const up = dayHikeWalkingMinutes(
      resolveDayHike(index, hikeOf(THREE_MILES))!,
      index,
      ground(),
      STANDARD_PACE,
    )
    const down = dayHikeWalkingMinutes(
      resolveDayHike(index, hikeOf([[end(LON, 39 + 3 * MILE_LAT), end(LON, 39)]]))!,
      index,
      ground(),
      STANDARD_PACE,
    )

    expect(up).not.toBeNull()
    expect(down).not.toBeNull()
    expect(up!).toBeGreaterThan(down!)
  })

  it('costs an out-and-back exactly the way up plus the way down', () => {
    // The turnaround is where a per-edge sum would go wrong in the other
    // direction: the route's edge list doubles back, so the walk climbs on
    // the way out and descends over the same ground on the way home. Split
    // into monotonic runs, that is the uphill walk plus the downhill one and
    // nothing else - the climb charged once, the six miles charged twice.
    const up = dayHikeWalkingMinutes(
      resolveDayHike(index, hikeOf(THREE_MILES))!,
      index,
      ground(),
      STANDARD_PACE,
    )
    const down = dayHikeWalkingMinutes(
      resolveDayHike(index, hikeOf([[end(LON, 39 + 3 * MILE_LAT), end(LON, 39)]]))!,
      index,
      ground(),
      STANDARD_PACE,
    )
    const outAndBack = dayHikeWalkingMinutes(
      resolveDayHike(
        index,
        hikeOf([[end(LON, 39), end(LON, 39 + 3 * MILE_LAT), end(LON, 39)]]),
      )!,
      index,
      ground(),
      STANDARD_PACE,
    )

    expect(outAndBack).not.toBeNull()
    expect(outAndBack!).toBeCloseTo(up! + down!, 6)
  })

  it('walks a closed loop back to where it started, not to the last tap', () => {
    // `closeTheLoop` routes the last tap back to the FIRST, so a looped
    // walk's final edge ends at points[0] and not at points[n-1]. Taking the
    // closing fraction from the last tap instead prices the way home against
    // the wrong end of the wrong edge - here it drops the whole return, which
    // is the short answer again.
    //
    // Out to node 3 and back down the same trail: the same ground as the
    // explicit out-and-back above, said with the loop flag instead of a
    // third tap, and it has to cost the same.
    const looped = resolveDayHike(
      index,
      hikeOf([[end(LON, 39), end(LON, 39 + 3 * MILE_LAT)]], true),
    )
    expect(looped).not.toBeNull()
    expect(looped!.looped).toBe(true)

    const outAndBack = dayHikeWalkingMinutes(
      resolveDayHike(
        index,
        hikeOf([[end(LON, 39), end(LON, 39 + 3 * MILE_LAT), end(LON, 39)]]),
      )!,
      index,
      ground(),
      STANDARD_PACE,
    )
    const minutes = dayHikeWalkingMinutes(looped!, index, ground(), STANDARD_PACE)

    expect(minutes).not.toBeNull()
    expect(minutes!).toBeCloseTo(outAndBack!, 6)
  })

  it('refuses the whole walk when one edge has no profile under it', () => {
    // THE DEFECT THIS FUNCTION EXISTS TO PREVENT. A side trail is real,
    // walkable ground with no elevation published for it. Pricing it at zero
    // ascent understates the day; pricing the rest and printing the total
    // understates it just as much, with a number attached.
    const sideIndex = buildGraphIndex(GRAPH_WITH_SIDE_TRAIL)
    const ontoTheSideTrail = hikeOf([[end(LON, 39), end(LON + 0.02, 39 + MILE_LAT)]])
    const resolved = resolveDayHike(sideIndex, ontoTheSideTrail)
    expect(resolved).not.toBeNull()
    expect(resolved!.legs.some((leg) => leg.source === 'side_trails')).toBe(true)

    expect(
      dayHikeWalkingMinutes(resolved!, sideIndex, ground(), STANDARD_PACE),
    ).toBeNull()
  })

  it('says nothing on a download with no profile', () => {
    const resolved = resolveDayHike(index, hikeOf(THREE_MILES))
    expect(
      dayHikeWalkingMinutes(resolved!, index, ground({ profile: null }), STANDARD_PACE),
    ).toBeNull()
  })

  it('says nothing without the anchors that carry the two mile axes across', () => {
    // A client-scale mile read against pipeline-scale samples is the mixed
    // measurement lib/route.ts exists to prevent (HIKE_PLANNING.md Finding
    // 1). No correction available means no answer, not an uncorrected one.
    const resolved = resolveDayHike(index, hikeOf(THREE_MILES))
    expect(
      dayHikeWalkingMinutes(resolved!, index, ground({ anchors: [] }), STANDARD_PACE),
    ).toBeNull()
  })

  it('says nothing without the centerline index to place the graph on', () => {
    const resolved = resolveDayHike(index, hikeOf(THREE_MILES))
    expect(
      dayHikeWalkingMinutes(
        resolved!,
        index,
        ground({ trailIndex: null }),
        STANDARD_PACE,
      ),
    ).toBeNull()
  })
})
