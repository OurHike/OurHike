// Tests for lib/dayHikeCard.ts - the finished-hike card's derivations (#980).
//
// The two rules worth a suite: a saved hike the current graph cannot claim is
// REFUSED whole (never partially rerouted), and a bail-out's mile is the
// distance a hiker has actually walked when they reach the junction - which
// pair-wise accumulation gets right and a deduplicated edge list gets wrong
// on any out-and-back.

import { describe, expect, it } from 'vitest'

import { dayHikeBailOuts, resolveDayHike } from './dayHikeCard'
import type { DayHike, DayHikeEnd, DayHikeSegment } from './dayHikes'
import { buildGraphIndex, type TrailGraph } from './trailGraph'

// The App.dayHike fixture's Harriman-ish T, grown one arm so the junction is
// a real crossing: Seven Hills passes THROUGH node 1, one edge each side,
// same trail_id - the shape whose two edges must collapse onto one row.
//
//        3 (-74.09, 41.26)   Seven Hills Trail, white (edge 2)
//        |
//   0 -- 1 -- 2              Pine Meadow Trail, blue (edges 0, 1)
//        |
//        4 (-74.09, 41.24)   Seven Hills Trail, white (edge 3)
const GRAPH: TrailGraph = {
  nodes: [
    [-74.1, 41.25],
    [-74.09, 41.25],
    [-74.08, 41.25],
    [-74.09, 41.26],
    [-74.09, 41.24],
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
      from: 1,
      to: 4,
      length_m: 1112,
      trail_id: 'nynjtc_long_path:2',
      source: 'nynjtc_long_path',
      name: 'Seven Hills Trail',
      blaze_color: 'white',
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

const end = (lon: number, lat: number): DayHikeEnd => ({ coord: [lon, lat], poiId: null })

function hikeOf(segments: DayHikeSegment[], looped = false): DayHike {
  return {
    id: 'hike-1',
    name: 'Pine Meadow out',
    date: null,
    segments,
    // A stale cache on purpose: nothing below may read it.
    figures: { miles: 99, legs: [] },
    looped,
    recorded: 'planned',
    note: '',
  }
}

describe('resolveDayHike', () => {
  it('re-claims the stored ends and re-derives the figures', () => {
    const resolved = resolveDayHike(
      index,
      hikeOf([[end(-74.095, 41.25), end(-74.085, 41.25)]]),
    )

    expect(resolved).not.toBeNull()
    // Half of each 836 m edge: 836 m, not the cache's planted 99 miles.
    expect(resolved?.miles).toBeCloseTo(0.52, 2)
    expect(resolved?.legs.map((leg) => leg.name)).toEqual(['Pine Meadow Trail'])
    // The leg agrees with the total (#1002): priced at the walked metres,
    // never the two edges billed whole.
    expect(resolved?.legs[0].miles).toBeCloseTo(0.52, 2)
    expect(resolved?.looped).toBe(false)
  })

  it('refuses the whole hike when one end is off every trail', () => {
    const resolved = resolveDayHike(
      index,
      hikeOf([[end(-74.095, 41.25), end(-74.095, 41.3)]]),
    )

    expect(resolved).toBeNull()
  })

  it('refuses a multi-segment hike asked to loop, rather than guessing across the gap', () => {
    const resolved = resolveDayHike(
      index,
      hikeOf(
        [
          [end(-74.095, 41.25), end(-74.085, 41.25)],
          [end(-74.09, 41.252), end(-74.09, 41.258)],
        ],
        true,
      ),
    )

    expect(resolved).toBeNull()
  })

  it('sums walked miles across segments and keeps their legs in order', () => {
    const resolved = resolveDayHike(
      index,
      hikeOf([
        [end(-74.095, 41.25), end(-74.085, 41.25)],
        [end(-74.09, 41.252), end(-74.09, 41.258)],
      ]),
    )

    expect(resolved).not.toBeNull()
    // 836 m of Pine Meadow, then 41.252→41.258 of Seven Hills (0.006 of the
    // 0.01-degree, 1,112 m edge): 836 + 667.2 = 1,503 m.
    expect(resolved?.miles).toBeCloseTo(0.93, 2)
    expect(resolved?.legs.map((leg) => leg.name)).toEqual([
      'Pine Meadow Trail',
      'Seven Hills Trail',
    ])
  })
})

describe('dayHikeBailOuts', () => {
  it('lists a crossing trail once, at the mile actually walked to its junction', () => {
    const resolved = resolveDayHike(
      index,
      hikeOf([[end(-74.095, 41.25), end(-74.085, 41.25)]]),
    )
    const bailOuts = dayHikeBailOuts(index, resolved!)

    // Seven Hills crosses node 1 with an edge on each side; one trail is one
    // way off, so the two edges are one row.
    expect(bailOuts).toHaveLength(1)
    expect(bailOuts[0].name).toBe('Seven Hills Trail')
    expect(bailOuts[0].blaze_color).toBe('white')
    // Half of the first 836 m edge walked to reach the junction.
    expect(bailOuts[0].miles).toBeCloseTo(0.26, 2)
  })

  it('lists a crossing trail once even where its two sides are two published lines (#1433)', () => {
    // The same claim as the test above, against the artifact's real shape:
    // `trail_id` is one id per source FEATURE, so a junction is routinely also
    // the place a publisher's line ends. Keyed on the id, Seven Hills listed
    // twice here - two identical rows on the list somebody reads while working
    // out how to get off a trail.
    const split: TrailGraph = {
      nodes: GRAPH.nodes,
      edges: GRAPH.edges.map((edge, at) =>
        at === 3 ? { ...edge, trail_id: 'nynjtc_long_path:99' } : edge,
      ),
    }
    const splitIndex = buildGraphIndex(published(split))
    const resolved = resolveDayHike(
      splitIndex,
      hikeOf([[end(-74.095, 41.25), end(-74.085, 41.25)]]),
    )
    const bailOuts = dayHikeBailOuts(splitIndex, resolved!)

    expect(bailOuts).toHaveLength(1)
    expect(bailOuts[0].name).toBe('Seven Hills Trail')
  })

  it('keeps two unnamed ways off apart, where the route order would merge them', () => {
    // WHERE THIS LIST PARTS COMPANY WITH THE ROUTE ORDER, deliberately. There,
    // two consecutive "Unnamed trail" rows are a repeat and #1433 merges them.
    // Here a row is a way off a trail somebody may need to leave in a hurry,
    // so two unnamed arms stay two rows: folding them would delete an escape
    // route rather than a duplicate.
    const unnamed: TrailGraph = {
      nodes: GRAPH.nodes,
      edges: GRAPH.edges.map((edge, at) =>
        at === 2 || at === 3
          ? { ...edge, name: null, blaze_color: null, trail_id: `nynjtc:${at}` }
          : edge,
      ),
    }
    const unnamedIndex = buildGraphIndex(published(unnamed))
    const resolved = resolveDayHike(
      unnamedIndex,
      hikeOf([[end(-74.095, 41.25), end(-74.085, 41.25)]]),
    )

    expect(dayHikeBailOuts(unnamedIndex, resolved!)).toHaveLength(2)
  })

  it('lists ONE unnamed trail crossing the junction as one way off', () => {
    // The crossing case, for a trail nobody named. `build_trail_graph.py`
    // splits a published line at every junction and gives each piece the
    // parent feature's id, so both sides of the crossing share one - which is
    // why the identity above falls back to the id before it falls back to the
    // edge. Keyed straight off the edge this listed one trail twice, both rows
    // reading "Unnamed trail" at the same mile.
    const crossing: TrailGraph = {
      nodes: GRAPH.nodes,
      edges: GRAPH.edges.map((edge, at) =>
        at === 2 || at === 3 ? { ...edge, name: null, blaze_color: null } : edge,
      ),
    }
    const crossingIndex = buildGraphIndex(published(crossing))
    const resolved = resolveDayHike(
      crossingIndex,
      hikeOf([[end(-74.095, 41.25), end(-74.085, 41.25)]]),
    )

    expect(dayHikeBailOuts(crossingIndex, resolved!)).toHaveLength(1)
  })

  it('answers a single-edge walk with an empty list, which the card must print', () => {
    const resolved = resolveDayHike(
      index,
      hikeOf([[end(-74.098, 41.25), end(-74.092, 41.25)]]),
    )

    expect(dayHikeBailOuts(index, resolved!)).toEqual([])
  })

  it('lists a junction once per pass on an out-and-back, at increasing miles', () => {
    // Up Seven Hills and back down to Pine Meadow's far side: node 1 is
    // walked through twice, and each pass is a real chance to get off.
    const resolved = resolveDayHike(
      index,
      hikeOf([[end(-74.095, 41.25), end(-74.09, 41.255), end(-74.085, 41.25)]]),
    )
    const bailOuts = dayHikeBailOuts(index, resolved!)

    expect(bailOuts).toHaveLength(2)
    expect(bailOuts[0].name).toBe('Seven Hills Trail')
    expect(bailOuts[1].name).toBe('Seven Hills Trail')
    expect(bailOuts[1].miles).toBeGreaterThan(bailOuts[0].miles)
    // Pass one: 418 m of Pine Meadow. Pass two: that, plus 556 m up and 556 m
    // back down Seven Hills - the doubled climb a deduplicated edge list
    // would have counted once.
    expect(bailOuts[0].miles).toBeCloseTo(0.26, 2)
    expect(bailOuts[1].miles).toBeCloseTo(0.95, 2)
  })

  it('walks the closing leg of a loop too', () => {
    const resolved = resolveDayHike(
      index,
      hikeOf([[end(-74.095, 41.25), end(-74.085, 41.25)]], true),
    )
    const bailOuts = dayHikeBailOuts(index, resolved!)

    // Out through the junction, and back through it on the closing leg.
    expect(bailOuts).toHaveLength(2)
    expect(bailOuts[1].miles).toBeGreaterThan(bailOuts[0].miles)
  })
})
