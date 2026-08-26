// Tests for lib/dayHikeWalk.ts - a saved hike flattened into the pieces of
// trail a hiker actually covers (#1041).
//
// The rule worth a suite is the one lib/dayHikeCard.ts already states from
// the other end: an out-and-back walks parts of an edge TWICE, and the two
// passes are different moments in the day. A walk that held each edge once
// would put a hiker on the way home at the mile they passed on the way out.

import { describe, expect, it } from 'vitest'

import { resolveDayHike } from './dayHikeCard'
import { dayHikeWalk, walkMiles } from './dayHikeWalk'
import {
  EAST_END,
  NETWORK,
  NORTH_END,
  WEST_END,
  hikeThrough,
} from './dayHikeWalk.fixtures'
import { buildGraphIndex, metresToMiles } from './trailGraph'

function walkFor(hike = hikeThrough([WEST_END, NORTH_END])) {
  const index = buildGraphIndex(NETWORK)
  const resolved = resolveDayHike(index, hike)
  expect(resolved).not.toBeNull()
  return dayHikeWalk(index, resolved!)
}

describe('dayHikeWalk', () => {
  it('is one traversal per edge, in walking order, with the metres before each', () => {
    const steps = walkFor()

    expect(steps.map((step) => step.edgeIndex)).toEqual([0, 2])
    expect(steps[0].beforeMetres).toBe(0)
    expect(steps[0].metres).toBeCloseTo(836, 6)
    expect(steps[1].beforeMetres).toBeCloseTo(836, 6)
  })

  it('marks only the boundaries that are junctions', () => {
    const steps = walkFor()

    // The first traversal ends where the two edges meet; the last ends at
    // the hiker's own tap, which #934's split-the-segment rule puts mid-edge
    // and which is not a place with a choice at it.
    expect(steps[0].junctionNode).toBe(1)
    expect(steps[1].junctionNode).toBeNull()
  })

  it('keeps both passes of an out-and-back, at their own miles', () => {
    const steps = walkFor(hikeThrough([WEST_END, EAST_END, WEST_END]))

    expect(steps.map((step) => step.edgeIndex)).toEqual([0, 1, 1, 0])
    // Edge 0 twice, 2,508 m apart - which is the whole walk out and back
    // again minus the piece itself.
    expect(steps[0].beforeMetres).toBeCloseTo(0, 6)
    expect(steps[3].beforeMetres).toBeCloseTo(2508, 6)
    expect(walkMiles(steps)).toBeCloseTo(metresToMiles(3344), 6)
  })

  it('records which way each edge is walked, so bearings can be read', () => {
    const steps = walkFor(hikeThrough([WEST_END, EAST_END, WEST_END]))

    // Out along both edges in their published direction, home against it.
    expect(steps.map((step) => step.forward)).toEqual([true, true, false, false])
    expect(steps[3].startFraction).toBe(1)
    expect(steps[3].endFraction).toBe(0)
  })
})
