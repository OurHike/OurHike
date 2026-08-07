import { describe, it, expect, vi, beforeEach } from 'vitest'
import { get, set, del } from 'idb-keyval'
import {
  clearPlannedHike,
  hikeSummary,
  loadPlannedHike,
  plannedDirection,
  plannedHike,
  savePlannedHike,
  wholeTrail,
  PLANNED_HIKE_KEY,
} from './plannedHike'

vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }))

// #335. Two numbers, and everything the app needs from a hike falls out of
// them. The rules worth holding are all about what those two numbers are NOT
// allowed to be: a pair that cannot describe a hike must never reach the code
// that decides which way "ahead" is, because the answer would be invented
// rather than derived - and the app would then use it to pick which closures
// to warn a hiker about.

describe('plannedDirection', () => {
  it('reads northbound off the numbers rather than a stored flag', () => {
    // The same call backend/app/models/hike.py makes by having no `direction`
    // column: a second source of truth is a second thing that can drift.
    expect(plannedDirection({ startMile: 0, endMile: 2197 })).toBe('NOBO')
  })

  it('reads southbound off the numbers too', () => {
    expect(plannedDirection({ startMile: 2197, endMile: 0 })).toBe('SOBO')
  })

  it('answers for a section as readily as for a thru-hike', () => {
    expect(plannedDirection({ startMile: 1408, endMile: 1450 })).toBe('NOBO')
    expect(plannedDirection({ startMile: 1450, endMile: 1408 })).toBe('SOBO')
  })
})

describe('plannedHike', () => {
  it('takes two different mile markers', () => {
    expect(plannedHike(10, 40)).toEqual({ startMile: 10, endMile: 40 })
  })

  it('refuses the same marker twice rather than nudging one', () => {
    // A hike with no length has no direction, and guessing one here would
    // invent a heading that the closure banner then uses to decide what is
    // ahead of somebody.
    expect(plannedHike(40, 40)).toBeNull()
  })

  it('refuses what a half-typed input actually produces', () => {
    // `Number.parseFloat('')` is NaN, and NaN compares false against
    // everything - so an unguarded pair would sail through the equality check
    // above and produce a hike whose direction is neither.
    expect(plannedHike(Number.NaN, 40)).toBeNull()
    expect(plannedHike(10, Number.NaN)).toBeNull()
    expect(plannedHike(Number.POSITIVE_INFINITY, 40)).toBeNull()
  })

  it('refuses a mile before the southern terminus', () => {
    expect(plannedHike(-5, 40)).toBeNull()
    expect(plannedHike(10, -1)).toBeNull()
  })

  it('refuses a mile past the end of the trail, when the length is known', () => {
    expect(plannedHike(10, 3000, 2197)).toBeNull()
    expect(plannedHike(3000, 10, 2197)).toBeNull()
  })

  it('accepts the terminus itself, which is where a thru-hike ends', () => {
    expect(plannedHike(0, 2197, 2197)).toEqual({ startMile: 0, endMile: 2197 })
  })

  it('checks only against zero when the trail length is not known yet', () => {
    // A phone that has not finished downloading the trail has no length to
    // check against. Refusing every hike until it does would be stricter than
    // the app can justify - the number a hiker typed is not wrong just
    // because this build cannot yet confirm it.
    expect(plannedHike(10, 3000)).toEqual({ startMile: 10, endMile: 3000 })
  })
})

describe('wholeTrail', () => {
  it('runs south to north for a northbound thru-hike', () => {
    expect(wholeTrail('NOBO', 2197)).toEqual({ startMile: 0, endMile: 2197 })
  })

  it('runs the other way for a southbound one', () => {
    expect(wholeTrail('SOBO', 2197)).toEqual({ startMile: 2197, endMile: 0 })
  })

  it('produces something plannedHike would accept', () => {
    // The shortcut and the validator must agree, or a button offers a hike
    // the Save beside it refuses.
    for (const direction of ['NOBO', 'SOBO'] as const) {
      const whole = wholeTrail(direction, 2197)
      expect(plannedHike(whole.startMile, whole.endMile, 2197)).toEqual(whole)
    }
  })
})

describe('hikeSummary', () => {
  it('names the direction and the range, low mile first', () => {
    expect(hikeSummary({ startMile: 0, endMile: 2197 })).toBe('Northbound · mi 0 – 2,197')
  })

  it('still reads low-to-high for a southbound hike', () => {
    // The direction word carries which way; a range printed backwards would
    // read as a typo rather than as information.
    expect(hikeSummary({ startMile: 2197, endMile: 0 })).toBe('Southbound · mi 0 – 2,197')
  })
})

describe('storage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps a hike under its own key, not in preferences', () => {
    // UserPreferences syncs to a backend schema that is `extra="forbid"`, so a
    // key invented there becomes a 422 the moment somebody signs in (#242).
    expect(PLANNED_HIKE_KEY).toBe('ourhike:hike')
    expect(PLANNED_HIKE_KEY).not.toContain('preferences')
  })

  it('saves and reads back what was set', async () => {
    const hike = { startMile: 1408, endMile: 2197 }
    await savePlannedHike(hike)
    expect(vi.mocked(set)).toHaveBeenCalledWith(PLANNED_HIKE_KEY, hike)

    vi.mocked(get).mockResolvedValue(hike)
    expect(await loadPlannedHike()).toEqual(hike)
  })

  it('reads nothing as no hike, which is the ordinary state', async () => {
    vi.mocked(get).mockResolvedValue(undefined)

    expect(await loadPlannedHike()).toBeNull()
  })

  it('re-validates on the way out rather than trusting what was stored', async () => {
    // The same call lib/preferences.ts makes about a background it no longer
    // recognises. This is a value some earlier build wrote, and a pair that
    // cannot describe a hike must not reach the code deciding what is ahead.
    vi.mocked(get).mockResolvedValue({ startMile: 40, endMile: 40 })

    expect(await loadPlannedHike()).toBeNull()
  })

  it('survives a stored shape that is missing a field entirely', async () => {
    vi.mocked(get).mockResolvedValue({ startMile: 40 })

    expect(await loadPlannedHike()).toBeNull()
  })

  it('clears by deleting the key, not by writing an empty hike', async () => {
    // "No hike" has to be the same state a hiker who never set one is in -
    // an empty-ish record would be a fourth state for every reader to handle.
    await clearPlannedHike()

    expect(vi.mocked(del)).toHaveBeenCalledWith(PLANNED_HIKE_KEY)
    expect(vi.mocked(set)).not.toHaveBeenCalled()
  })
})
