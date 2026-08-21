import { describe, it, expect } from 'vitest'
import { MAX_LANE_SPAN_MI, planLanes, planRibbon } from './planRibbon'
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

// The lanes over the same stretch. What is worth testing here is which mile a
// pin is placed from, which window it is placed in, and the two states where
// no lanes at all is the honest answer.
describe('planLanes', () => {
  const shelter = (id: string, mile?: number) => ({ id, type: 'shelter', ...{ mile } })

  function laneRibbon(startMile: number, endMile: number) {
    return planRibbon(longProfile(), { startMile, endMile }, null)
  }

  it('keeps the POIs on the stretch and leaves out the ones off it', () => {
    const lanes = planLanes(laneRibbon(10, 30), [
      shelter('before', 9.5),
      shelter('start', 10),
      shelter('middle', 20),
      shelter('end', 30),
      shelter('after', 30.5),
    ])

    expect(lanes?.points.map((p) => p.id)).toEqual(['start', 'middle', 'end'])
  })

  it('places a pin from the published mile, and skips a POI that has none', () => {
    // The pipeline's mile (#753) is the axis this ribbon is drawn on. A POI
    // from a download that predates it has no position here at all - and is
    // left out rather than given one from the client index, which measures
    // the same trail differently (HIKE_PLANNING.md Finding 1).
    const lanes = planLanes(laneRibbon(10, 30), [
      shelter('placed', 15),
      shelter('unplaceable'),
      { id: 'spring', type: 'water', mile: 16 },
    ])

    expect(lanes?.points).toEqual([
      { id: 'placed', type: 'shelter', mile: 15 },
      { id: 'spring', type: 'water', mile: 16 },
    ])
  })

  it('windows the lanes on the ribbon’s own domain, not on its samples', () => {
    // The samples stop up to a sample spacing short of the stretch's end, so
    // a lane windowed on them drops the stop the route is walking TO.
    // A destination between two samples, which is where a real one falls: the
    // profile is sampled every 25 m and a shelter is where it is.
    const ribbon = laneRibbon(10, 30.005)
    const lanes = planLanes(ribbon, [shelter('destination', 30.005)])

    expect(lanes?.startMile).toBe(10)
    expect(lanes?.endMile).toBe(30.005)
    expect(ribbon!.samples[ribbon!.samples.length - 1].mile).toBeLessThan(30.005)
    expect(lanes?.points.map((p) => p.id)).toEqual(['destination'])
  })

  it('draws empty lanes for a stretch that genuinely holds nothing', () => {
    // Emptiness that is a fact about the trail, not about the download - the
    // lanes are drawn and say so by being empty.
    const lanes = planLanes(laneRibbon(10, 30), [shelter('far', 80)])

    expect(lanes?.points).toEqual([])
  })

  it('refuses when nothing in the download carries a published mile', () => {
    // Empty lanes here would be the screen reporting "nothing along this
    // stretch" about POIs it cannot place. A pre-#753 download gets no lanes.
    expect(planLanes(laneRibbon(10, 30), [shelter('a'), shelter('b')])).toBeUndefined()
  })

  it('refuses without a ribbon to sit under', () => {
    expect(planLanes(undefined, [shelter('a', 12)])).toBeUndefined()
  })

  it('drops the lanes on a stretch too long for a pin to name a place', () => {
    // MAX_LANE_SPAN_MI is where a pill swallows the eight miles Decision 1
    // measures between shelters. Either side of it, deliberately.
    const wide = profileOf(
      Array.from({ length: 1201 }, (_, i) => [i, 1000] as [number, number]),
    )
    const under = planRibbon(wide, { startMile: 0, endMile: MAX_LANE_SPAN_MI - 10 }, null)
    const over = planRibbon(wide, { startMile: 0, endMile: MAX_LANE_SPAN_MI + 10 }, null)

    expect(planLanes(under, [shelter('a', 12)])).toBeDefined()
    expect(planLanes(over, [shelter('a', 12)])).toBeUndefined()
  })
})
