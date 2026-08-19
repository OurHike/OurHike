import { describe, it, expect } from 'vitest'
import {
  projectClosure,
  projectClosures,
  type ProjectableClosure,
} from './closureProjection'
import { buildTrailIndex } from './trailPosition'

// #674, features/POI_IDENTITY.md's "Miles are a projection, not an anchor".
// A closure stored only as two miles drifts when the ATC re-measures the
// centerline; stored geometry does not, so the miles are re-read from it
// against whatever release this phone is holding.

/** Eleven points a mile apart, the same shape seriousWarnings.test.ts builds
 *  and for the same reason: `mileOnTrail` snaps to the nearest vertex and gives
 *  up past `MAX_OFF_TRAIL_MILES`, so a two-point line would put every point
 *  four miles from anything and fail to snap - which would make these cases
 *  pass through the fallback while claiming to test the projection. */
const MILE_LAT = 1 / 69.05
const INDEX = buildTrailIndex({
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { source: 'centerline' },
      geometry: {
        type: 'LineString',
        coordinates: Array.from(
          { length: 11 },
          (_, i) => [-77, 39 + i * MILE_LAT] as [number, number],
        ),
      },
    },
  ],
})

function closure(over: Partial<ProjectableClosure> = {}): ProjectableClosure {
  return {
    start_mile_marker: 900,
    end_mile_marker: 906,
    start_lat: null,
    start_lon: null,
    end_lat: null,
    end_lon: null,
    ...over,
  }
}

const ANCHORED = closure({
  start_lat: 39 + 2 * MILE_LAT,
  start_lon: -77,
  end_lat: 39 + 7 * MILE_LAT,
  end_lon: -77,
})

describe('projectClosure', () => {
  it('re-reads both miles from the geometry rather than trusting what was stored', () => {
    // The stored pair (900, 906) was measured against whatever centerline was
    // published the day the closure was filed. The geometry is on this index.
    const projected = projectClosure(ANCHORED, INDEX)

    expect(projected.start_mile_marker).toBeCloseTo(2, 1)
    expect(projected.end_mile_marker).toBeCloseTo(7, 1)
  })

  it('keeps the stored miles when there is no geometry to project from', () => {
    // Every closure in existence today, and every one filed until this app
    // grows a closure form.
    const projected = projectClosure(closure(), INDEX)

    expect(projected.start_mile_marker).toBe(900)
    expect(projected.end_mile_marker).toBe(906)
  })

  it('returns the very same object when nothing projected, so memos do not churn', () => {
    const stored = closure()

    expect(projectClosure(stored, INDEX)).toBe(stored)
  })

  it('keeps BOTH stored miles when only one end projects', () => {
    // The load-bearing case. Taking the end that worked would give a stretch
    // measured half against this release and half against the one it was
    // authored on - its length would be the difference between two different
    // rulers, which is not a distance. Both stale miles are at least
    // consistent with each other.
    const halfAnchored = closure({ start_lat: 39 + 2 * MILE_LAT, start_lon: -77 })

    const projected = projectClosure(halfAnchored, INDEX)

    expect(projected.start_mile_marker).toBe(900)
    expect(projected.end_mile_marker).toBe(906)
  })

  it('keeps the stored miles when an end is too far off the trail to snap', () => {
    // `mileOnTrail` refuses past MAX_OFF_TRAIL_MILES rather than guessing, and
    // a refusal has to land as "no projection", not as a null mile.
    const astray = closure({ ...ANCHORED, end_lat: 45, end_lon: -60 })

    const projected = projectClosure(astray, INDEX)

    expect(projected.start_mile_marker).toBe(900)
    expect(projected.end_mile_marker).toBe(906)
  })

  it('treats a missing key as no geometry, the way an old baked baseline sends it', () => {
    // A baseline published before these columns existed omits the keys
    // entirely, so a phone on last month's release reads `undefined` rather
    // than null. Both are "no geometry"; letting undefined through would put
    // NaN coordinates into mileOnTrail and produce a mile that looks real.
    const fromOldBaseline = {
      start_mile_marker: 900,
      end_mile_marker: 906,
    } as ProjectableClosure

    const projected = projectClosure(fromOldBaseline, INDEX)

    expect(projected.start_mile_marker).toBe(900)
    expect(projected.end_mile_marker).toBe(906)
  })

  it('orders the projected pair, because closureBanner assumes start <= end', () => {
    // Projection should not invert a pair - both ends move a few hundred feet
    // the same way - but an inverted pair makes the inside-the-closure test
    // unsatisfiable and the banner silently wrong (#257's lesson).
    const backwards = closure({
      start_lat: 39 + 7 * MILE_LAT,
      start_lon: -77,
      end_lat: 39 + 2 * MILE_LAT,
      end_lon: -77,
    })

    const projected = projectClosure(backwards, INDEX)

    expect(projected.start_mile_marker).toBeLessThan(projected.end_mile_marker)
    expect(projected.start_mile_marker).toBeCloseTo(2, 1)
  })

  it('carries every other field through untouched', () => {
    const withNote = { ...ANCHORED, id: 'c1', note: 'Blowdown' }

    const projected = projectClosure(withNote, INDEX)

    expect(projected.id).toBe('c1')
    expect(projected.note).toBe('Blowdown')
  })
})

describe('projectClosures', () => {
  it('projects the anchored ones and leaves the rest alone', () => {
    const projected = projectClosures(
      [ANCHORED, closure({ start_mile_marker: 10, end_mile_marker: 12 })],
      INDEX,
    )

    expect(projected[0].start_mile_marker).toBeCloseTo(2, 1)
    expect(projected[1].start_mile_marker).toBe(10)
  })

  it('returns the same array when nothing moved', () => {
    // Which is every call today, so the memo downstream must not re-run.
    const stored = [closure()]

    expect(projectClosures(stored, INDEX)).toBe(stored)
  })
})
