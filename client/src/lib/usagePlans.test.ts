import { describe, expect, it } from 'vitest'

import { DEFAULT_TRAIL_ID, type Hike } from './hikes'
import type { HikePlan } from './plan'
import { hikeExtent, planExtent } from './usagePlans'

// How far a plan reaches, as usage measurement splits it across clubs (#1902).

describe('planExtent', () => {
  it('reads a trip from its first stop to its last on the mile axis', () => {
    const plan = {
      target: { miles: 12 },
      stops: [
        { mile: 1410.2, resupply: false },
        { mile: 1396.0, resupply: false },
        { mile: 1388.5, resupply: false },
      ],
      days: [],
    } as unknown as HikePlan

    expect(planExtent(plan)).toEqual({ fromMile: 1388.5, toMile: 1410.2 })
  })
})

describe('hikeExtent', () => {
  const points = [{ mile: 1000 }, { mile: 1250 }, { mile: 1100 }]

  it('reads a long hike on the A.T. from its points’ miles', () => {
    const hike = { trailId: DEFAULT_TRAIL_ID, points } as unknown as Hike

    expect(hikeExtent(hike)).toEqual({ fromMile: 1000, toMile: 1250 })
  })

  it('gives a hike on a trail with no mile axis no stretch, and so no club', () => {
    const hike = { trailId: 'some-other-trail', points } as unknown as Hike

    expect(hikeExtent(hike)).toEqual({})
  })
})
