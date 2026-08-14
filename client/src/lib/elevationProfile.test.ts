// Tests for elevationProfile.ts.
//
// Two things here are load-bearing beyond "does it parse".
//
// DEM coverage gaps have to survive into the gain calculation and have to NOT
// survive into the SVG. ElevationRibbon takes Math.min of the elevations it is
// given, so a single NaN there turns the whole path into NaN and the ribbon
// renders as nothing at all - a blank strip where a profile should be, with no
// error anywhere. The gain calculation needs the opposite: a gap that is
// stepped over silently joins two samples that may be a mile apart and counts
// that step as a climb nobody made.
//
// And the window is asymmetric on purpose (features/ELEVATION_PROFILE.md).
// Getting it backwards for a southbounder would show them the ground they have
// already walked, which is the one direction of error that is useless rather
// than merely imperfect.

import { describe, it, expect } from 'vitest'
import {
  parseProfile,
  profileSamples,
  ribbonSamples,
  ribbonWindow,
  WINDOW_BEHIND_MI,
  WINDOW_SPAN_MI,
  type ElevationProfile,
} from './elevationProfile'
import { gainBetween } from './elevationGain'

/** A profile from (mile, ft) pairs, with null standing for a DEM gap. */
function profileOf(points: Array<[number, number | null]>): ElevationProfile {
  return {
    distanceMi: Float32Array.from(points.map(([mile]) => mile)),
    elevationFt: Float32Array.from(
      points.map(([, ft]) => (ft === null ? Number.NaN : ft)),
    ),
  }
}

/** A flat profile from mile 0 to `miles`, one sample per mile. */
function flatProfile(miles: number): ElevationProfile {
  return profileOf(Array.from({ length: miles + 1 }, (_, i) => [i, 1000]))
}

function published(records: Array<Record<string, unknown>>): string {
  return JSON.stringify(records)
}

describe('parseProfile', () => {
  it('reads the published records into parallel arrays', () => {
    const profile = parseProfile(
      published([
        { distance_mi: 0, elevation_ft: 3782.2 },
        { distance_mi: 0.016, elevation_ft: 3775.1 },
      ]),
    )

    expect(Array.from(profile?.distanceMi ?? [])).toEqual([0, expect.closeTo(0.016, 4)])
    expect(Array.from(profile?.elevationFt ?? [])).toEqual([
      expect.closeTo(3782.2, 3),
      expect.closeTo(3775.1, 3),
    ])
  })

  it('keeps a DEM gap as a gap rather than dropping the sample', () => {
    // Dropping it would join the samples either side into one step and count
    // that step as a climb nobody made.
    const profile = parseProfile(
      published([
        { distance_mi: 0, elevation_ft: 1000 },
        { distance_mi: 1, elevation_ft: null },
        { distance_mi: 2, elevation_ft: 2000 },
      ]),
    )

    expect(profile?.distanceMi.length).toBe(3)
    expect(Number.isNaN(profile?.elevationFt[1] ?? 0)).toBe(true)
  })

  it('drops a sample with no distance, which cannot be placed on the axis', () => {
    const profile = parseProfile(
      published([{ elevation_ft: 1000 }, { distance_mi: 1, elevation_ft: 2000 }]),
    )

    expect(profile?.distanceMi.length).toBe(1)
    expect(profile?.distanceMi[0]).toBe(1)
  })

  it.each([
    ['a body that is not an array', '{"samples":[]}'],
    ['a truncated download', '[{"distance_mi":0,'],
    ['an empty array', '[]'],
    ['an array of nothing usable', '[{"nope":1}]'],
  ])('gives back nothing for %s rather than throwing', (_case, text) => {
    // The ribbon is a decoration on a screen whose job is showing a hiker where
    // they are. A profile that arrives broken should cost itself and not the
    // map it was downloaded beside.
    expect(parseProfile(text)).toBeNull()
  })
})

describe('ribbonWindow', () => {
  const profile = flatProfile(2200)

  it('looks nine miles ahead and one behind for a northbounder', () => {
    const window = ribbonWindow(profile, 1000, 'NOBO')

    expect(window.startMile).toBeCloseTo(999)
    expect(window.endMile).toBeCloseTo(1009)
  })

  it('mirrors for a southbounder, whose ahead is a decreasing mile', () => {
    const window = ribbonWindow(profile, 1000, 'SOBO')

    expect(window.startMile).toBeCloseTo(991)
    expect(window.endMile).toBeCloseTo(1001)
  })

  it('centres the window while the direction is still unknown', () => {
    // lib/hikeDirection.ts withholds the direction until a quarter mile of
    // movement. Assuming NOBO for that stretch would be a confident-looking
    // answer that is wrong for half of everyone.
    const window = ribbonWindow(profile, 1000, undefined)

    expect(window.startMile).toBeCloseTo(995)
    expect(window.endMile).toBeCloseTo(1005)
  })

  it('always spans the same distance, whichever way the hiker faces', () => {
    for (const direction of ['NOBO', 'SOBO', undefined] as const) {
      const window = ribbonWindow(profile, 1000, direction)
      expect(window.endMile - window.startMile).toBeCloseTo(WINDOW_SPAN_MI)
    }
  })

  it('slides rather than shrinks at the southern terminus', () => {
    // Standing on Springer there is no mile behind you, and a ribbon that
    // shrank to nine miles would be a narrower picture at exactly the moment
    // the whole trail is ahead.
    const window = ribbonWindow(profile, 0.2, 'NOBO')

    expect(window.startMile).toBeCloseTo(0)
    expect(window.endMile).toBeCloseTo(WINDOW_SPAN_MI)
  })

  it('slides rather than shrinks at the northern terminus', () => {
    const window = ribbonWindow(profile, 2199.5, 'NOBO')

    expect(window.startMile).toBeCloseTo(2200 - WINDOW_SPAN_MI)
    expect(window.endMile).toBeCloseTo(2200)
  })

  it('draws a profile shorter than the window whole', () => {
    const window = ribbonWindow(flatProfile(4), 2, 'NOBO')

    expect(window.startMile).toBeCloseTo(0)
    expect(window.endMile).toBeCloseTo(4)
  })

  it('puts the hiker inside the window rather than on its edge', () => {
    // The "you are here" rule needs somewhere to be. Against the left edge on
    // every frame it indicates nothing.
    const window = ribbonWindow(profile, 1000, 'NOBO')

    expect(1000 - window.startMile).toBeCloseTo(WINDOW_BEHIND_MI)
  })
})

describe('profileSamples', () => {
  const profile = profileOf([
    [0, 1000],
    [1, 1100],
    [2, null],
    [3, 1300],
    [4, 1400],
  ])

  it('takes the window inclusive of both bounds', () => {
    const samples = profileSamples(profile, { startMile: 1, endMile: 3 })

    expect(samples.map((s) => s.distanceMi)).toEqual([1, 2, 3])
  })

  it('hands the gain calculation its gaps, which is what breaks the run', () => {
    const samples = profileSamples(profile, { startMile: 0, endMile: 4 })

    expect(samples[2].elevationFt).toBeNull()
  })
})

describe('ribbonSamples', () => {
  it('drops gaps, because one NaN blanks the entire SVG path', () => {
    const profile = profileOf([
      [0, 1000],
      [1, null],
      [2, 1200],
    ])

    const samples = ribbonSamples(profile, { startMile: 0, endMile: 2 })

    expect(samples).toEqual([
      { mile: 0, elevationFt: 1000 },
      { mile: 2, elevationFt: 1200 },
    ])
  })

  it('gives back nothing when the window is entirely uncovered', () => {
    // The honest state is the same as having no profile at all, and App.tsx
    // omits the ribbon rather than drawing an empty one.
    const profile = profileOf([
      [0, null],
      [1, null],
    ])

    expect(ribbonSamples(profile, { startMile: 0, endMile: 1 })).toEqual([])
  })
})

// --- centerline seams (#559) ------------------------------------------------

describe('part boundaries', () => {
  it('carries part_start through to the samples ascent is counted over', () => {
    const profile = parseProfile(
      JSON.stringify([
        { distance_mi: 0, elevation_ft: 100 },
        { distance_mi: 0.1, elevation_ft: 110 },
        { distance_mi: 0.2, elevation_ft: 3000, part_start: true },
      ]),
    )

    const samples = profileSamples(profile!, { startMile: 0, endMile: 1 })
    expect(samples.map((s) => s.partStart)).toEqual([false, false, true])
  })

  it('reads a profile with no markers as having no seams', () => {
    // An artifact published before the pipeline recorded them. The file does
    // not say where its seams are, so nothing may be assumed about them.
    const profile = parseProfile(
      JSON.stringify([
        { distance_mi: 0, elevation_ft: 100 },
        { distance_mi: 0.1, elevation_ft: 3000 },
      ]),
    )

    const samples = profileSamples(profile!, { startMile: 0, endMile: 1 })
    expect(samples.map((s) => s.partStart)).toEqual([false, false])
  })

  it('survives a profile restored from a download that predates the field', () => {
    // lib/storedShapes.fixtures.ts' storedElevation() is exactly this shape.
    // Requiring partStart would throw on every early tester's archive.
    const stored = {
      distanceMi: Float32Array.from([0, 0.1, 0.2]),
      elevationFt: Float32Array.from([100, 110, 3000]),
    }

    const samples = profileSamples(stored, { startMile: 0, endMile: 1 })

    expect(samples).toHaveLength(3)
    expect(samples.every((s) => s.partStart === false)).toBe(true)
  })

  it('does not sum the step into a seam as a climb', () => {
    const profile = parseProfile(
      JSON.stringify([
        { distance_mi: 0, elevation_ft: 100 },
        { distance_mi: 0.1, elevation_ft: 110 },
        { distance_mi: 0.2, elevation_ft: 3000, part_start: true },
        { distance_mi: 0.3, elevation_ft: 3010 },
      ]),
    )

    const samples = profileSamples(profile!, { startMile: 0, endMile: 1 })
    expect(gainBetween(samples, 0, 1)).toBeCloseTo(20)
  })
})
