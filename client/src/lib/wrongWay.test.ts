import { describe, it, expect } from 'vitest'
import {
  detectWrongWay,
  OFF_TRAIL_THRESHOLD_FT,
  CUE_PERSISTENCE_MS,
  PUSH_PERSISTENCE_MS,
} from './wrongWay'

// See features/HIKER_SAFETY.md §5 and WIREFRAMES.md's wrong-way alert copy.
// The 90ft / 12min / 25min numbers below are WIREFRAMES.md UI-mockup
// placeholders, NOT a validated HIKER_SAFETY.md spec - that doc explicitly
// declines to give numbers pending real field-testing under canopy
// (ROADMAP.md Phase 4). These tests assert the MECHANISM behaves correctly
// against the placeholder constants, never that the numbers themselves are
// correct. False negatives are acceptable; false positives are the failure
// this whole module exists to prevent.

const MIN = 60 * 1000

function trace(
  samples: Array<{ atMs: number; distanceFt: number; bearingDeltaDeg: number | null }>,
) {
  return samples.map((s) => ({
    timestampMs: s.atMs,
    distanceFromTrailFt: s.distanceFt,
    bearingDeltaDeg: s.bearingDeltaDeg,
  }))
}

describe('detectWrongWay', () => {
  it('stays silent for an empty trace', () => {
    expect(detectWrongWay([])).toBe('silent')
  })

  it('stays silent when off-trail distance is under the threshold, even sustained for a long time', () => {
    const t = trace([
      { atMs: 0, distanceFt: OFF_TRAIL_THRESHOLD_FT - 10, bearingDeltaDeg: 0 },
      {
        atMs: PUSH_PERSISTENCE_MS + MIN,
        distanceFt: OFF_TRAIL_THRESHOLD_FT - 10,
        bearingDeltaDeg: 0,
      },
    ])
    expect(detectWrongWay(t)).toBe('silent')
  })

  it('stays silent for a short backtrack (e.g. to a spring) that does not persist past the cue threshold', () => {
    const t = trace([
      { atMs: 0, distanceFt: 20, bearingDeltaDeg: 0 },
      { atMs: 2 * MIN, distanceFt: 150, bearingDeltaDeg: 175 }, // brief reversal
      { atMs: 5 * MIN, distanceFt: 20, bearingDeltaDeg: 0 }, // back on track well before 12min
    ])
    expect(detectWrongWay(t)).toBe('silent')
  })

  it('stays silent while standing still - no bearing (below the minimum-movement threshold) never counts as sustained divergence', () => {
    const t = trace([
      { atMs: 0, distanceFt: 20, bearingDeltaDeg: null },
      { atMs: 30 * MIN, distanceFt: 20, bearingDeltaDeg: null }, // long dwell at a shelter, but not moving
    ])
    expect(detectWrongWay(t)).toBe('silent')
  })

  it('fires the in-app cue once reversed bearing persists past the cue threshold, but not yet the push threshold', () => {
    const t = trace([
      { atMs: 0, distanceFt: 150, bearingDeltaDeg: 175 },
      { atMs: CUE_PERSISTENCE_MS + MIN, distanceFt: 150, bearingDeltaDeg: 175 },
    ])
    expect(detectWrongWay(t)).toBe('cue')
  })

  it('escalates to push once reversed bearing persists past the push threshold', () => {
    const t = trace([
      { atMs: 0, distanceFt: 150, bearingDeltaDeg: 175 },
      { atMs: CUE_PERSISTENCE_MS + MIN, distanceFt: 150, bearingDeltaDeg: 175 },
      { atMs: PUSH_PERSISTENCE_MS + MIN, distanceFt: 150, bearingDeltaDeg: 175 },
    ])
    expect(detectWrongWay(t)).toBe('push')
  })

  it('a return to the correct bearing resets the sustained-divergence clock', () => {
    const t = trace([
      { atMs: 0, distanceFt: 150, bearingDeltaDeg: 175 },
      { atMs: 10 * MIN, distanceFt: 150, bearingDeltaDeg: 175 }, // 10min in, not yet cue (12min)
      { atMs: 11 * MIN, distanceFt: 20, bearingDeltaDeg: 0 }, // corrects course
      { atMs: 11 * MIN + PUSH_PERSISTENCE_MS, distanceFt: 20, bearingDeltaDeg: 0 }, // long time later, on track
    ])
    expect(detectWrongWay(t)).toBe('silent')
  })

  it('off-trail distance alone (independent of bearing) can also trigger, once sustained', () => {
    const t = trace([
      { atMs: 0, distanceFt: OFF_TRAIL_THRESHOLD_FT + 50, bearingDeltaDeg: 0 },
      {
        atMs: CUE_PERSISTENCE_MS + MIN,
        distanceFt: OFF_TRAIL_THRESHOLD_FT + 50,
        bearingDeltaDeg: 0,
      },
    ])
    expect(detectWrongWay(t)).toBe('cue')
  })
})
