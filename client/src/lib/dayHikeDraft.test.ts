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
  clearDraft,
  draftRoute,
  draftStatus,
  EMPTY_DRAFT,
  loopDraft,
  OFF_NETWORK_REFUSAL,
  tapAt,
  undoTap,
} from './dayHikeDraft'
import { buildGraphIndex, type TrailGraph } from './trailGraph'

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

const index = buildGraphIndex(GRAPH)

/** On Pine Meadow, halfway along its first edge. */
const ON_TRAIL = { lon: -74.095, lat: 41.25 }
/** Further along Pine Meadow. */
const FURTHER = { lon: -74.085, lat: 41.25 }
/** Up Seven Hills. */
const UP_SEVEN_HILLS = { lon: -74.09, lat: 41.255 }
/** On the Kakiat island, which nothing connects to. */
const OTHER_ISLAND = { lon: -73.995, lat: 41.3 }
/** Nowhere near a trail. */
const OFF_TRAIL = { lon: -74.095, lat: 41.31 }

describe('tapping', () => {
  it('places a point on a trail', () => {
    const draft = tapAt(index, EMPTY_DRAFT, ON_TRAIL)

    expect(draft.points).toHaveLength(1)
    expect(draft.refusal).toBeNull()
  })

  it('refuses a tap off the network and places nothing', () => {
    const draft = tapAt(index, EMPTY_DRAFT, OFF_TRAIL)

    expect(draft.points).toHaveLength(0)
    expect(draft.refusal).toBe(OFF_NETWORK_REFUSAL)
  })

  it('keeps the points it already had when one tap is refused', () => {
    const started = tapAt(index, EMPTY_DRAFT, ON_TRAIL)
    const refused = tapAt(index, started, OFF_TRAIL)

    expect(refused.points).toEqual(started.points)
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

    expect(undoTap(two).points).toHaveLength(1)
  })

  it('clears a refusal before it takes back anything', () => {
    // Undo right after a refused tap must not also eat the good point before
    // it - the hiker is dismissing the message, not their work.
    const started = tapAt(index, EMPTY_DRAFT, ON_TRAIL)
    const refused = tapAt(index, started, OFF_TRAIL)
    const undone = undoTap(refused)

    expect(undone.refusal).toBeNull()
    expect(undone.points).toHaveLength(1)
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
    expect(status.route.legs.map((leg) => leg.name)).toEqual([
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
    expect(draftRoute(index, across)).toBeNull()
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
    const out = draftRoute(index, two)
    const loop = draftRoute(index, loopDraft(two))

    expect(out).not.toBeNull()
    expect(loop).not.toBeNull()
    expect(loop?.miles).toBeCloseTo((out?.miles ?? 0) * 2, 5)
  })

  it('reopens when the hiker taps again, rather than appending after the return leg', () => {
    const looped = loopDraft(tapAt(index, tapAt(index, EMPTY_DRAFT, ON_TRAIL), FURTHER))
    const reopened = tapAt(index, looped, UP_SEVEN_HILLS)

    expect(reopened.looped).toBe(false)
    expect(reopened.points).toHaveLength(3)
  })
})

describe('clearing', () => {
  it('goes back to empty', () => {
    expect(clearDraft()).toEqual(EMPTY_DRAFT)
  })
})
