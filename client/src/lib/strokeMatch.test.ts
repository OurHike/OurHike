// Putting a drawn line on the trails (#983, frame `1k`).
//
// THE ASYMMETRY THIS SUITE PINS, which is lib/trailGraph.test.ts's stated one
// arriving in a different shape: a stroke that comes back as FEWER stretches
// than the hiker drew is an inconvenience, and one that comes back as a route
// across ground with no trail on it is the failure the whole module exists to
// prevent. So the tests below assert that ground is DROPPED, and a change that
// makes them pass by bridging a gap is not an improvement.

import { describe, expect, it } from 'vitest'

import {
  matchStroke,
  STROKE_HOLD_MARGIN_METRES,
  STROKE_SAMPLE_METRES,
} from './strokeMatch'
import { buildGraphIndex, DRAWN_SNAP_METRES, type TrailGraph } from './trailGraph'

// 0.0001 deg of latitude is about 11.1 m here; 0.0001 deg of longitude about
// 8.4 m at 41.25 N. The fixtures below are spelled in those units so a
// distance in a comment can be checked against the coordinates.
//
//   Pine Meadow Trail (blue), west to east along 41.2500
//   Seven Hills Trail (orange), west to east along 41.2502   (~22 m north)
//   Kakiat Trail (yellow), a separate island far to the north
const GRAPH: TrailGraph = {
  nodes: [
    [-74.1, 41.25],
    [-74.09, 41.25],
    [-74.1, 41.2502],
    [-74.09, 41.2502],
    [-74.1, 41.28],
    [-74.09, 41.28],
  ],
  edges: [
    {
      from: 0,
      to: 1,
      length_m: 836,
      trail_id: 'oprhp:pm',
      source: 'oprhp_trails',
      name: 'Pine Meadow Trail',
      blaze_color: 'blue',
    },
    {
      from: 2,
      to: 3,
      length_m: 836,
      trail_id: 'nynjtc:sh',
      source: 'nynjtc_long_path',
      name: 'Seven Hills Trail',
      blaze_color: 'orange',
    },
    {
      from: 4,
      to: 5,
      length_m: 836,
      trail_id: 'oprhp:kk',
      source: 'oprhp_trails',
      name: 'Kakiat Trail',
      blaze_color: 'yellow',
    },
  ],
}

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

/** A stroke of `count` samples spread along a line of latitude. */
function along(lat: number, fromLon: number, toLon: number, count = 12) {
  return Array.from({ length: count }, (_, at) => ({
    lon: fromLon + ((toLon - fromLon) * at) / (count - 1),
    lat,
  }))
}

describe('a stroke drawn along one trail', () => {
  it('comes back as that trail, once', () => {
    const match = matchStroke(index, along(41.25, -74.099, -74.091))

    expect(match.stretches).toHaveLength(1)
    expect(match.stretches[0].name).toBe('Pine Meadow Trail')
    expect(match.droppedMetres).toBe(0)
  })

  it('holds its trail through a wobble that reaches the neighbour', () => {
    // THE CONTINUITY RULE, and the reason this module is not N independent
    // calls. Seven Hills is ~22 m north - inside the 25 m match radius for
    // much of this stroke - so a per-sample nearest would flick between the
    // two and hand back a walk down four trails that is really a walk down
    // one.
    const wobbly = along(41.25, -74.099, -74.091, 16).map((point, at) => ({
      ...point,
      // Drift north toward Seven Hills in the middle and come back.
      lat: point.lat + (at > 4 && at < 11 ? 0.00009 : 0),
    }))

    const match = matchStroke(index, wobbly)

    expect(match.stretches).toHaveLength(1)
    expect(match.stretches[0].name).toBe('Pine Meadow Trail')
  })

  it('changes trail when the stroke genuinely leaves the old one', () => {
    // Half along Pine Meadow, then north past the hold radius onto Seven
    // Hills. Continuity is a preference for the trail in hand, not a refusal
    // to ever leave it.
    const stroke = [
      ...along(41.25, -74.099, -74.0955, 6),
      ...along(41.2502, -74.0945, -74.091, 6),
    ]

    const match = matchStroke(index, stroke)
    const names = match.stretches.map((stretch) => stretch.name)

    expect(names).toContain('Pine Meadow Trail')
    expect(names).toContain('Seven Hills Trail')
  })
})

describe('ground with no trail under it', () => {
  it('ends a stretch and is dropped, never bridged', () => {
    // Pine Meadow, then a long way north over nothing, then the Kakiat
    // island. The two ends are on real trail and there is no maintained way
    // between them - drawing one would be the app claiming ground.
    const stroke = [
      ...along(41.25, -74.099, -74.095, 6),
      ...along(41.26, -74.095, -74.095, 6),
      ...along(41.28, -74.099, -74.095, 6),
    ]

    const match = matchStroke(index, stroke)

    expect(match.stretches.map((stretch) => stretch.name)).toEqual([
      'Pine Meadow Trail',
      'Kakiat Trail',
    ])
    // The gap is real and measured, and the two stretches are two - not one
    // route with a hole in it.
    expect(match.droppedMetres).toBeGreaterThan(1000)
  })

  it('drops a stroke that never touches a trail at all', () => {
    const match = matchStroke(index, along(41.27, -74.099, -74.091))

    expect(match.stretches).toHaveLength(0)
    expect(match.droppedMetres).toBeGreaterThan(0)
  })
})

describe('two trails on one tread', () => {
  // The Harriman case: the A.T. runs concurrently with Ramapo-Dunderberg, and
  // OPRHP publishes its own line over ground ATC's centerline already covers.
  const CONCURRENT: TrailGraph = {
    nodes: GRAPH.nodes,
    edges: [
      GRAPH.edges[0],
      {
        ...GRAPH.edges[0],
        trail_id: 'centerline:at',
        source: 'centerline',
        name: 'Appalachian Trail',
        blaze_color: 'white',
      },
    ],
  }

  it('names both rather than picking one and hiding the other', () => {
    // Neither label is wrong on ground that carries both blazes, and choosing
    // silently would be the app deciding which paint a hiker should look for.
    const match = matchStroke(
      buildGraphIndex(published(CONCURRENT)),
      along(41.25, -74.099, -74.091),
    )

    expect(match.stretches).toHaveLength(1)
    const named = [
      match.stretches[0].name,
      ...match.stretches[0].alsoKnownAs.map((also) => also.name),
    ]
    expect(named).toContain('Pine Meadow Trail')
    expect(named).toContain('Appalachian Trail')
  })

  it('does not treat a concurrency as something to ask about', () => {
    // `alternatives` is "you might be on this INSTEAD", and a trail on the
    // same tread is not that. A question with no consequence is one a hiker
    // learns to dismiss.
    const match = matchStroke(
      buildGraphIndex(published(CONCURRENT)),
      along(41.25, -74.099, -74.091),
    )

    expect(match.stretches[0].alternatives).toHaveLength(0)
  })
})

describe('the thresholds', () => {
  it('keeps the hold margin under the match radius', () => {
    // The bug the margin's own note records: a hold WIDER than the radius
    // means a stroke can never move onto a neighbouring trail at all, which
    // through Harriman - where marked trails routinely run within 25 m of
    // each other - is a hiker drawing a turn the app refuses to see.
    expect(STROKE_HOLD_MARGIN_METRES).toBeLessThan(DRAWN_SNAP_METRES)
  })

  it('decimates to well inside the match radius', () => {
    // The bound that makes decimation safe: any trail within reach of a
    // dropped sample is within reach of one of its neighbours.
    expect(STROKE_SAMPLE_METRES).toBeLessThan(DRAWN_SNAP_METRES)
  })
})
