// Tests for lib/dayHikeDraft.ts - the day hike being built (#978, #976,
// wireframe frame `1j`).
//
// The rules under test are the ones a component could quietly break:
//
//   A refused tap PLACES NOTHING and says why. Neither doing nothing (reads as
//   a broken map) nor placing the point anyway (the app deciding which trail
//   somebody meant) is acceptable, and #771's 48%-within-150-m measurement is
//   why the second one is worse here than it sounds.
//
//   Taps that cannot be connected are `unroutable`, not an empty route. The
//   caller has to be able to tell "nothing to route yet" from "nothing to
//   route at all", because only the second is something the hiker needs told.

import { describe, expect, it } from 'vitest'

import {
  canCloseLoop,
  canStartStretch,
  clearDraft,
  draftPoints,
  draftStatus,
  EMPTY_DRAFT,
  loopDraft,
  NETWORK_STILL_ARRIVING,
  OFF_NETWORK_REFUSAL,
  startStretch,
  stretchRoute,
  tapAt,
  undoTap,
} from './dayHikeDraft'
import { buildGraphIndex, type RouteLeg, type TrailGraph } from './trailGraph'

//   3 (-74.09, 41.26)  Seven Hills Trail, NYNJTC
//   |  1112 m
//   0 --- 836 m --- 1 --- 836 m --- 2   Pine Meadow Trail, OPRHP
//   4 --- 836 m --- 5   Kakiat Trail, a separate island
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

/** On Pine Meadow, halfway along its first edge. */
const ON_TRAIL = { lon: -74.095, lat: 41.25 }
/** Further along Pine Meadow. */
const FURTHER = { lon: -74.085, lat: 41.25 }
/** Up Seven Hills. */
const UP_SEVEN_HILLS = { lon: -74.09, lat: 41.255 }
/** Node 3, the far end of Seven Hills - a second stretch's finish. */
const SEVEN_HILLS_END = { lon: -74.09, lat: 41.26 }
/** On the Kakiat island, which nothing connects to. */
const OTHER_ISLAND = { lon: -73.995, lat: 41.3 }
/** Nowhere near a trail. */
const OFF_TRAIL = { lon: -74.095, lat: 41.31 }

describe('tapping', () => {
  it('places a point on a trail', () => {
    const draft = tapAt(index, EMPTY_DRAFT, ON_TRAIL)

    expect(draftPoints(draft)).toHaveLength(1)
    expect(draft.refusal).toBeNull()
  })

  it('refuses a tap off the network and places nothing', () => {
    const draft = tapAt(index, EMPTY_DRAFT, OFF_TRAIL)

    expect(draftPoints(draft)).toHaveLength(0)
    expect(draft.refusal).toBe(OFF_NETWORK_REFUSAL)
  })

  it('does not call a tap off-network when it is the LINES that are missing', () => {
    // #1093. `trail_graph.json` lands at launch and carries no vertices;
    // `trail_graph_geometry.json` is fetched only when this builder opens.
    // In between, a tap dead on the drawn trail cannot be answered at all -
    // and the sentence a hiker gets must not be the one that says their aim
    // was wrong, because it was not.
    const arriving = buildGraphIndex(GRAPH)
    const draft = tapAt(arriving, EMPTY_DRAFT, ON_TRAIL)

    expect(draftPoints(draft)).toHaveLength(0)
    expect(draft.refusal).toBe(NETWORK_STILL_ARRIVING)
    expect(draft.refusal).not.toBe(OFF_NETWORK_REFUSAL)
  })

  it('says the same thing whether the tap was on a trail or off one, in that window', () => {
    // The distinction it CANNOT draw, stated so nobody adds it back. With no
    // vertices the app does not know where any trail runs, so it cannot know
    // which of the two happened - and guessing would put it back to telling
    // some hikers their aim was wrong on no evidence.
    const arriving = buildGraphIndex(GRAPH)

    expect(tapAt(arriving, EMPTY_DRAFT, ON_TRAIL).refusal).toBe(NETWORK_STILL_ARRIVING)
    expect(tapAt(arriving, EMPTY_DRAFT, OFF_TRAIL).refusal).toBe(NETWORK_STILL_ARRIVING)
  })

  it('keeps the points it already had when one tap is refused', () => {
    const started = tapAt(index, EMPTY_DRAFT, ON_TRAIL)
    const refused = tapAt(index, started, OFF_TRAIL)

    expect(draftPoints(refused)).toEqual(draftPoints(started))
    expect(refused.refusal).toBe(OFF_NETWORK_REFUSAL)
  })

  it('clears the refusal as soon as a tap lands', () => {
    const refused = tapAt(index, EMPTY_DRAFT, OFF_TRAIL)
    const landed = tapAt(index, refused, ON_TRAIL)

    expect(landed.refusal).toBeNull()
  })

  it('says the same thing every time it refuses', () => {
    // The sentence tells a hiker the app has a rule rather than a bug, which
    // only works if it is the same sentence.
    expect(OFF_NETWORK_REFUSAL).toMatch(
      /only builds routes on trails an organization maintains/,
    )
    expect(tapAt(index, EMPTY_DRAFT, OFF_TRAIL).refusal).toBe(OFF_NETWORK_REFUSAL)
    expect(tapAt(index, EMPTY_DRAFT, OTHER_ISLAND).refusal).toBeNull()
  })
})

describe('undo', () => {
  it('takes back the last tap', () => {
    const two = tapAt(index, tapAt(index, EMPTY_DRAFT, ON_TRAIL), FURTHER)

    expect(draftPoints(undoTap(two))).toHaveLength(1)
  })

  it('clears a refusal before it takes back anything', () => {
    // Undo right after a refused tap must not also eat the good point before
    // it - the hiker is dismissing the message, not their work.
    const started = tapAt(index, EMPTY_DRAFT, ON_TRAIL)
    const refused = tapAt(index, started, OFF_TRAIL)
    const undone = undoTap(refused)

    expect(undone.refusal).toBeNull()
    expect(draftPoints(undone)).toHaveLength(1)
  })

  it('is harmless on an empty draft', () => {
    expect(undoTap(EMPTY_DRAFT)).toEqual(EMPTY_DRAFT)
  })
})

describe('what the bar should be saying', () => {
  it('is empty before anything is tapped', () => {
    expect(draftStatus(index, EMPTY_DRAFT).kind).toBe('empty')
  })

  it('is started after one tap, which is not an error', () => {
    expect(draftStatus(index, tapAt(index, EMPTY_DRAFT, ON_TRAIL)).kind).toBe('started')
  })

  it('is routed once two taps connect', () => {
    const two = tapAt(index, tapAt(index, EMPTY_DRAFT, ON_TRAIL), UP_SEVEN_HILLS)
    const status = draftStatus(index, two)

    expect(status.kind).toBe('routed')
    if (status.kind !== 'routed') throw new Error('unreachable')
    expect(status.legs.map((leg: RouteLeg) => leg.name)).toEqual([
      'Pine Meadow Trail',
      'Seven Hills Trail',
    ])
  })

  it('is unroutable when both taps are on real trails the network cannot connect', () => {
    // The honest case, not a bug: the published network is clipped to a ring,
    // and two parks can be genuinely unconnected by maintained trail. Drawing
    // a straight line between them would be the app claiming ground.
    const across = tapAt(index, tapAt(index, EMPTY_DRAFT, ON_TRAIL), OTHER_ISLAND)

    expect(draftStatus(index, across).kind).toBe('unroutable')
    expect(stretchRoute(index, draftPoints(across), false)).toBeNull()
  })
})

describe('closing the loop', () => {
  it('is not offered until there is somewhere to come back from', () => {
    expect(canCloseLoop(EMPTY_DRAFT)).toBe(false)
    expect(canCloseLoop(tapAt(index, EMPTY_DRAFT, ON_TRAIL))).toBe(false)
    expect(canCloseLoop(tapAt(index, tapAt(index, EMPTY_DRAFT, ON_TRAIL), FURTHER))).toBe(
      true,
    )
  })

  it('is not offered twice', () => {
    const two = tapAt(index, tapAt(index, EMPTY_DRAFT, ON_TRAIL), FURTHER)

    expect(canCloseLoop(loopDraft(two))).toBe(false)
  })

  it('walks back to the first tap', () => {
    const two = tapAt(index, tapAt(index, EMPTY_DRAFT, ON_TRAIL), FURTHER)
    const out = stretchRoute(index, draftPoints(two), false)
    const loop = stretchRoute(index, draftPoints(two), true)

    expect(out).not.toBeNull()
    expect(loop).not.toBeNull()
    expect(loop?.miles).toBeCloseTo((out?.miles ?? 0) * 2, 5)
  })

  it('undo after closing the loop reopens it and takes back nothing else', () => {
    // Closing the loop was one action, so undo is one action: the tapped
    // points are the hiker's work and this must not silently eat one.
    const two = tapAt(index, tapAt(index, EMPTY_DRAFT, ON_TRAIL), FURTHER)
    const undone = undoTap(loopDraft(two))

    expect(undone.looped).toBe(false)
    expect(draftPoints(undone)).toHaveLength(2)
  })

  it('reopens when the hiker taps again, rather than appending after the return leg', () => {
    const looped = loopDraft(tapAt(index, tapAt(index, EMPTY_DRAFT, ON_TRAIL), FURTHER))
    const reopened = tapAt(index, looped, UP_SEVEN_HILLS)

    expect(reopened.looped).toBe(false)
    expect(draftPoints(reopened)).toHaveLength(3)
  })
})

describe('clearing', () => {
  it('goes back to empty', () => {
    expect(clearDraft()).toEqual(EMPTY_DRAFT)
  })
})

describe('several stretches, and the gap between them (#935, #983)', () => {
  // The whole model in one fixture: walk a bit of Pine Meadow, bushwhack, pick
  // Seven Hills up on the far side.
  function twoStretches() {
    const first = tapAt(index, tapAt(index, EMPTY_DRAFT, ON_TRAIL), FURTHER)
    return tapAt(
      index,
      tapAt(index, startStretch(first), UP_SEVEN_HILLS),
      SEVEN_HILLS_END,
    )
  }

  it('is not offered until the stretch in hand is already a walk', () => {
    // A stretch of one tap is a start with no finish, and a draft holding two
    // of those is a pair of pins rather than a hike.
    expect(canStartStretch(EMPTY_DRAFT)).toBe(false)
    expect(canStartStretch(tapAt(index, EMPTY_DRAFT, ON_TRAIL))).toBe(false)
    expect(
      canStartStretch(tapAt(index, tapAt(index, EMPTY_DRAFT, ON_TRAIL), FURTHER)),
    ).toBe(true)
  })

  it('routes each stretch on its own and never across the gap', () => {
    const status = draftStatus(index, twoStretches())

    expect(status.kind).toBe('routed')
    if (status.kind !== 'routed') return
    // TWO sets of geometry, which is what makes drawing across the gap
    // impossible rather than merely discouraged: there is no combined
    // `sections` anywhere for a caller to reach for.
    expect(status.stretches).toHaveLength(2)
    expect(status.miles).toBeCloseTo(
      status.stretches[0].route.miles + status.stretches[1].route.miles,
      6,
    )
  })

  it('keeps the gap out of the trail miles and reports it separately', () => {
    const status = draftStatus(index, twoStretches())

    if (status.kind !== 'routed') throw new Error('expected a routed draft')
    expect(status.gapMiles).toBeGreaterThan(0)
    // The load-bearing assertion, and the reason this test exists: a change
    // that folded the gap into the total would make the app claim ground no
    // organization maintains and nobody has walked for us.
    expect(status.miles).toBeLessThan(status.miles + status.gapMiles)
    expect(status.stretches.every((stretch) => stretch.route.miles > 0)).toBe(true)
  })

  it('is unroutable when a LATER stretch cannot be routed, rather than dropping it', () => {
    // Dropping it would turn the walk the hiker described into a shorter one
    // they did not, with totals that are right about a different walk.
    const first = tapAt(index, tapAt(index, EMPTY_DRAFT, ON_TRAIL), FURTHER)
    const stranded = tapAt(
      index,
      tapAt(index, startStretch(first), OTHER_ISLAND),
      ON_TRAIL,
    )

    expect(draftStatus(index, stranded).kind).toBe('unroutable')
  })

  it('undo takes back the new stretch before it takes back a tap', () => {
    const started = startStretch(
      tapAt(index, tapAt(index, EMPTY_DRAFT, ON_TRAIL), FURTHER),
    )
    const undone = undoTap(started)

    expect(undone.segments).toHaveLength(1)
    expect(draftPoints(undone)).toHaveLength(2)
  })

  it('will not close a loop across a gap', () => {
    // lib/dayHikeCard.ts refuses to resolve a multi-segment looped hike, so
    // offering this would let a hiker save a walk that can never be
    // re-resolved and falls back to its cache for ever.
    expect(canStartStretch(twoStretches())).toBe(true)
    expect(canCloseLoop(twoStretches())).toBe(false)
  })
})
