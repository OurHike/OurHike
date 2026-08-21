import { describe, it, expect } from 'vitest'
import { planRibbon } from './planRibbon'
import { ENVELOPE_BUCKETS } from './chartProfile'
import type { ElevationProfile } from './elevationProfile'

// What this module has to get right is not the drawing - envelopeSamples is
// tested next door - but the three refusals and the one claim:
//
//   refuse   no profile, no stretch, a stretch with no width, a stretch that
//            is entirely DEM gap. Every one of those has to come back
//            undefined, because MapScreen draws an empty ribbon otherwise and
//            an empty ribbon reads as "no terrain here".
//   claim    the "you are here" rule, which appears only when the fix is
//            genuinely on the planned stretch.

function profileOf(samples: Array<[number, number | null]>): ElevationProfile {
  const distanceMi = new Float32Array(samples.length)
  const elevationFt = new Float32Array(samples.length)
  samples.forEach(([mile, ft], i) => {
    distanceMi[i] = mile
    elevationFt[i] = ft === null ? Number.NaN : ft
  })
  return { distanceMi, elevationFt }
}

/** 100 miles at the profile's own 25 m spacing, near enough - one sample
 *  every 0.01 mi, so a stretch of it is thousands of samples. */
function longProfile(): ElevationProfile {
  const samples: Array<[number, number | null]> = []
  for (let i = 0; i <= 10000; i += 1) {
    samples.push([i / 100, 1000 + Math.sin(i / 50) * 500])
  }
  return profileOf(samples)
}

describe('planRibbon', () => {
  it('draws the stretch the route draft covers', () => {
    const ribbon = planRibbon(longProfile(), { startMile: 10, endMile: 30 }, null)

    expect(ribbon).toBeDefined()
    const samples = ribbon!.samples
    expect(samples[0].mile).toBeCloseTo(10, 2)
    expect(samples[samples.length - 1].mile).toBeCloseTo(30, 2)
    expect(ribbon!.subject).toBe('planned-stretch')
  })

  it('reads a stretch given end-first the same way as start-first', () => {
    const profile = longProfile()
    const south = planRibbon(profile, { startMile: 30, endMile: 10 }, null)
    const north = planRibbon(profile, { startMile: 10, endMile: 30 }, null)

    // A SOBO draft's stops arrive in walk order, which puts the larger mile
    // first. The ribbon is a picture of ground, and ground has no direction.
    expect(south?.samples).toEqual(north?.samples)
  })

  it('refuses without a profile, without a stretch, and on a zero-width one', () => {
    expect(planRibbon(null, { startMile: 10, endMile: 30 }, null)).toBeUndefined()
    expect(planRibbon(longProfile(), null, null)).toBeUndefined()
    expect(
      planRibbon(longProfile(), { startMile: 12, endMile: 12 }, null),
    ).toBeUndefined()
  })

  it('refuses a stretch the DEM never covered rather than drawing a blank', () => {
    const gap = profileOf([
      [10, 1000],
      [20, null],
      [21, null],
      [22, null],
      [40, 1200],
    ])

    // One surviving sample is a dot, not a shape - and a ribbon showing a dot
    // over a 2-mile plan says "flat" about ground nobody measured.
    expect(planRibbon(gap, { startMile: 20, endMile: 22 }, null)).toBeUndefined()
  })

  it('marks the hiker only when the fix is on the stretch being planned', () => {
    const profile = longProfile()

    expect(planRibbon(profile, { startMile: 10, endMile: 30 }, 22)?.currentMile).toBe(22)
    expect(
      planRibbon(profile, { startMile: 10, endMile: 30 }, 74)?.currentMile,
    ).toBeNull()
    expect(
      planRibbon(profile, { startMile: 10, endMile: 30 }, null)?.currentMile,
    ).toBeNull()
  })

  it('decimates a stretch too long to draw sample by sample', () => {
    // 90 miles at 0.01 mi spacing is ~9,000 samples. Handing every one of them
    // to an SVG path is the honesty problem lib/chartProfile.ts describes, not
    // just a cost one: what survives is decided by paint order.
    const ribbon = planRibbon(longProfile(), { startMile: 5, endMile: 95 }, null)

    expect(ribbon!.samples.length).toBeLessThanOrEqual(ENVELOPE_BUCKETS * 2)
  })

  it('keeps the real samples on a stretch short enough to draw whole', () => {
    // A three-mile plan is 300 samples here. Nothing is decimated, so the
    // drawn line is the measurements rather than an envelope of them.
    const ribbon = planRibbon(longProfile(), { startMile: 40, endMile: 43 }, null)

    expect(ribbon!.samples).toHaveLength(301)
  })
})
