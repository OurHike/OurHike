// Tests for upcomingClimb.ts.
//
// What the callout claims
// -----------------------
// `+640 ft · 2.6 mi · ≈1h 10m` is the most specific promise this app makes
// about ground a hiker has not reached yet, and it feeds a pacing decision -
// FEATURES.md moved elevation into MVP on exactly that argument. Three ways to
// get it wrong, all held below:
//
//   - highlight noise, and the ribbon cries wolf until nobody reads it;
//   - count a climb that is half underfoot at its full size, and the hiker
//     budgets time and water for work they have already done;
//   - count a southbounder's climb along an ascending mile axis, where it is
//     the descent off the far side and sums to nothing.
//
// The floor is derived, not picked, and the derivation is testable: naismithTime
// rounds to five minutes and Naismith gives an hour per 600 m, so 164 ft of
// ascent is one rounding step. Anything below that would be highlighted and
// then captioned with a time indistinguishable from flat ground.

import { describe, it, expect } from 'vitest'
import { MIN_CLIMB_FT, upcomingClimb } from './upcomingClimb'
import type { ElevationProfile, MileWindow } from './elevationProfile'

/**
 * A profile sampled every tenth of a mile between linearly-interpolated control
 * points. Denser than the tests strictly need, and deliberately: the real
 * artifact samples every 25 m, so a window edge or a hiker's position lands
 * BETWEEN samples the way it does on the trail rather than always on one.
 */
function rampProfile(controls: Array<[number, number]>, stepMi = 0.1): ElevationProfile {
  const miles: number[] = []
  const feet: number[] = []
  const end = controls[controls.length - 1][0]

  for (let mile = controls[0][0]; mile <= end + 1e-9; mile += stepMi) {
    const next = controls.findIndex(([m]) => m >= mile - 1e-9)
    const upper = Math.max(next, 1)
    const [m0, f0] = controls[upper - 1]
    const [m1, f1] = controls[upper]
    const t = m1 === m0 ? 0 : (mile - m0) / (m1 - m0)

    miles.push(Number(mile.toFixed(4)))
    feet.push(f0 + (f1 - f0) * t)
  }

  return { distanceMi: Float32Array.from(miles), elevationFt: Float32Array.from(feet) }
}

const WHOLE: MileWindow = { startMile: 0, endMile: 4 }

/** Flat, then 1,000 ft up between mile 1 and mile 2, then back down. */
const CLIMB = rampProfile([
  [0, 1000],
  [1, 1000],
  [2, 2000],
  [3, 1000],
  [4, 1000],
])

/** A 200 ft bump - under the floor - and then a real 1,000 ft climb. */
const BUMP_THEN_CLIMB = rampProfile([
  [0, 1000],
  [1, 1200],
  [2, 1000],
  [3, 2000],
  [4, 1000],
])

describe('finding the next climb', () => {
  it('reports the trough, the peak and the ascent between them', () => {
    const climb = upcomingClimb(CLIMB, WHOLE, 0, 'NOBO')

    expect(climb?.startMile).toBeCloseTo(1, 1)
    expect(climb?.endMile).toBeCloseTo(2, 1)
    expect(climb?.ascentFt).toBe(1000)
  })

  it('starts the climb where the ground turns up, not where the flat began', () => {
    // Otherwise the callout captions a one-mile climb "· 2.0 mi ·" and the
    // highlight covers a mile of level walking.
    const climb = upcomingClimb(CLIMB, WHOLE, 0, 'NOBO')

    // One mile of climbing, not two miles of flat-and-then-climbing.
    expect((climb?.endMile ?? 0) - (climb?.startMile ?? 0)).toBeCloseTo(1, 1)
    expect(climb?.startMile).toBeGreaterThan(0.9)
  })

  it('walks past a bump under the floor to the climb that matters', () => {
    const climb = upcomingClimb(BUMP_THEN_CLIMB, WHOLE, 0, 'NOBO')

    expect(climb?.startMile).toBeCloseTo(2, 1)
    expect(climb?.ascentFt).toBe(1000)
  })

  it('highlights nothing on ground with no real climb on it', () => {
    // Rolling ridge with nothing over the floor in the next nine miles is a
    // true and useful thing to show. ElevationRibbon draws the profile without
    // a highlight or a callout when it gets undefined.
    const rolling = rampProfile([
      [0, 1000],
      [1, 1150],
      [2, 1000],
      [3, 1150],
      [4, 1000],
    ])

    expect(upcomingClimb(rolling, WHOLE, 0, 'NOBO')).toBeUndefined()
  })

  it('ignores a climb already walked', () => {
    const climb = upcomingClimb(CLIMB, WHOLE, 2.5, 'NOBO')

    expect(climb).toBeUndefined()
  })
})

describe('a hiker already on the climb', () => {
  it('counts from where they are, not from the trough behind them', () => {
    // The callout is a claim about work not yet done. Printing the whole climb
    // when half of it is underfoot is a promise the profile does not make.
    const climb = upcomingClimb(CLIMB, WHOLE, 1.5, 'NOBO')

    expect(climb?.startMile).toBeCloseTo(1.5, 1)
    expect(climb?.endMile).toBeCloseTo(2, 1)
    expect(climb?.ascentFt).toBe(500)
  })

  it('stops highlighting a climb once too little of it is left to matter', () => {
    // Ninety percent up a 500 ft climb leaves fifty feet - below the floor, and
    // no longer the thing worth showing. The search carries on past the top.
    const shortClimb = rampProfile([
      [0, 1000],
      [1, 1000],
      [2, 1500],
      [3, 1000],
      [4, 1000],
    ])

    expect(upcomingClimb(shortClimb, WHOLE, 1.9, 'NOBO')).toBeUndefined()
  })
})

describe('a southbounder', () => {
  // Ahead is a decreasing mile. Everything below would pass trivially if the
  // direction were ignored, and be wrong on the trail.
  it('is shown the climb behind them on the mile axis', () => {
    const climb = upcomingClimb(CLIMB, WHOLE, 4, 'SOBO')

    expect(climb?.ascentFt).toBe(1000)
  })

  it('gets bounds in ascending mile order, so the highlight has a width', () => {
    // ElevationRibbon positions its rect as pctAlong(end) - pctAlong(start).
    // Travel-ordered bounds would make that negative, and an SVG rect with a
    // negative width draws nothing at all.
    const climb = upcomingClimb(CLIMB, WHOLE, 4, 'SOBO')

    expect(climb?.endMile ?? 0).toBeGreaterThan(climb?.startMile ?? 0)
  })

  it('ignores the climb once it is north of them', () => {
    const climb = upcomingClimb(CLIMB, WHOLE, 1.5, 'SOBO')

    expect(climb).toBeUndefined()
  })

  it('counts from where they are when already on it', () => {
    const climb = upcomingClimb(CLIMB, WHOLE, 2.5, 'SOBO')

    expect(climb?.ascentFt).toBe(500)
    expect(climb?.startMile).toBeCloseTo(2, 1)
    expect(climb?.endMile).toBeCloseTo(2.5, 1)
  })
})

describe('DEM noise', () => {
  /**
   * A climb and then a descent, each carrying a 5 ft wobble on every other
   * sample - half the dead band, and roughly the shape real 25 m samples have.
   *
   * Built by hand rather than with rampProfile() because interpolated ramps are
   * too clean to exercise this: a tenth of a mile of a real gradient moves the
   * ground far more than the dead band, so every reversal confirms on the first
   * sample and the noise-rejection path never runs.
   */
  const JITTERY = (() => {
    const miles: number[] = []
    const feet: number[] = []
    let ft = 1000
    let mile = 0

    const push = (value: number) => {
      miles.push(Number(mile.toFixed(2)))
      feet.push(value)
      mile += 0.1
    }

    push(ft)
    for (let i = 0; i < 10; i += 1) {
      ft += 100
      push(ft)
      push(ft - 5)
    }
    for (let i = 0; i < 10; i += 1) {
      ft -= 100
      push(ft)
      push(ft + 5)
    }

    return {
      distanceMi: Float32Array.from(miles),
      elevationFt: Float32Array.from(feet),
    }
  })()

  it('reads a wobbling climb as one climb, not a staircase of small ones', () => {
    // Every 5 ft dip is under the dead band, so none of them is a summit. Take
    // them at face value and the first "climb" ahead is a hundred feet ending a
    // tenth of a mile away, which is both wrong and useless.
    const climb = upcomingClimb(JITTERY, { startMile: 0, endMile: 4 }, 0, 'NOBO')

    expect(climb?.ascentFt).toBe(1000)
    expect(climb?.endMile).toBeCloseTo(1.9, 1)
  })

  it('does not find a climb in a descent that only wobbles', () => {
    // The same rejection in the other direction. A 5 ft rise partway down is
    // not the bottom of the hill, and treating it as one would caption the
    // ribbon with a climb that is not there.
    expect(
      upcomingClimb(JITTERY, { startMile: 0, endMile: 4 }, 2.5, 'NOBO'),
    ).toBeUndefined()
  })
})

describe('before the direction is known', () => {
  it('claims no climb at all', () => {
    // lib/hikeDirection.ts withholds the direction for the first quarter mile
    // of movement. The window is centred over that stretch, which claims
    // nothing about which way anyone faces - but a climb callout is a claim
    // about work they are going to do, and it would be a coin flip.
    expect(upcomingClimb(CLIMB, WHOLE, 0, undefined)).toBeUndefined()
  })
})

describe('DEM coverage gaps', () => {
  it('does not invent a climb across ground the DEM never measured', () => {
    const gapped: ElevationProfile = {
      distanceMi: Float32Array.from([0, 1, 2, 3]),
      elevationFt: Float32Array.from([1000, Number.NaN, Number.NaN, 2000]),
    }

    // Joining 1,000 ft to 2,000 ft across the gap would be a 1,000 ft climb
    // nobody can say is there.
    expect(upcomingClimb(gapped, { startMile: 0, endMile: 3 }, 0, 'NOBO')).toBeUndefined()
  })

  it('still offers a climb measured on the near side of a gap', () => {
    const gapped = rampProfile([
      [0, 1000],
      [1, 1000],
      [2, 2000],
    ])
    gapped.elevationFt[gapped.elevationFt.length - 1] = Number.NaN

    const climb = upcomingClimb(gapped, { startMile: 0, endMile: 2 }, 0, 'NOBO')

    expect(climb?.ascentFt).toBeGreaterThanOrEqual(MIN_CLIMB_FT)
  })
})

describe('MIN_CLIMB_FT', () => {
  it('clears the five-minute step below which the callout could not move', () => {
    // Naismith: one hour per 600 m of ascent, and naismithTime rounds to five
    // minutes, so 164 ft is one step. A floor at or under it would highlight a
    // region and caption it with flat-ground time.
    const oneRoundingStep = (5 / 60) * (600 / 0.3048)

    expect(oneRoundingStep).toBeCloseTo(164, 0)
    expect(MIN_CLIMB_FT).toBeGreaterThan(oneRoundingStep)
  })
})
