import { expect, it } from 'vitest'
import { fixtureSites } from './fixtures'
import { needUnder, rerank, tierFor } from './ranking'
import type { Site } from './types'

const TIERS = { P1_min: 60, P2_min: 50 }
const DEFAULTS = { deficit: 60, water: 12, trail: 6, cluster: 8, restricted: 10 }

it('needUnder is the weighted sum of need_parts, clamped to 0-100', () => {
  const site = {
    need: 0,
    need_parts: { deficit: 21 / 27, water: 0.5, trail: 1, cluster: 0.5, restricted: 0 },
  } as Site
  const club = { deficit: 40, water: 20, trail: 0, cluster: 16, restricted: 10 }
  expect(needUnder(site, club)).toBe(Math.floor((40 * 21) / 27 + 10 + 8 + 0.5))
  expect(needUnder(site, { ...club, deficit: 100, water: 100, trail: 100 })).toBe(100)
})

it('needUnder rounds a half up, as the analysis job does, not to even', () => {
  // A water weight of 13, half of it: 6.5 is 7 in both places.
  const site = {
    need: 0,
    need_parts: { deficit: 0, water: 0.5, trail: 0, cluster: 0, restricted: 0 },
  } as Site
  expect(needUnder(site, { ...DEFAULTS, water: 13 })).toBe(7)
})

it('needUnder keeps the published need for a site with no parts', () => {
  expect(
    needUnder({ need: 42, need_parts: null } as Site, { ...DEFAULTS, deficit: 0 }),
  ).toBe(42)
})

it('under the default weights, every invented site keeps its need', () => {
  for (const site of fixtureSites) expect(needUnder(site, DEFAULTS)).toBe(site.need)
})

it('tierFor gives tiers only to sites that need work', () => {
  expect(tierFor(70, 'close_restore', TIERS)).toBe('P1')
  expect(tierFor(55, 'harden', TIERS)).toBe('P2')
  expect(tierFor(10, 'close_restore', TIERS)).toBe('P3')
  expect(tierFor(90, 'monitor', TIERS)).toBeNull()
})

it('rerank changes need and tier and leaves the input sites untouched', () => {
  const before = fixtureSites.map((s) => s.need)
  const flat = rerank(
    fixtureSites,
    { deficit: 0, water: 0, trail: 0, cluster: 0, restricted: 0 },
    TIERS,
  )
  expect(flat.every((s) => s.need === 0)).toBe(true)
  expect(fixtureSites.map((s) => s.need)).toEqual(before)
})
