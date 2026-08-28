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
  DRAWN_SNAP_METRES,
  canSnapToGraph,
  closeTheLoop,
  holdDesignation,
  legsFromEdges,
  MAX_OFF_NETWORK_FEET,
  metresToMiles,
  nearestPointOnGraph,
  routeBetween,
  routeGeometry,
  routeLines,
  routeThrough,
  SAME_TREAD_METRES,
  sameTrail,
  sameTread,
  trailChoice,
  trailsNear,
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

/**
 * The fixture with each edge's vertex list filled in, which is what every
 * published graph actually carries (`build_trail_graph.py` writes one per
 * edge, always). Every trail here is straight, so an edge's vertices are its
 * two nodes and no assertion below moves.
 *
 * Not cosmetic: since #1093 `nearestPointOnGraph` will not snap a tap to an
 * edge with no vertices, because the only line such an edge offers is the
 * chord between its junctions and the map is drawing the published one. A
 * fixture without geometry is a phone mid-download, not a network.
 */
function published(graph: TrailGraph): TrailGraph {
  return {
    nodes: graph.nodes,
    edges: graph.edges.map((edge) => ({
      ...edge,
      geometry: [graph.nodes[edge.from], graph.nodes[edge.to]],
    })),
  }
}

const index = buildGraphIndex(published(GRAPH))

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

  it('prices a routed leg at the metres walked, never the edges billed whole (#1002)', () => {
    // Halfway along e0 to halfway along e1: 836 m of trail, which once wore a
    // 1,672 m leg - the finished-hike card printed 0.5 mi beside a 1.0 mi leg
    // for the same walk.
    const route = routeBetween(index, pointOn(0, 0.5), pointOn(1, 0.5))

    expect(route?.legs).toHaveLength(1)
    expect(route?.legs[0].miles).toBeCloseTo(route!.miles, 4)
  })

  it('counts re-walked ground in the leg, which a deduplicated edge list cannot (#1002)', () => {
    // Mid-e0, up Seven Hills, back down to mid-e1: both Seven Hills spans are
    // real distance while the drawn edge list holds edge 2 once. The legs sum
    // to the route, and the Seven Hills leg carries both passes.
    const route = routeThrough(index, [pointOn(0, 0.5), pointOn(2, 0.5), pointOn(1, 0.5)])

    expect(route).not.toBeNull()
    const legMiles = route!.legs.reduce((sum, leg) => sum + leg.miles, 0)
    expect(legMiles).toBeCloseTo(route!.miles, 4)
    const sevenHills = route!.legs.find((leg) => leg.name === 'Seven Hills Trail')
    expect(sevenHills?.miles).toBeCloseTo(metresToMiles(1112), 4)
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

  it('has no search grid before geometry arrives, and one after (#1020)', () => {
    // Not a degraded state either way: an edge with no vertices is not a snap
    // candidate at all, so a graph with no geometry has nothing to index.
    expect(buildGraphIndex(GRAPH).grid).toBeNull()
    expect(buildGraphIndex(published(GRAPH)).grid).not.toBeNull()
  })

  it('answers a tap identically with the grid and without it (#1020)', () => {
    // The grid is an optimisation and must not be a behaviour change. Same
    // graph, same taps, one index carrying the grid and one with it removed
    // so the fallback scan runs.
    const withGrid = buildGraphIndex(published(GRAPH))
    const withoutGrid = { ...withGrid, grid: null }

    const taps = [
      { lon: -74.095, lat: 41.25 }, // mid Pine Meadow
      { lon: -74.09, lat: 41.2555 }, // near the Seven Hills junction
      { lon: -74.0, lat: 41.3 }, // the Kakiat island
      { lon: -74.05, lat: 41.28 }, // off everything
      { lon: -74.1, lat: 41.25 }, // exactly on node 0
    ]

    for (const tap of taps) {
      expect(nearestPointOnGraph(withGrid, tap)).toEqual(
        nearestPointOnGraph(withoutGrid, tap),
      )
    }
  })

  it('keeps a tap out of a grid cell it only nearly reaches (#1020)', () => {
    // The cell is 0.05 deg, so a tap can sit in a cell holding no edge while
    // the nearest edge is one cell over and well inside the tolerance. If the
    // query read only its own cell this would refuse a tap that is 20 ft from
    // a trail.
    const grid = buildGraphIndex(published(GRAPH))
    // 0.0001 deg north of Pine Meadow is about 11 m - inside the 150 ft
    // tolerance - and Math.floor puts it in the same cell here; the margin
    // sweep is what the assertion below actually exercises at a cell edge.
    const justOff = nearestPointOnGraph(grid, { lon: -74.0999, lat: 41.2501 })

    expect(justOff).not.toBeNull()
    expect(justOff?.edgeIndex).toBe(0)
  })
})

describe('which of two equal routes comes back (#1020)', () => {
  // A diamond: two ways from node 0 to node 3, the same length either way.
  //
  //        1
  //      /   \        both arms 836 m + 1112 m
  //     0     3
  //      \   /
  //        2
  //
  // The scan this replaced took whichever node had been discovered first,
  // which depended on adjacency order, which depends on the edge numbering
  // that build_trail_graph.py rewrites on every publish. That was never a
  // stable answer. The heap orders ties by node id, which is stable for as
  // long as one artifact is - and this test exists so that a future change
  // to the tie-break is a decision somebody takes rather than a diff nobody
  // notices.
  const DIAMOND: TrailGraph = {
    nodes: [
      [-74.1, 41.25],
      [-74.09, 41.26],
      [-74.09, 41.24],
      [-74.08, 41.25],
    ],
    edges: [
      { ...GRAPH.edges[0], from: 0, to: 1, length_m: 1000, name: 'North arm' },
      { ...GRAPH.edges[0], from: 1, to: 3, length_m: 1000, name: 'North arm' },
      { ...GRAPH.edges[0], from: 0, to: 2, length_m: 1000, name: 'South arm' },
      { ...GRAPH.edges[0], from: 2, to: 3, length_m: 1000, name: 'South arm' },
    ],
  }

  it('is the same route every time, and it is the lower-numbered node', () => {
    const diamond = buildGraphIndex(published(DIAMOND))
    const start = {
      edgeIndex: 0,
      fraction: 0,
      at: { lon: -74.1, lat: 41.25 },
      offNetworkFeet: 0,
    }
    const end = {
      edgeIndex: 3,
      fraction: 1,
      at: { lon: -74.08, lat: 41.25 },
      offNetworkFeet: 0,
    }

    const first = routeBetween(diamond, start, end)
    const again = routeBetween(diamond, start, end)

    expect(first).not.toBeNull()
    expect(first?.legs.map((leg) => leg.name)).toEqual(again?.legs.map((leg) => leg.name))
    // Node 1 is the north arm and sorts before node 2.
    expect(first?.legs.map((leg) => leg.name)).toContain('North arm')
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

  it('draws an out-and-back over one edge rather than nothing (#1040)', () => {
    // The defect: `route.edgeIndices` is deduplicated across leg joins, so
    // walking out and back over one edge collapses to `[1]` - and the caller
    // then handed routeGeometry the FIRST and LAST tap, which for a walk
    // returning to its start are the same point. The edge got trimmed to a
    // zero-length span and the whole drawing came back null, under a bar
    // reading "1 leg · 0.6 mi · ≈12m walking".
    const index = buildGraphIndex(DRAWN)
    const out = nearestPointOnGraph(index, { lon: -74.088, lat: 41.25 })
    const turn = nearestPointOnGraph(index, { lon: -74.082, lat: 41.25 })
    expect(out).not.toBeNull()
    expect(turn).not.toBeNull()

    const route = routeThrough(index, [out!, turn!, out!])
    expect(route).not.toBeNull()
    // The route itself was always right - it counts both directions.
    expect(route!.edgeIndices).toEqual([1])
    expect(route!.miles).toBeCloseTo(0.623, 2)

    const naive = routeGeometry(index.graph, route!.edgeIndices, out!, out!)
    expect(naive).toBeNull()

    const lines = routeLines(index.graph, route!)
    expect(lines).not.toBeNull()
    // One line per leg: out, and back over the same ground.
    expect(lines).toHaveLength(2)
    const span = (line: Array<[number, number]>) =>
      Math.abs(line[line.length - 1][0] - line[0][0])
    expect(span(lines![0])).toBeCloseTo(0.006, 5)
    expect(span(lines![1])).toBeCloseTo(0.006, 5)
    // And drawn in opposite directions, which is what walking back is.
    expect(lines![0][0]).toEqual(lines![1][lines![1].length - 1])
  })

  it('draws the ground walked twice, not just the span between the taps', () => {
    // Out to 0.8, turn, stop at 0.5. The stretch from 0.5 to 0.8 is walked
    // twice and was drawn zero times: the old call trimmed the deduplicated
    // edge to the span between the first and last tap.
    const index = buildGraphIndex(DRAWN)
    const start = nearestPointOnGraph(index, { lon: -74.088, lat: 41.25 })
    const turn = nearestPointOnGraph(index, { lon: -74.082, lat: 41.25 })
    const stop = nearestPointOnGraph(index, { lon: -74.085, lat: 41.25 })

    const route = routeThrough(index, [start!, turn!, stop!])
    expect(route).not.toBeNull()

    const lines = routeLines(index.graph, route!)
    expect(lines).toHaveLength(2)
    // The far leg reaches the turnaround, which the single-call drawing
    // never did. East is the larger longitude here, and the turnaround is
    // the eastmost point of the walk.
    const reached = Math.max(...lines!.flat().map(([lon]) => lon))
    expect(reached).toBeCloseTo(-74.082, 3)
    // The old call stopped at the last tap instead.
    const naive = routeGeometry(index.graph, route!.edgeIndices, start!, stop!)
    expect(Math.max(...naive!.flat().map(([lon]) => lon))).toBeCloseTo(-74.085, 3)
  })

  it('refuses the whole drawing when one leg cannot be drawn', () => {
    // The same asymmetry routeGeometry states per edge, one level up: four
    // legs of a five-leg walk is a picture that lies about the fifth.
    const index = buildGraphIndex(DRAWN)
    const a = nearestPointOnGraph(index, { lon: -74.088, lat: 41.25 })
    const b = nearestPointOnGraph(index, { lon: -74.082, lat: 41.25 })
    const route = routeThrough(index, [a!, b!])
    expect(route).not.toBeNull()

    // Strip the geometry from the one edge the route uses.
    const stripped = {
      ...index.graph,
      edges: index.graph.edges.map((edge, at) =>
        at === route!.edgeIndices[0] ? { ...edge, geometry: undefined } : edge,
      ),
    }
    expect(routeLines(stripped, route!)).toBeNull()
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

// #1093. The state above with its vertices taken away, which is not an old
// artifact - it is every phone between the day-hike door opening and
// `trail_graph_geometry.json` landing, and every phone whose fetch of it
// never resolves.
describe('a graph that has arrived without its lines', () => {
  //         2 ------------- 3      Kakiat Trail, straight, 22 m north of the
  //                                bend's apex
  //             (apex)
  //            /       \            Pine Meadow Trail, bowing 445 m north of
  //   0 - - - - chord - - - 1       the chord between its own two junctions
  const NETWORK: TrailGraph = {
    nodes: [
      [-74.1, 41.25],
      [-74.09, 41.25],
      [-74.1, 41.2542],
      [-74.09, 41.2542],
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
      {
        from: 2,
        to: 3,
        length_m: 836,
        trail_id: 'nynjtc_long_path:9',
        source: 'nynjtc_long_path',
        name: 'Kakiat Trail',
        blaze_color: 'yellow',
        geometry: [
          [-74.1, 41.2542],
          [-74.09, 41.2542],
        ],
      },
    ],
  }
  const bare: TrailGraph = {
    nodes: NETWORK.nodes,
    edges: NETWORK.edges.map(({ geometry: _geometry, ...edge }) => edge),
  }

  /** The apex of Pine Meadow's bend - dead on the line the map is drawing. */
  const ON_THE_BEND = { lon: -74.095, lat: 41.254 }

  it('says so, rather than answering', () => {
    expect(canSnapToGraph(buildGraphIndex(bare))).toBe(false)
    expect(canSnapToGraph(buildGraphIndex(NETWORK))).toBe(true)
  })

  it('refuses a tap it cannot place instead of placing it on the wrong trail', () => {
    // WITH the lines, the tap is where the finger was: on Pine Meadow, at no
    // measurable distance off it.
    const placed = nearestPointOnGraph(buildGraphIndex(NETWORK), ON_THE_BEND)
    expect(placed?.edgeIndex).toBe(0)
    expect(placed?.offNetworkFeet).toBeLessThan(5)

    // WITHOUT them, Pine Meadow offers only the chord between its junctions,
    // 445 m south of the finger - and Kakiat's chord runs 22 m north of it.
    // The nearest chord is therefore a DIFFERENT TRAIL, inside the tolerance,
    // and the old code returned it with no sign that anything had happened:
    // a walk starting on a trail the hiker never touched. Measured across
    // Harriman that was 7% of on-trail taps, against 20% refused outright.
    expect(nearestPointOnGraph(buildGraphIndex(bare), ON_THE_BEND)).toBeNull()
  })

  it('refuses even a tap on a junction node, which it could have answered', () => {
    // Node 0 is a published coordinate and its fraction would be 0 either
    // way, so this one case a chord could have got right. Refused anyway:
    // the rule is about what the graph can be trusted to say, not about the
    // handful of points where a wrong answer happens to coincide with a
    // right one, and a tolerance that admits nodes admits everything within
    // 150 ft of one.
    expect(
      nearestPointOnGraph(buildGraphIndex(bare), { lon: -74.1, lat: 41.25 }),
    ).toBeNull()
  })
})

// Climb over a walk (#1011). The graph above carries no `climb`, which is the
// state of a phone that has not fetched the elevation artifact - so these
// build their own graph with it attached rather than mutating the shared one.
describe('pricing the climb of a walk', () => {
  /** GRAPH with a climb on every edge, or on the ones named. */
  function withClimb(climbs: Record<number, [number, number] | null>): TrailGraph {
    return {
      nodes: GRAPH.nodes,
      edges: GRAPH.edges.map((edge, at) => ({ ...edge, climb: climbs[at] })),
    }
  }

  it('is null when this phone has fetched no elevation at all', () => {
    // The shared GRAPH's edges have no `climb` key. Undefined, not null: the
    // artifact was never fetched, rather than fetched and empty.
    const route = routeBetween(index, pointOn(0, 0), pointOn(1, 1))
    expect(route?.climb).toBeNull()
  })

  it('adds every whole edge it walks', () => {
    const graph = withClimb({ 0: [100, 20], 1: [50, 10] })
    const priced = buildGraphIndex(graph)
    const route = routeBetween(priced, pointOn(0, 0), pointOn(1, 1))
    expect(route?.climb).toEqual({ gainFt: 150, lossFt: 30 })
  })

  it('pro-rates a partial edge by the share actually walked', () => {
    // Half of edge 0 is walked, so half its climb is counted - the same share
    // walkedMetresPerEdge gives the miles, so the two cannot disagree about
    // how much of the edge the hiker covered.
    const priced = buildGraphIndex(withClimb({ 0: [100, 20] }))
    const route = routeBetween(priced, pointOn(0, 0), pointOn(0, 0.5))
    expect(route?.climb).toEqual({ gainFt: 50, lossFt: 10 })
  })

  it('refuses the whole walk when one edge of it was never measured', () => {
    // The rule this artifact exists to make possible: a total missing one
    // edge reads as the climb of the whole walk and is silently low, on the
    // figure a hiker uses to judge whether they beat the dark.
    const priced = buildGraphIndex(withClimb({ 0: [100, 20], 1: null }))
    const route = routeBetween(priced, pointOn(0, 0), pointOn(1, 1))
    expect(route?.miles).toBeGreaterThan(0)
    expect(route?.climb).toBeNull()
  })

  it('counts a re-walked stretch once per pass, in the direction of each pass', () => {
    // The out-and-back half of #1002, applied to climb: walking edge 0 out
    // and back is two passes of real ground - and the second pass climbs
    // what the first descended, which is the half #1034 was about. This
    // asserted `{ gainFt: 200, lossFt: 40 }` until then: two passes counted
    // in the same direction, describing a walk that ends 200 ft above the
    // trailhead it returns to.
    const priced = buildGraphIndex(withClimb({ 0: [100, 20], 1: [50, 10] }))
    const there = routeBetween(priced, pointOn(0, 0), pointOn(0, 1))
    const andBack = routeThrough(priced, [pointOn(0, 0), pointOn(0, 1), pointOn(0, 0)])

    expect(there?.climb).toEqual({ gainFt: 100, lossFt: 20 })
    // Both passes of real ground: 100 + 20 up, 20 + 100 down.
    expect(andBack?.climb).toEqual({ gainFt: 120, lossFt: 120 })
  })

  it('a walk that ends where it started gains exactly what it loses', () => {
    // The invariant worth pinning rather than a pair of literals: it is
    // arithmetic about the ground, true of every closed walk on every
    // profile, and it is what the old behaviour broke visibly.
    const priced = buildGraphIndex(withClimb({ 0: [100, 20], 1: [50, 10], 2: [70, 5] }))
    const outAndBack = routeThrough(priced, [
      pointOn(0, 0.25),
      pointOn(1, 1),
      pointOn(0, 0.25),
    ])
    expect(outAndBack?.climb).not.toBeNull()
    expect(outAndBack?.climb?.gainFt).toBeCloseTo(outAndBack?.climb?.lossFt as number, 6)
    expect(outAndBack?.climb?.gainFt).toBeGreaterThan(0)
  })

  it('walking an edge backwards climbs what walking it forwards descended', () => {
    // The plainest statement of the defect. Edge 0 rises 500 ft from node 0
    // to node 1, so walking 1 -> 0 is 500 ft of descent and no ascent - and
    // the ascent figure is the only input the day-hike card's ≈time has.
    const priced = buildGraphIndex(withClimb({ 0: [500, 0] }))
    const uphill = routeBetween(priced, pointOn(0, 0), pointOn(0, 1))
    const downhill = routeBetween(priced, pointOn(0, 1), pointOn(0, 0))

    expect(uphill?.climb).toEqual({ gainFt: 500, lossFt: 0 })
    expect(downhill?.climb).toEqual({ gainFt: 0, lossFt: 500 })
  })

  it('prices a closed loop over every edge the loop walks', () => {
    const priced = buildGraphIndex(withClimb({ 0: [100, 20], 1: [50, 10], 2: [70, 5] }))
    const loop = closeTheLoop(priced, [pointOn(0, 0), pointOn(2, 1)])
    expect(loop?.climb).not.toBeNull()
    expect(loop?.climb?.gainFt).toBeGreaterThan(0)
  })

  it('is null when any section of a multi-tap walk cannot be priced', () => {
    const priced = buildGraphIndex(withClimb({ 0: [100, 20], 1: [50, 10], 2: null }))
    const route = routeThrough(priced, [pointOn(0, 0), pointOn(1, 1), pointOn(2, 1)])
    expect(route?.climb).toBeNull()
  })
})

describe('which trail a drawn line meant (#935)', () => {
  // Two trails on the SAME tread - the Harriman case, where the A.T. runs
  // concurrently with Ramapo-Dunderberg and OPRHP publishes its own line over
  // ground ATC's centerline already covers. Measured on the published network
  // (2026-08-27): the median separation between the top two candidates at a
  // sampled Harriman point is 0.0 m.
  const CONCURRENT: TrailGraph = {
    nodes: [
      [-74.1, 41.25],
      [-74.09, 41.25],
      // A third trail, 20 m north - inside 25 m and well outside the 8 m that
      // means "the same place".
      [-74.1, 41.2502],
      [-74.09, 41.2502],
    ],
    edges: [
      {
        ...GRAPH.edges[0],
        from: 0,
        to: 1,
        name: 'Appalachian Trail',
        blaze_color: 'white',
        trail_id: 'centerline:at',
        source: 'centerline',
      },
      {
        ...GRAPH.edges[0],
        from: 0,
        to: 1,
        name: 'Ramapo-Dunderberg',
        blaze_color: 'red',
        trail_id: 'oprhp:rd',
        source: 'oprhp_trails',
      },
      {
        ...GRAPH.edges[0],
        from: 2,
        to: 3,
        name: 'Pine Meadow Trail',
        blaze_color: 'blue',
        trail_id: 'oprhp:pm',
        source: 'oprhp_trails',
      },
    ],
  }
  const concurrent = buildGraphIndex(published(CONCURRENT))
  const onTheTread = { lon: -74.095, lat: 41.25 }

  it('finds every distinct trail in reach, not every edge of them', () => {
    // A hiker can answer "which blaze were you following". They cannot answer
    // "which of these four pieces of the Pine Meadow Trail", which is a
    // question about the artifact rather than about the ground.
    const near = trailsNear(concurrent, onTheTread, DRAWN_SNAP_METRES)

    expect(near).toHaveLength(3)
    expect(near[0].offNetworkFeet).toBeLessThanOrEqual(near[1].offNetworkFeet)
  })

  it('matches nothing past 25 m, which ends a stretch rather than refusing the walk', () => {
    // 0.0001 deg of latitude is about 11.1 m here, so this sits 66 m from the
    // concurrent pair and 44 m from the third trail - outside what a drawn
    // line may reach, on either.
    const wellOff = { lon: -74.095, lat: 41.2506 }

    expect(trailsNear(concurrent, wellOff, DRAWN_SNAP_METRES)).toHaveLength(0)
    expect(trailChoice(concurrent, wellOff).kind).toBe('none')
  })

  it('asks when the answer changes where somebody walks', () => {
    const choice = trailChoice(concurrent, onTheTread)

    expect(choice.kind).toBe('ask')
    if (choice.kind !== 'ask') return
    // The two on one tread collapse to their nearest; the trail 20 m away is
    // the second option, because taking it is a different walk.
    expect(choice.options).toHaveLength(2)
  })

  it('does not ask when both answers are the same ground', () => {
    // The concurrency alone, with the third trail removed. Both candidates
    // are within SAME_TREAD_METRES, so the choice is about a label rather
    // than about a walk - and a question with no consequence is one a hiker
    // learns to dismiss.
    const tread = buildGraphIndex(
      published({ nodes: CONCURRENT.nodes, edges: CONCURRENT.edges.slice(0, 2) }),
    )
    const choice = trailChoice(tread, onTheTread)

    expect(SAME_TREAD_METRES).toBe(8)
    expect(choice.kind).toBe('one')
  })
})

describe('holding a designation across shared tread (#1115)', () => {
  // A corridor where the Long Path rides Pine Meadow's tread, published the
  // way the real artifact publishes it: the shared piece appears TWICE, once
  // per organization, between the same node pairs. The lengths differ by
  // tracing noise, arranged so the shortest-path search provably alternates -
  // it takes whichever twin is shorter, and a different twin is shorter on
  // each piece. That alternation is the defect: without holdDesignation the
  // legs read Pine Meadow / Long Path / Pine Meadow over one straight walk.
  //
  //   0 -- e0 (836, PM) -- 1 == e1/e2 == 2 == e3/e4 == 3 -- e5 (836, PM) -- 4
  //                            (PM 830)      (PM 836)
  //                            (LP 836)      (LP 830)
  const PM = {
    trail_id: 'oprhp_trails:pm',
    source: 'oprhp_trails',
    name: 'Pine Meadow Trail',
    blaze_color: 'blue',
  }
  const LP = {
    trail_id: 'nynjtc_long_path:lp',
    source: 'nynjtc_long_path',
    name: 'Long Path',
    blaze_color: 'aqua',
  }
  const CORRIDOR: TrailGraph = {
    nodes: [
      [-74.1, 41.25],
      [-74.09, 41.25],
      [-74.08, 41.25],
      [-74.07, 41.25],
      [-74.06, 41.25],
    ],
    edges: [
      { from: 0, to: 1, length_m: 836, ...PM },
      { from: 1, to: 2, length_m: 830, ...PM },
      { from: 1, to: 2, length_m: 836, ...LP },
      { from: 2, to: 3, length_m: 836, ...PM },
      { from: 2, to: 3, length_m: 830, ...LP },
      { from: 3, to: 4, length_m: 836, ...PM },
    ],
  }
  const corridor = buildGraphIndex(published(CORRIDOR))

  function on(edgeIndex: number, fraction: number) {
    const edge = CORRIDOR.edges[edgeIndex]
    const [fromLon, fromLat] = CORRIDOR.nodes[edge.from]
    const [toLon, toLat] = CORRIDOR.nodes[edge.to]
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

  it('re-picks interior twins so the walk keeps the designation it entered on', () => {
    const raw = [0, 1, 4, 5]
    // The precondition the fixture exists to set up: the raw pick alternates.
    expect(sameTrail(CORRIDOR.edges[1], CORRIDOR.edges[4])).toBe(false)

    const held = holdDesignation(corridor, raw)
    expect(held).toEqual([0, 1, 3, 5])
  })

  it('lists one leg over the concurrency, crediting both organizations', () => {
    const route = routeBetween(corridor, on(0, 0.5), on(5, 0.5))
    expect(route).not.toBeNull()
    if (route === null) return

    expect(route.legs).toHaveLength(1)
    expect(route.legs[0].name).toBe('Pine Meadow Trail')
    // Post-swap pricing: 418 + 830 + 836 + 418, from the edges the walk now
    // actually names rather than from the search's pre-swap total.
    expect(route.miles).toBeCloseTo(metresToMiles(418 + 830 + 836 + 418), 6)

    // The folded-away designation's organization keeps its credit - #1115's
    // "silently drops the other steward's name" is the failure this pins.
    expect(route.legs[0].concurrent_sources).toEqual(['nynjtc_long_path'])
    expect(route.legsBySource).toContainEqual({ source: 'oprhp_trails', legs: 1 })
    expect(route.legsBySource).toContainEqual({ source: 'nynjtc_long_path', legs: 1 })
  })

  it('keeps the merged leg through a multi-tap walk', () => {
    const route = routeThrough(corridor, [on(0, 0.5), on(3, 0.5), on(5, 0.5)])
    expect(route).not.toBeNull()
    if (route === null) return

    expect(route.legs).toHaveLength(1)
    expect(route.legs[0].concurrent_sources).toEqual(['nynjtc_long_path'])
  })

  it('never swaps onto a fork, however alike its length', () => {
    // Same node pair, near-equal lengths, genuinely different ground: the
    // south side bows ~500 m away at its midpoint. This is the published
    // graph's "Lenape Ridge beside Minisink" shape - the pair that proves
    // length alone cannot answer same-tread - and swapping onto it would
    // draw a hiker a line they are not on.
    const forked: TrailGraph = {
      nodes: CORRIDOR.nodes,
      edges: [
        { from: 0, to: 1, length_m: 836, ...PM },
        { from: 1, to: 2, length_m: 830, ...PM },
        { from: 1, to: 2, length_m: 836, ...LP },
        { from: 3, to: 4, length_m: 836, ...PM },
      ],
    }
    const graph = published(forked)
    // Bow the LP copy away mid-piece; its endpoints still weld to 1 and 2.
    graph.edges[2].geometry = [CORRIDOR.nodes[1], [-74.085, 41.2545], CORRIDOR.nodes[2]]
    const index = buildGraphIndex(graph)

    expect(sameTread(graph, 1, 2)).toBe(false)
    expect(holdDesignation(index, [0, 2, 3])).toEqual([0, 2, 3])
  })

  it('refuses twins whose lengths disagree by more than tracing noise', () => {
    // Identical straight geometry cannot rescue a 5%+ length disagreement on
    // a long edge: 80 m of extra ground over a mile is a different path.
    const graph = published({
      nodes: CORRIDOR.nodes,
      edges: [
        { from: 1, to: 2, length_m: 1609, ...PM },
        { from: 1, to: 2, length_m: 1700, ...LP },
      ],
    })
    expect(sameTread(graph, 0, 1)).toBe(false)
  })

  it('reads no evidence as "not the same ground"', () => {
    // Twins without vertices offer nothing to check the tread against, and
    // an unverifiable swap is refused rather than taken on faith.
    const bare = buildGraphIndex({
      nodes: CORRIDOR.nodes,
      edges: CORRIDOR.edges,
    })
    expect(sameTread(bare.graph, 1, 4)).toBe(false)
    expect(holdDesignation(bare, [0, 1, 4, 5])).toEqual([0, 1, 4, 5])
  })
})
