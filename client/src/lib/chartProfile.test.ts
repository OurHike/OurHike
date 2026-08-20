import { describe, it, expect } from 'vitest'
import {
  clampDomain,
  envelopeSamples,
  fullDomain,
  MIN_DOMAIN_SPAN_MI,
  nearestMile,
  sampleAtMile,
  tickStep,
  ticks,
} from './chartProfile'
import type { ElevationProfile } from './elevationProfile'

// The decimation's one promise is the one worth testing hard: a summit or a
// notch inside a bucket survives at its true elevation. Everything else here
// is edges - gaps, tiny windows, the clamp at the terminuses.

function profileOf(samples: Array<[number, number]>): ElevationProfile {
  const distanceMi = new Float32Array(samples.length)
  const elevationFt = new Float32Array(samples.length)
  samples.forEach(([mile, ft], i) => {
    distanceMi[i] = mile
    elevationFt[i] = ft
  })
  return { distanceMi, elevationFt }
}

/** A long flat profile with named extremes: a spike up at mile 40 and a
 *  notch down at mile 60, each a single sample wide - exactly what naive
 *  averaging would erase. */
function flatWithExtremes(): ElevationProfile {
  const samples: Array<[number, number]> = []
  for (let i = 0; i <= 10000; i += 1) {
    const mile = i / 100
    let ft = 1000
    if (mile === 40) ft = 5000
    if (mile === 60) ft = 200
    samples.push([mile, ft])
  }
  return profileOf(samples)
}

describe('fullDomain', () => {
  it('spans first to last sample', () => {
    const profile = profileOf([
      [3, 1000],
      [5, 1200],
      [9, 900],
    ])
    expect(fullDomain(profile)).toEqual({ startMile: 3, endMile: 9 })
  })

  it('is null for an empty profile', () => {
    expect(fullDomain(profileOf([]))).toBeNull()
  })
})

describe('clampDomain', () => {
  const profile = flatWithExtremes() // miles 0..100

  it('normalises a reversed request', () => {
    expect(clampDomain({ startMile: 30, endMile: 10 }, profile)).toEqual({
      startMile: 10,
      endMile: 30,
    })
  })

  it('widens a too-narrow request around its centre', () => {
    const domain = clampDomain({ startMile: 50, endMile: 50.2 }, profile)
    expect(domain).not.toBeNull()
    expect(domain!.endMile - domain!.startMile).toBeCloseTo(MIN_DOMAIN_SPAN_MI, 6)
    expect((domain!.startMile + domain!.endMile) / 2).toBeCloseTo(50.1, 6)
  })

  it('slides rather than shrinks against the terminus', () => {
    const domain = clampDomain({ startMile: 99.5, endMile: 99.9 }, profile)
    expect(domain).toEqual({ startMile: 100 - MIN_DOMAIN_SPAN_MI, endMile: 100 })
  })

  it('returns the whole profile when the profile is shorter than the minimum span', () => {
    const short = profileOf([
      [0, 1000],
      [1, 1100],
    ])
    expect(clampDomain({ startMile: 0.4, endMile: 0.5 }, short)).toEqual({
      startMile: 0,
      endMile: 1,
    })
  })
})

describe('envelopeSamples', () => {
  it('keeps a one-sample spike and a one-sample notch at their true elevations', () => {
    const profile = flatWithExtremes()
    const drawn = envelopeSamples(profile, { startMile: 0, endMile: 100 }, 200)

    // 10,001 samples into 200 buckets: heavily decimated...
    expect(drawn.length).toBeLessThan(450)
    // ...and both extremes survive exactly.
    expect(drawn.some((s) => s.elevationFt === 5000)).toBe(true)
    expect(drawn.some((s) => s.elevationFt === 200)).toBe(true)
  })

  it('emits bucket extremes in the order they occur along the trail', () => {
    const profile = flatWithExtremes()
    const drawn = envelopeSamples(profile, { startMile: 0, endMile: 100 }, 200)
    for (let i = 1; i < drawn.length; i += 1) {
      expect(drawn[i].mile).toBeGreaterThanOrEqual(drawn[i - 1].mile)
    }
  })

  it('returns raw samples when the window is small enough to draw whole', () => {
    const profile = flatWithExtremes()
    const drawn = envelopeSamples(profile, { startMile: 40, endMile: 41 }, 200)
    // 101 samples in the window, well under 2 per bucket: all of them, as-is.
    expect(drawn.length).toBe(101)
    expect(drawn[0].mile).toBeCloseTo(40, 5)
  })

  it('drops DEM gaps from the drawing', () => {
    const profile = profileOf([
      [0, 1000],
      [1, Number.NaN],
      [2, 1200],
    ])
    const drawn = envelopeSamples(profile, { startMile: 0, endMile: 2 }, 10)
    expect(drawn).toEqual([
      { mile: 0, elevationFt: 1000 },
      { mile: 2, elevationFt: 1200 },
    ])
  })

  it('is empty for an empty or inverted domain', () => {
    const profile = flatWithExtremes()
    expect(envelopeSamples(profile, { startMile: 50, endMile: 50 }, 10)).toEqual([])
  })
})

describe('sampleAtMile', () => {
  const profile = profileOf([
    [0, 1000],
    [1, 1100],
    [2, Number.NaN],
    [3, 1300],
  ])

  it('answers the nearest sample', () => {
    expect(sampleAtMile(profile, 0.9)).toEqual({ mile: 1, elevationFt: 1100 })
  })

  it('clamps beyond the ends', () => {
    expect(sampleAtMile(profile, -5)).toEqual({ mile: 0, elevationFt: 1000 })
    expect(sampleAtMile(profile, 99)).toEqual({ mile: 3, elevationFt: 1300 })
  })

  it('answers null over a DEM gap rather than the nearest measured neighbour', () => {
    expect(sampleAtMile(profile, 2.1)).toBeNull()
  })

  it('answers null for an empty profile', () => {
    expect(sampleAtMile(profileOf([]), 1)).toBeNull()
  })
})

describe('nearestMile', () => {
  const profile = profileOf([
    [0, 1000],
    [1, 1100],
    [2, Number.NaN],
    [3, 1300],
  ])

  it('snaps to the nearest sample position, gaps included', () => {
    expect(nearestMile(profile, 0.9)).toBe(1)
    // Unlike sampleAtMile, a gap is still a POSITION on the axis.
    expect(nearestMile(profile, 2.1)).toBe(2)
  })

  it('clamps beyond the ends and is null when empty', () => {
    expect(nearestMile(profile, -4)).toBe(0)
    expect(nearestMile(profile, 40)).toBe(3)
    expect(nearestMile(profileOf([]), 1)).toBeNull()
  })
})

describe('tickStep and ticks', () => {
  it('yields 4-8 ticks across representative spans', () => {
    for (const span of [2, 10, 60, 100, 500, 2197]) {
      const step = tickStep(span)
      const count = Math.floor(span / step)
      expect(count).toBeGreaterThanOrEqual(4)
      expect(count).toBeLessThanOrEqual(8)
    }
  })

  it('places ticks on round multiples inside the range', () => {
    expect(ticks(0, 2197, 500)).toEqual([0, 500, 1000, 1500, 2000])
    expect(ticks(443.2, 500, 10)).toEqual([450, 460, 470, 480, 490, 500])
  })

  it('keeps float error out of the labels', () => {
    for (const tick of ticks(0, 2100, 300)) {
      expect(Number.isInteger(tick)).toBe(true)
    }
  })
})
