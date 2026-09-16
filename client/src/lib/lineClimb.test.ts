import { describe, it, expect } from 'vitest'
import { COVERAGE_TOLERANCE, edgesOfLine, lineClimb } from './lineClimb'
import type { GraphEdge, TrailGraph } from './trailGraph'

const MILE_M = 1609.344

function edge(overrides: Partial<GraphEdge> = {}): GraphEdge {
  return {
    from: 0,
    to: 1,
    length_m: MILE_M,
    trail_id: 'nynjtc:ramapo-dunderberg',
    source: 'nynjtc_trails',
    name: 'Ramapo–Dunderberg',
    blaze_color: 'Red',
    ...overrides,
  }
}

function graph(edges: GraphEdge[]): TrailGraph {
  return { nodes: [], edges }
}

const ID = 'nynjtc:ramapo-dunderberg'

describe('edgesOfLine', () => {
  it('matches on the published id, never on the name', () => {
    // Two different trails genuinely share a name on this ground; the id is
    // what build_trail_graph.py copies onto an edge for exactly this reason.
    const edges = [
      edge({ trail_id: 'a', name: 'Blue Trail' }),
      edge({ trail_id: 'b', name: 'Blue Trail' }),
    ]

    expect(edgesOfLine(graph(edges), 'a')).toHaveLength(1)
  })
})

describe('lineClimb (#1476)', () => {
  it('adds the climb of every edge the line is made of', () => {
    const result = lineClimb(
      graph([edge({ climb: [400, 120] }), edge({ climb: [260, 350] })]),
      { id: ID, lengthMiles: 2 },
    )

    expect(result).toEqual({ kind: 'measured', gainFt: 660, lossFt: 470, miles: 2 })
  })

  it('never adds across a node join, because there is nothing to add across', () => {
    // The whole guard against #559's phantom 36,800 ft: each entry is
    // measured along one edge's own vertices and the sum is over edges, so
    // the step between one edge's end and the next edge's start - which
    // ENDPOINT_SNAP_M allows to be metres apart - is never a term.
    const climbs: Array<[number, number]> = [
      [100, 0],
      [100, 0],
      [100, 0],
    ]
    const result = lineClimb(graph(climbs.map((climb) => edge({ climb }))), {
      id: ID,
      lengthMiles: 3,
    })

    expect(result).toMatchObject({ gainFt: 300 })
  })

  it('refuses a total when any edge is a hole in the DEM', () => {
    const result = lineClimb(
      graph([
        edge({ climb: [400, 120] }),
        // null is the artifact saying nobody measured this edge. Adding the
        // rest would print a figure that reads as the whole trail's and is
        // silently low - the unsafe direction, on the daylight question.
        edge({ climb: null, length_m: MILE_M * 2 }),
      ]),
      { id: ID, lengthMiles: 3 },
    )

    expect(result).toEqual({
      kind: 'unmeasured',
      measuredMiles: 1,
      unmeasuredMiles: 2,
    })
  })

  it('says nothing at all when this phone has no elevation artifact', () => {
    // `undefined`, not `null`: the climb half was never fetched. A different
    // fact from a DEM hole, and it must not be reported as one.
    const result = lineClimb(graph([edge(), edge()]), { id: ID, lengthMiles: 2 })

    expect(result).toEqual({ kind: 'none' })
  })

  it('reports a line that runs past the cells this phone holds', () => {
    const result = lineClimb(graph([edge({ climb: [400, 120] })]), {
      id: ID,
      // The steward publishes 19.1 miles; one mile of it is on this phone.
      lengthMiles: 19.1,
    })

    expect(result).toMatchObject({ kind: 'partial', heldMiles: 1, publishedMiles: 19.1 })
  })

  it('does not call an ordinary measurement disagreement a missing download', () => {
    // Two independent measurements of one trail: EPSG:5070 metres over
    // rounded vertices against whatever the organization surveyed. Just
    // inside the tolerance is a total, not a prompt to download.
    const held = 10 * (1 - COVERAGE_TOLERANCE) + 0.01
    const result = lineClimb(
      graph([edge({ climb: [900, 880], length_m: held * MILE_M })]),
      { id: ID, lengthMiles: 10 },
    )

    expect(result.kind).toBe('measured')
  })

  it('prefers the DEM hole to the missing cell, because only one of them can be fixed', () => {
    // Both conditions hold: an unmeasured edge AND far less line than the
    // steward published. Telling a hiker to download a cell would not
    // produce the figure, so the honest answer is the one about the ground.
    const result = lineClimb(
      graph([edge({ climb: [400, 120] }), edge({ climb: null })]),
      { id: ID, lengthMiles: 19.1 },
    )

    expect(result.kind).toBe('unmeasured')
  })

  it('answers nothing for a line the graph does not carry', () => {
    expect(lineClimb(graph([edge({ climb: [1, 1] })]), { id: 'other' })).toEqual({
      kind: 'none',
    })
    expect(lineClimb(null, { id: ID })).toEqual({ kind: 'none' })
    expect(lineClimb(graph([edge({ climb: [1, 1] })]), { id: null })).toEqual({
      kind: 'none',
    })
  })

  it('returns unverified, not measured, when lengthMiles is null (#1516)', () => {
    // WHAT THIS TEST USED TO ASSERT, and why it changed rather than being
    // deleted. It expected `measured` here, reasoning that "a line with a
    // climb and no published length is not a partial download, and
    // withholding the figure for want of a comparison would lose it on every
    // one of them". The second half of that is still right and this fix keeps
    // it - gainFt is still returned below. The first half rested on a false
    // premise: no exporter wrote `length_miles`, so this was not one case
    // among several, it was the ONLY case, and every tap took it. A phone
    // holding one cell of a long trail printed that cell's climb as the
    // trail's, silently low, on the band a hiker uses to judge daylight.
    const result = lineClimb(graph([edge({ climb: [400, 120] })]), {
      id: ID,
      lengthMiles: null,
    })

    expect(result).toMatchObject({ kind: 'unverified', gainFt: 400, lossFt: 120 })
  })

  it('returns unverified when lengthMiles is absent, zero or not finite', () => {
    // Three shapes of "no length to compare against", each reaching the phone
    // from a different place: a release published before #1516 added the
    // field, a source that publishes a zero, and a malformed property that
    // numberProp let through.
    for (const lengthMiles of [undefined, null, 0, Number.NaN]) {
      expect(
        lineClimb(graph([edge({ climb: [400, 120] })]), { id: ID, lengthMiles }),
      ).toMatchObject({ kind: 'unverified' })
    }
  })

  it('still reports measured once a length is there and the edges cover it', () => {
    // The guard firing in the other direction: with the field present and the
    // held edges long enough, the answer is the line's own total and says so.
    const result = lineClimb(graph([edge({ climb: [400, 120] })]), {
      id: ID,
      lengthMiles: 1,
    })

    expect(result).toMatchObject({ kind: 'measured', gainFt: 400, lossFt: 120 })
  })
})

describe('the companion passed beside the graph (#1476)', () => {
  it('prices a line from an index-aligned elevation array', () => {
    // The tap's own shape: the graph as merged, and the climb half held
    // beside it rather than rebuilt into a new index.
    const edges = [edge({ trail_id: 'other' }), edge(), edge()]

    const result = lineClimb(graph(edges), { id: ID, lengthMiles: 2 }, [
      [999, 999],
      [400, 120],
      [260, 350],
    ])

    // The first entry belongs to a different trail and must not be added -
    // which is exactly what index alignment is protecting.
    expect(result).toEqual({ kind: 'measured', gainFt: 660, lossFt: 470, miles: 2 })
  })

  it('refuses an array whose length disagrees with the graph', () => {
    // edge 40 priced from edge 41's climb is a plausible number against the
    // wrong trail. The whole array is declined rather than trimmed.
    const result = lineClimb(graph([edge(), edge()]), { id: ID, lengthMiles: 2 }, [
      [400, 120],
    ])

    expect(result).toEqual({ kind: 'none' })
  })

  it('reads a null in the array as a DEM hole, exactly as an attached null is', () => {
    const result = lineClimb(graph([edge(), edge()]), { id: ID, lengthMiles: 2 }, [
      [400, 120],
      null,
    ])

    expect(result).toMatchObject({ kind: 'unmeasured', measuredMiles: 1 })
  })

  it('falls back to whatever the edges themselves carry when no array is given', () => {
    const result = lineClimb(graph([edge({ climb: [400, 120] })]), {
      id: ID,
      lengthMiles: 1,
    })

    expect(result).toMatchObject({ kind: 'measured', gainFt: 400 })
  })
})
