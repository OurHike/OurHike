// One junction, four arms, real geometry - the fixture the following-a-day-
// hike suites share (#1041).
//
// It is deliberately the shape frame `D10` draws: a hiker walking east along
// Pine Meadow reaches a crossing where Seven Hills goes north, Reeves Meadow
// goes south, and Pine Meadow carries straight on without them. Only ONE of
// the four is the route, which is the whole reason that card names all of
// them.
//
// EVERY EDGE CARRIES GEOMETRY, and that is what separates this fixture from
// the ones dayHikeCard.test.ts and trailGraph.test.ts use. Without vertices
// lib/dayHikeTurns.ts withholds a turn's side rather than reading it off the
// chord between two junctions, so a fixture with no geometry can only test
// the honest-unknown path - which is worth testing and is not the same suite.
//
// THE NUMBERS ARE CHOSEN TO BE READ RATHER THAN COMPUTED. At 41.25 N one
// hundredth of a degree of longitude is about 836 m and of latitude about
// 1,112 m, and `length_m` says so explicitly because build_trail_graph.py
// measures those rather than the client re-deriving them. The arms lie due
// north, south, east and west of the junction, so every bearing this suite
// asserts is a cardinal one somebody can check by looking at the coordinates.

import type { DayHike } from './dayHikes'
import type { TrailGraph } from './trailGraph'

export const JUNCTION_NODE = 1

/**
 *            3  Seven Hills Trail, NYNJTC, white  (e2, north)
 *            |
 *   0 - e0 - 1 - e1 - 2   Pine Meadow Trail, OPRHP, blue (west and east)
 *            |
 *            4  Reeves Meadow Trail, OPRHP, yellow (e3, south)
 */
export const NETWORK: TrailGraph = {
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
      blaze_color: 'Blue',
      geometry: [
        [-74.1, 41.25],
        [-74.09, 41.25],
      ],
    },
    {
      from: 1,
      to: 2,
      length_m: 836,
      trail_id: 'oprhp_trails:1',
      source: 'oprhp_trails',
      name: 'Pine Meadow Trail',
      blaze_color: 'Blue',
      geometry: [
        [-74.09, 41.25],
        [-74.08, 41.25],
      ],
    },
    {
      from: 1,
      to: 3,
      length_m: 1112,
      trail_id: 'nynjtc:2',
      source: 'nynjtc',
      name: 'Seven Hills Trail',
      blaze_color: 'White',
      geometry: [
        [-74.09, 41.25],
        [-74.09, 41.26],
      ],
    },
    {
      from: 1,
      to: 4,
      length_m: 1112,
      trail_id: 'oprhp_trails:9',
      source: 'oprhp_trails',
      name: 'Reeves Meadow Trail',
      blaze_color: 'Yellow',
      geometry: [
        [-74.09, 41.25],
        [-74.09, 41.24],
      ],
    },
  ],
}

/** The same network with every vertex list removed - a graph published
 *  before `trail_graph_geometry.json` existed, which is the state a phone is
 *  in until the lazy fetch lands. */
export const NETWORK_WITHOUT_GEOMETRY: TrailGraph = {
  nodes: NETWORK.nodes,
  edges: NETWORK.edges.map(({ geometry: _geometry, ...edge }) => edge),
}

/** A saved hike over these coordinates, with the fields no test here reads
 *  filled in honestly rather than left to a cast. */
export function hikeThrough(coords: Array<[number, number]>, looped = false): DayHike {
  return {
    id: 'fixture-hike',
    name: 'Fixture walk',
    date: null,
    segments: [coords.map((coord) => ({ coord, poiId: null }))],
    // The cache a saved hike carries. Never read by anything under test here
    // - every figure these suites assert is re-derived from the graph - and
    // deliberately wrong-looking so a test that started reading it would
    // fail loudly rather than agree by luck.
    figures: { miles: 0, legs: [] },
    looped,
    recorded: 'planned',
  }
}

/** West end of Pine Meadow. */
export const WEST_END: [number, number] = [-74.1, 41.25]
/** East end of Pine Meadow, straight on through the junction. */
export const EAST_END: [number, number] = [-74.08, 41.25]
/** North end of Seven Hills - the left turn. */
export const NORTH_END: [number, number] = [-74.09, 41.26]
