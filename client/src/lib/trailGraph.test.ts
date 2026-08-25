// Tests for lib/trailGraph.ts - routing a day hike over the junction graph
// (#975, features/HIKE_PLANNING.md "The day hike on a network").
//
// THE ASYMMETRY THIS SUITE PINS, which is the same one
// pipeline/tests/test_build_trail_graph.py states from the other end.
//
// A refused route is an honest answer a hiker can act on: OurHike could not
// build that walk. An INVENTED one is a path across ground with no trail on
// it, handed to somebody on the screen they use to decide where to go. So
// several tests below assert that a route comes back NULL, and a change that
// makes them pass by returning something is not an improvement.
//
// The other rule under test is #934's, recorded in features/HIKE_PLANNING.md:
// a tap SPLITS the segment. The route runs exactly between the two tapped
// points, and never quietly starts at the nearest junction instead.

import { describe, expect, it } from 'vitest'

import {
  buildGraphIndex,
  closeTheLoop,
  legsFromEdges,
  MAX_OFF_NETWORK_FEET,
  metresToMiles,
  nearestPointOnGraph,
  routeBetween,
  routeGeometry,
  routeThrough,
  type TrailGraph,
} from './trailGraph'

// Harriman-ish. At 41.25 N, 0.01 deg of longitude is about 836 m and 0.01 deg
// of latitude about 1,112 m; the edge lengths below say so explicitly, because
// build_trail_graph.py measures them rather than the client re-deriving them.
//
//   3 (-74.09, 41.26)          Seven Hills Trail, NYNJTC, white
//   |
//   |  e2 (1112 m)
//   |
//   0 --- e0 (836 m) --- 1 --- e1 (836 m) --- 2      Pine Meadow Trail, OPRHP, blue
//
//   4 --- e3 (836 m) --- 5    Kakiat Trail, a separate island
const GRAPH: TrailGraph = {
  nodes: [
    [-74.1, 41.25],
    [-74.09, 41.25],
    [-74.08, 41.25],
    [-74.09, 41.26],
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
      from: 1,
      to: 3,
      length_m: 1112,
      trail_id: 'nynjtc_long_path:2',
      source: 'nynjtc_long_path',
      name: 'Seven Hills Trail',
      blaze_color: 'white',
    },
    {
      from: 4,
      to: 5,
      length_m: 836,
      trail_id: 'oprhp_trails:9',
      source: 'oprhp_trails',
      name: 'Kakiat Trail',
      blaze_color: 'yellow',
    },
  ],
}

const index = buildGraphIndex(GRAPH)

/** A point on an edge at a known fraction, without going through a tap. */
function pointOn(edgeIndex: number, fraction: number) {
  const edge = GRAPH.edges[edgeIndex]
  const [fromLon, fromLat] = GRAPH.nodes[edge.from]
  const [toLon, toLat] = GRAPH.nodes[edge.to]
  return {
    edgeIndex,
    fraction,
    at: {
      lon: fromLon + (toLon - fromLon) * fraction,
      lat: fromLat + (toLat - fromLat) * fraction,
    },
    offNetworkFeet: 0,
  }
}

describe('finding the tap', () => {
  it('lands mid-edge rather than on the nearest junction', () => {
    // Halfway along Pine Meadow's first edge. Node 1 is 418 m away and the
    // point must not become it - that is #934's decision, and #771 measured
    // why it matters: a junction every 1.2 trail-miles in this park.
    const found = nearestPointOnGraph(index, { lon: -74.095, lat: 41.25 })

    expect(found).not.toBeNull()
    expect(found?.edgeIndex).toBe(0)
    expect(found?.fraction).toBeCloseTo(0.5, 2)
    expect(found?.offNetworkFeet).toBeLessThan(1)
  })

  it('refuses a tap that is not on a marked hiking route', () => {
    // Roughly 5.5 km north of anything. Frame 1j's refusal, and the whole
    // reason this function returns null rather than a best guess.
    expect(nearestPointOnGraph(index, { lon: -74.095, lat: 41.3 })).toBeNull()
  })

  it('refuses a tap just outside the tolerance and accepts one just inside', () => {
    // The offsets are DERIVED from MAX_OFF_NETWORK_FEET rather than restated
    // as coordinates, so retuning the @unvalidated constant retunes this test
    // instead of silently detaching it from the boundary it names.
    const degreesPerFoot = 1 / (111_320 * 3.280839895)
    const inside = {
      lon: -74.095,
      lat: 41.25 + MAX_OFF_NETWORK_FEET * 0.5 * degreesPerFoot,
    }
    const outside = {
      lon: -74.095,
      lat: 41.25 + MAX_OFF_NETWORK_FEET * 1.5 * degreesPerFoot,
    }
    expect(nearestPointOnGraph(index, inside)).not.toBeNull()
    expect(nearestPointOnGraph(index, outside)).toBeNull()
  })

  it('takes the nearer of two trails and reports how far off the tap was', () => {
    // Near node 1, where Pine Meadow and Seven Hills meet. Whichever it picks,
    // it must say how far the tap was so the caller can refuse on it.
    const found = nearestPointOnGraph(index, { lon: -74.0901, lat: 41.2505 })

    expect(found).not.toBeNull()
    expect(found?.offNetworkFeet).toBeGreaterThan(0)
    expect(found?.offNetworkFeet).toBeLessThanOrEqual(MAX_OFF_NETWORK_FEET)
  })

  it('honours a caller that wants a tighter tolerance than the default', () => {
    const degreesPerFoot = 1 / (111_320 * 3.280839895)
    const at = { lon: -74.095, lat: 41.25 + MAX_OFF_NETWORK_FEET * 0.5 * degreesPerFoot }
    expect(nearestPointOnGraph(index, at)).not.toBeNull()
    expect(nearestPointOnGraph(index, at, MAX_OFF_NETWORK_FEET * 0.1)).toBeNull()
  })
})

describe('routing between two taps', () => {
  it('runs exactly between the tapped points, not junction to junction', () => {
    // Halfway along e0 to halfway along e1: 418 m + 418 m. If either end had
    // snapped to node 1 the answer would be 418, and if both had it would be 0.
    const route = routeBetween(index, pointOn(0, 0.5), pointOn(1, 0.5))

    expect(route).not.toBeNull()
    expect(route?.miles).toBeCloseTo(metresToMiles(836), 4)
  })

  it('handles both taps on one edge without searching at all', () => {
    const route = routeBetween(index, pointOn(0, 0.25), pointOn(0, 0.75))

    expect(route?.miles).toBeCloseTo(metresToMiles(418), 4)
    expect(route?.edgeIndices).toEqual([0])
  })

  it('takes the shorter way round when the graph offers two', () => {
    // From mid-e0 to node 3's end of Seven Hills: through node 1 is
    // 418 + 1112. Nothing else is shorter, and the total pins that it did not
    // wander down e1 and back.
    const route = routeBetween(index, pointOn(0, 0.5), pointOn(2, 1))

    expect(route?.miles).toBeCloseTo(metresToMiles(418 + 1112), 4)
  })

  it('returns null rather than a straight line when nothing connects', () => {
    // The Kakiat island. A route the network cannot carry is said, never
    // drawn - this is the assertion the module exists to keep true.
    expect(routeBetween(index, pointOn(0, 0.5), pointOn(3, 0.5))).toBeNull()
  })
})

describe('legs, which is what the hiker reads', () => {
  it('collapses consecutive edges of one trail into a single leg', () => {
    const legs = legsFromEdges(GRAPH, [0, 1])

    expect(legs).toHaveLength(1)
    expect(legs[0].name).toBe('Pine Meadow Trail')
    expect(legs[0].miles).toBeCloseTo(metresToMiles(1672), 4)
  })

  it('starts a new leg when the trail changes', () => {
    const legs = legsFromEdges(GRAPH, [0, 2])

    expect(legs.map((leg) => leg.name)).toEqual([
      'Pine Meadow Trail',
      'Seven Hills Trail',
    ])
    expect(legs.map((leg) => leg.blaze_color)).toEqual(['blue', 'white'])
  })

  it('carries each leg its own organization, for frame 1j to tally live', () => {
    const route = routeBetween(index, pointOn(0, 0), pointOn(2, 1))

    expect(route?.legsBySource).toEqual([
      { source: 'oprhp_trails', legs: 1 },
      { source: 'nynjtc_long_path', legs: 1 },
    ])
  })
})

describe('walking through several taps', () => {
  it('routes each pair in order and sums them', () => {
    const route = routeThrough(index, [pointOn(0, 0), pointOn(1, 1), pointOn(2, 1)])

    expect(route).not.toBeNull()
    // 0 -> 2 is 1,672 m; back to node 1 and up Seven Hills is 836 + 1,112.
    expect(route?.miles).toBeCloseTo(metresToMiles(1672 + 836 + 1112), 4)
  })

  it('refuses the whole walk when one leg of it cannot be routed', () => {
    // Four routable legs and one that is not is not four-fifths of an answer.
    expect(
      routeThrough(index, [pointOn(0, 0), pointOn(1, 1), pointOn(3, 0.5)]),
    ).toBeNull()
  })

  it('needs at least two points to be a walk', () => {
    expect(routeThrough(index, [pointOn(0, 0.5)])).toBeNull()
    expect(routeThrough(index, [])).toBeNull()
  })
})

describe('close the loop', () => {
  it('walks back to the first tap', () => {
    // Out along Pine Meadow and back: twice 836 m.
    const loop = closeTheLoop(index, [pointOn(0, 0), pointOn(1, 1)])

    expect(loop).not.toBeNull()
    expect(loop?.miles).toBeCloseTo(metresToMiles(1672 * 2), 4)
  })

  it('returns null when there is no way back the network can carry', () => {
    expect(closeTheLoop(index, [pointOn(0, 0.5), pointOn(3, 0.5)])).toBeNull()
  })

  it('needs somewhere to come back from', () => {
    expect(closeTheLoop(index, [pointOn(0, 0.5)])).toBeNull()
  })
})

describe('the graph index', () => {
  it('survives an artifact whose edge names a node that is not there', () => {
    // Not hypothetical enough to ignore: the graph is generated, and a
    // truncated artifact should leave the app drawing no routes rather than
    // throwing on the first tap.
    const broken: TrailGraph = {
      nodes: [[-74.1, 41.25]],
      edges: [{ ...GRAPH.edges[0], from: 0, to: 7 }],
    }

    expect(() => buildGraphIndex(broken)).not.toThrow()
  })

  it('is empty for an empty graph, and routes nothing', () => {
    const empty = buildGraphIndex({ nodes: [], edges: [] })

    expect(nearestPointOnGraph(empty, { lon: -74.1, lat: 41.25 })).toBeNull()
  })
})

describe('routeGeometry, which is what the casing draws', () => {
  // The same graph, but with real polylines: e0 bends north mid-way.
  const DRAWN: TrailGraph = {
    nodes: GRAPH.nodes,
    edges: [
      {
        ...GRAPH.edges[0],
        geometry: [
          [-74.1, 41.25],
          [-74.095, 41.254],
          [-74.09, 41.25],
        ],
      },
      {
        ...GRAPH.edges[1],
        geometry: [
          [-74.09, 41.25],
          [-74.08, 41.25],
        ],
      },
      {
        ...GRAPH.edges[2],
        geometry: [
          [-74.09, 41.25],
          [-74.09, 41.26],
        ],
      },
      { ...GRAPH.edges[3] },
    ],
  }

  it('keeps the bend rather than drawing the chord', () => {
    const lines = routeGeometry(DRAWN, [0])

    expect(lines).not.toBeNull()
    expect(lines?.[0]).toHaveLength(3)
    expect(lines?.[0][1]).toEqual([-74.095, 41.254])
  })

  it('reverses an edge walked against its published direction', () => {
    // e1 then e0: entering e0 at node 1, which is its `to`, so its
    // vertices must come back reversed - two legs meeting head to head is
    // the case a naive concatenation gets wrong invisibly.
    const lines = routeGeometry(DRAWN, [1, 0])

    expect(lines).not.toBeNull()
    expect(lines?.[1][0]).toEqual([-74.09, 41.25])
    expect(lines?.[1][2]).toEqual([-74.1, 41.25])
  })

  it('trims the first and last edges to the tapped fractions', () => {
    const start = {
      edgeIndex: 0,
      fraction: 0.5,
      at: { lon: 0, lat: 0 },
      offNetworkFeet: 0,
    }
    const end = { edgeIndex: 1, fraction: 0.5, at: { lon: 0, lat: 0 }, offNetworkFeet: 0 }

    const lines = routeGeometry(DRAWN, [0, 1], start, end)

    expect(lines).not.toBeNull()
    // The first line begins mid-edge, not at node 0.
    expect(lines?.[0][0][0]).toBeGreaterThan(-74.1)
    // The last line ends mid-edge, not at node 2.
    const lastLine = lines?.[lines.length - 1]
    expect(lastLine?.[lastLine.length - 1][0]).toBeLessThan(-74.08)
  })

  it('slices a single-edge route between the two taps, either way round', () => {
    const nearFrom = {
      edgeIndex: 1,
      fraction: 0.25,
      at: { lon: 0, lat: 0 },
      offNetworkFeet: 0,
    }
    const nearTo = {
      edgeIndex: 1,
      fraction: 0.75,
      at: { lon: 0, lat: 0 },
      offNetworkFeet: 0,
    }

    const forward = routeGeometry(DRAWN, [1], nearFrom, nearTo)
    const backward = routeGeometry(DRAWN, [1], nearTo, nearFrom)

    expect(forward).not.toBeNull()
    expect(backward).not.toBeNull()
    const span = (lines: Array<Array<[number, number]>>) =>
      Math.abs(lines[0][lines[0].length - 1][0] - lines[0][0][0])
    // Both cover the same half of the 0.01-degree edge.
    expect(span(forward!)).toBeCloseTo(0.005, 5)
    expect(span(backward!)).toBeCloseTo(0.005, 5)
  })

  it('refuses to draw chords when an edge has no geometry', () => {
    // GRAPH's edges carry no geometry at all - an older artifact. No drawing
    // beats drawing a straight line across a switchback.
    expect(routeGeometry(GRAPH, [0, 1])).toBeNull()
  })
})

describe('projection onto a bent edge', () => {
  it('measures a tap against the trail, not the chord between junctions', () => {
    const bent = buildGraphIndex({
      nodes: [
        [-74.1, 41.25],
        [-74.09, 41.25],
      ],
      edges: [
        {
          from: 0,
          to: 1,
          length_m: 1200,
          trail_id: 'oprhp_trails:1',
          source: 'oprhp_trails',
          name: 'Pine Meadow Trail',
          blaze_color: 'blue',
          geometry: [
            [-74.1, 41.25],
            [-74.095, 41.254],
            [-74.09, 41.25],
          ],
        },
      ],
    })

    // On the bend's apex - roughly 445 m from the chord, well past the 150 ft
    // tolerance, and ON the trail. The chord fallback would refuse it.
    const found = nearestPointOnGraph(bent, { lon: -74.095, lat: 41.254 })

    expect(found).not.toBeNull()
    expect(found?.offNetworkFeet).toBeLessThan(5)
    expect(found?.fraction).toBeCloseTo(0.5, 1)
  })
})
