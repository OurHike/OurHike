// Tests for elevationGain.ts.
//
// Why this exists
// ---------------
// Summing every rise in the 25 m elevation profile over-counts the full AT by
// ~17% - 594,520 ft against a ~510,000 ft consensus. The profile is right; the
// sum is wrong, because summing is the one operation that turns DEM
// measurement error into signal. That number feeds naismith.ts, so it is a
// hiking time estimate that is wrong, not just a figure on a screen.
//
// Two ways to be wrong, and both are held at once below:
//   - count the noise, and every estimate downstream inflates;
//   - reject it with something that also shaves real climbs, and steep
//     pitches get under-counted exactly where a hiker wants them counted.
//
// The shared-vector block at the bottom is the load-bearing part. The same
// algorithm lives in pipeline/lib/elevation_gain.py, and two implementations
// of one number drift the first time someone fixes an edge case in one
// language without opening the other file. Both suites read one JSON table,
// so that is a failing test rather than a silent disagreement.

import { describe, expect, it } from 'vitest'

import { readRepoFile } from '../test/repoFile'

import {
  cumulativeGain,
  cumulativeGainOverGaps,
  cumulativeGainOverProfile,
  cumulativeLossOverGaps,
  cumulativeLossOverProfile,
  gainBetween,
  lossBetween,
  rawCumulativeGain,
  reverseProfileWindow,
  THRESHOLD_FT,
  THRESHOLD_M,
  type ProfileSample,
} from './elevationGain'

const T = 3

describe('real climbs are counted at their real size', () => {
  it('counts a single climb whole', () => {
    expect(cumulativeGain([100, 200, 300, 400], T)).toBeCloseTo(300)
  })

  it('does not shave a climb by the threshold it was filtered with', () => {
    // The failure mode of the obvious implementation: carrying a running
    // reference and adding whenever it moves past the threshold loses up to
    // one threshold at the top of every climb.
    expect(cumulativeGain([0, 500, 0, 500, 0, 500], T)).toBeCloseTo(1500)
  })

  it('counts a gentle climb whose every step is under the threshold', () => {
    const profile = Array.from({ length: 101 }, (_, i) => i)
    expect(cumulativeGain(profile, T)).toBeCloseTo(100)
  })

  it('counts a climb the window ends on', () => {
    expect(cumulativeGain([0, 100, 50, 400], T)).toBeCloseTo(450)
  })

  it('measures from the true low rather than the first sample', () => {
    expect(cumulativeGain([100, 98, 500], T)).toBeCloseTo(402)
  })
})

describe('noise is not climbing', () => {
  it('finds no gain in flat ground with DEM jitter', () => {
    expect(cumulativeGain([1000, 1000.4, 999.3, 1000.2, 999.7, 1000.6, 999.5], T)).toBe(0)
  })

  it('drops a swing just under the threshold whole', () => {
    expect(cumulativeGain([100, 102.9, 100, 102.9, 100], T)).toBe(0)
  })

  it('keeps a swing just over the threshold whole', () => {
    expect(cumulativeGain([100, 103.1, 100, 103.1], T)).toBeCloseTo(6.2)
  })

  it('does not let denser sampling manufacture more climbing', () => {
    // Why "sample more finely" is not the fix. On the same flat ground,
    // doubling the samples doubles the fake gain, forever.
    const coarse = Array.from({ length: 100 }, (_, i) => 1000 + (i % 2 ? -0.4 : 0.3))
    const fine = Array.from({ length: 200 }, (_, i) => 1000 + (i % 2 ? -0.4 : 0.3))

    expect(rawCumulativeGain(fine)).toBeGreaterThan(1.9 * rawCumulativeGain(coarse))
    expect(cumulativeGain(fine, T)).toBe(0)
    expect(cumulativeGain(coarse, T)).toBe(0)
  })
})

describe('DEM coverage gaps', () => {
  it('does not bridge a gap into a climb nobody made', () => {
    expect(cumulativeGainOverGaps([100, 110, null, 3000, 3010], T)).toBeCloseTo(20)
  })

  it('still measures each side of a gap', () => {
    expect(cumulativeGainOverGaps([0, 500, null, 0, 500], T)).toBeCloseTo(1000)
  })

  it('treats a NaN the same as a null', () => {
    // A profile parsed from JSON can produce one; counting NaN as an
    // elevation poisons the whole running total to NaN, which then renders
    // as an empty ascent figure rather than as an error.
    expect(cumulativeGainOverGaps([100, 110, NaN, 3000, 3010], T)).toBeCloseTo(20)
  })
})

describe('windowing', () => {
  const profile: ProfileSample[] = [
    { distanceMi: 0, elevationFt: 1000 },
    { distanceMi: 1, elevationFt: 2000 },
    { distanceMi: 2, elevationFt: 1000 },
    { distanceMi: 3, elevationFt: 2000 },
  ]

  it('uses only the requested window', () => {
    expect(gainBetween(profile, 0, 1)).toBeCloseTo(1000)
    expect(gainBetween(profile, 0, 3)).toBeCloseTo(2000)
  })

  it('has no gain for a window too short to hold two samples', () => {
    // On a 25 m profile, asking about the next tenth of a mile is a
    // reasonable question that happens to select one sample.
    expect(gainBetween(profile, 0, 0.01)).toBe(0)
  })

  it('defaults to the shared threshold', () => {
    expect(THRESHOLD_FT * 0.3048).toBeCloseTo(THRESHOLD_M)
  })
})

describe('shared with the Python implementation', () => {
  interface Vector {
    name: string
    elevations: (number | null)[]
    threshold: number
    expected_gain: number
  }

  interface BoundaryVector {
    name: string
    samples: { elevation_ft: number | null; part_start?: boolean }[]
    threshold: number
    expected_gain: number
  }

  // Through test/repoFile.ts, which declares this out-of-tree read so
  // ciScope.test.ts can hold the CI scope list to it (#503).
  const vectors = JSON.parse(readRepoFile('pipeline/reference/gain_vectors.json')) as {
    cases: Vector[]
    gap_cases: Vector[]
    boundary_cases: BoundaryVector[]
  }

  it('has vectors to run', () => {
    // A vector file that silently emptied would turn every case below into
    // zero cases, and a suite that runs nothing passes.
    expect(vectors.cases.length).toBeGreaterThanOrEqual(10)
    expect(vectors.gap_cases.length).toBeGreaterThanOrEqual(3)
    expect(vectors.boundary_cases.length).toBeGreaterThanOrEqual(5)
  })

  it.each(vectors.cases)('$name', ({ elevations, threshold, expected_gain }) => {
    expect(cumulativeGain(elevations as number[], threshold)).toBeCloseTo(expected_gain)
  })

  it.each(vectors.gap_cases)('$name', ({ elevations, threshold, expected_gain }) => {
    expect(cumulativeGainOverGaps(elevations, threshold)).toBeCloseTo(expected_gain)
  })

  // #559's break, and the reason these carry `samples` rather than
  // `elevations`: a centerline part boundary is a marker on a record, not a
  // value in a list. It is not a DEM gap either - the measurement is fine and
  // the TRAIL is discontinuous, so the step across it is not a slope.
  it.each(vectors.boundary_cases)('$name', ({ samples, threshold, expected_gain }) => {
    const profile = samples.map((s, i) => ({
      distanceMi: i,
      elevationFt: s.elevation_ft,
      partStart: s.part_start === true,
    }))
    expect(cumulativeGainOverProfile(profile, threshold)).toBeCloseTo(expected_gain)
  })

  // Descent is pinned to the SAME table rather than a second one: loss is
  // defined as gain on the negated profile, so every shared vector negated
  // must produce exactly its expected_gain. A separate loss table would be a
  // second place for an edge case to be fixed in one language only.
  it.each(vectors.gap_cases)(
    'negated: $name',
    ({ elevations, threshold, expected_gain }) => {
      const negated = elevations.map((v) => (v === null ? null : -v))
      expect(cumulativeLossOverGaps(negated, threshold)).toBeCloseTo(expected_gain)
    },
  )

  it.each(vectors.boundary_cases)(
    'negated: $name',
    ({ samples, threshold, expected_gain }) => {
      const profile = samples.map((s, i) => ({
        distanceMi: i,
        elevationFt: s.elevation_ft === null ? null : -s.elevation_ft,
        partStart: s.part_start === true,
      }))
      expect(cumulativeLossOverProfile(profile, threshold)).toBeCloseTo(expected_gain)
    },
  )
})

describe('descent, and walking a window the other way', () => {
  const T = 3

  it('counts a single descent whole', () => {
    expect(cumulativeLossOverGaps([400, 300, 200, 100], T)).toBeCloseTo(300)
  })

  it('ignores jitter below the dead band, exactly as ascent does', () => {
    expect(cumulativeLossOverGaps([100, 99, 100, 98, 100], T)).toBe(0)
  })

  const seamed: ProfileSample[] = [
    { distanceMi: 0.0, elevationFt: 0 },
    { distanceMi: 0.1, elevationFt: 10 },
    // A new centerline piece 90 ft above the last one. The step between the
    // pieces is a seam in the trail, not a slope anybody walks.
    { distanceMi: 0.2, elevationFt: 100, partStart: true },
    { distanceMi: 0.3, elevationFt: 110 },
  ]

  it('lossBetween mirrors gainBetween across a seam', () => {
    expect(gainBetween(seamed, 0, 0.3, T)).toBeCloseTo(20)
    expect(lossBetween(seamed, 0, 0.3, T)).toBe(0)
  })

  it('keeps the seam where the trail breaks when the window is reversed', () => {
    const reversed = reverseProfileWindow(seamed)
    // Walked south the runs are [110, 100] and [10, 0]: two descents of 10,
    // no ascent. A dropped seam flag would join them into one 110 ft
    // phantom descent - the failure this helper exists to prevent.
    expect(reversed.map((s) => s.elevationFt)).toEqual([110, 100, 10, 0])
    expect(cumulativeGainOverProfile(reversed, T)).toBe(0)
    expect(cumulativeLossOverProfile(reversed, T)).toBeCloseTo(20)
  })

  it('walks the reversed run, and direction changes the figures', () => {
    // HIKE_PLANNING.md: "the ordered sample run has to be reversed before
    // counting, not the totals swapped afterwards." Reversal is what walking
    // the other way IS, so it is the operation implemented; whether the
    // hysteresis happens to make a swap coincide is a theorem nobody here
    // has proven, and nothing downstream is allowed to rely on it. What this
    // pins is the observable: the same window carries a 100 ft climb walked
    // south and none walked north.
    const window: ProfileSample[] = [
      { distanceMi: 0, elevationFt: 98 },
      { distanceMi: 0.1, elevationFt: 100 },
      { distanceMi: 0.2, elevationFt: 0 },
    ]
    expect(cumulativeGainOverProfile(reverseProfileWindow(window), T)).toBeCloseTo(100)
    expect(cumulativeGainOverProfile(window, T)).toBe(0)
  })

  it('reverses an empty and a one-sample window without inventing samples', () => {
    expect(reverseProfileWindow([])).toEqual([])
    expect(reverseProfileWindow([{ distanceMi: 1, elevationFt: 5 }])).toEqual([
      { distanceMi: 1, elevationFt: 5 },
    ])
  })
})
