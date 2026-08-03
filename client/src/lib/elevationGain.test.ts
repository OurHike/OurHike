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

import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

import {
  cumulativeGain,
  cumulativeGainOverGaps,
  gainBetween,
  rawCumulativeGain,
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

  // Walked up from the working directory rather than resolved from
  // import.meta.url: Vitest transforms this module, so its import.meta.url is
  // not a file: URL and fileURLToPath throws on it. Walking also survives the
  // suite being run from the repo root instead of client/.
  const findRepoFile = (relative: string): string => {
    let dir = process.cwd()
    for (;;) {
      const candidate = resolve(dir, relative)
      if (existsSync(candidate)) return candidate
      const parent = dirname(dir)
      if (parent === dir) throw new Error(`${relative} not found above ${process.cwd()}`)
      dir = parent
    }
  }

  const vectors = JSON.parse(
    readFileSync(findRepoFile('pipeline/reference/gain_vectors.json'), 'utf8'),
  ) as { cases: Vector[]; gap_cases: Vector[] }

  it('has vectors to run', () => {
    // A vector file that silently emptied would turn every case below into
    // zero cases, and a suite that runs nothing passes.
    expect(vectors.cases.length).toBeGreaterThanOrEqual(10)
    expect(vectors.gap_cases.length).toBeGreaterThanOrEqual(3)
  })

  it.each(vectors.cases)('$name', ({ elevations, threshold, expected_gain }) => {
    expect(cumulativeGain(elevations as number[], threshold)).toBeCloseTo(expected_gain)
  })

  it.each(vectors.gap_cases)('$name', ({ elevations, threshold, expected_gain }) => {
    expect(cumulativeGainOverGaps(elevations, threshold)).toBeCloseTo(expected_gain)
  })
})
