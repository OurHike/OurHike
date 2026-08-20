import { describe, it, expect, afterEach } from 'vitest'
import {
  FLAT_PACE_STEP_MPH,
  DESCENT_STEP_MINUTES,
  MAX_ASCENT_METERS_PER_HOUR,
  MAX_DESCENT_MINUTES_PER_1000M,
  MAX_FLAT_PACE_MPH,
  MIN_DESCENT_MINUTES_PER_1000M,
  MIN_ASCENT_METERS_PER_HOUR,
  MIN_FLAT_PACE_MPH,
  STANDARD_ASCENT_METERS_PER_HOUR,
  STANDARD_FLAT_PACE_MPH,
  STANDARD_PACE,
  isStandardPace,
  paceEstimate,
  paceMinutes,
  paceRatio,
  readPace,
  readStoredPace,
  writeStoredPace,
  clearStoredPace,
  PACE_STORAGE_KEY,
  type PaceProfile,
} from './pace'
import { naismithMinutes, naismithTime } from './naismith'

/** McAfee Knob's leg, as #883's mock-ups drew it. */
const WALK = { distanceMi: 4.0, ascentFt: 1740 }

function slower(overrides: Partial<PaceProfile> = {}): PaceProfile {
  return { ...STANDARD_PACE, flatPaceMph: 2.6, ...overrides }
}

describe('the standard pace is exactly Naismith', () => {
  it('agrees with naismithMinutes to the last decimal', () => {
    // The whole reason the controls are Naismith's OWN two terms rather than
    // an abstract multiplier: "standard" has to be exactly representable, or a
    // fresh install silently disagrees with the rule it claims to use.
    for (const walk of [
      WALK,
      { distanceMi: 12.4, ascentFt: 3200 },
      { distanceMi: 0.8, ascentFt: 0 },
      { distanceMi: 0, ascentFt: 500 },
    ]) {
      expect(paceMinutes(walk, STANDARD_PACE)).toBeCloseTo(naismithMinutes(walk), 9)
    }
  })

  it('prints what naismithTime prints, at the standard', () => {
    expect(paceEstimate(WALK, STANDARD_PACE).text).toBe(naismithTime(WALK))
  })

  it('says nothing about a baseline when it IS the baseline', () => {
    expect(paceEstimate(WALK, STANDARD_PACE).relativeLine).toBeNull()
  })
})

describe('a hiker who has moved the controls', () => {
  it('takes longer on the flat when the flat pace is lower', () => {
    const mine = paceMinutes(WALK, slower())
    expect(mine).toBeGreaterThan(naismithMinutes(WALK))
  })

  it('takes longer on a climb when the ascent penalty is steeper', () => {
    // Steeper penalty = FEWER metres per hour, which is the direction most
    // likely to be got backwards.
    const steeper = { ...STANDARD_PACE, ascentMetersPerHour: 480 }
    expect(paceMinutes(WALK, steeper)).toBeGreaterThan(naismithMinutes(WALK))
  })

  it('costs nothing for descent at the STANDARD pace, however much there is', () => {
    // A fresh install is Naismith, and Naismith has no descent term at all.
    // Asserted against a caller that passes descent ANYWAY - comparing two
    // identical calls would be a test that cannot fail.
    const withDescent = paceMinutes(
      { distanceMi: 3, ascentFt: 500, descentFt: 4000 },
      STANDARD_PACE,
    )
    const without = paceMinutes({ distanceMi: 3, ascentFt: 500 }, STANDARD_PACE)
    expect(withDescent).toBe(without)
  })
})

/**
 * The descent coefficient (#900), and the one direction it has.
 *
 * The maintainer's decision reverses PERSONALIZED_PACE.md's own lean, which put
 * descent in the learned layer because "almost nobody has a number for
 * descent". What it does NOT reverse is CLAUDE.md's rule that Naismith gets no
 * descent CREDIT - so this control only ever adds time.
 */
describe('descent', () => {
  const KNEES: PaceProfile = { ...STANDARD_PACE, descentMinutesPer1000m: 30 }
  const DOWNHILL = { distanceMi: 3, ascentFt: 0, descentFt: 3000 }

  it('costs time once a hiker says it costs them time', () => {
    expect(paceMinutes(DOWNHILL, KNEES)).toBeGreaterThan(
      paceMinutes(DOWNHILL, STANDARD_PACE),
    )
  })

  it('charges the rate it was given', () => {
    // 3,000 ft is 914.4 m; at 30 min per 1,000 m that is 27.4 extra minutes.
    const extra = paceMinutes(DOWNHILL, KNEES) - paceMinutes(DOWNHILL, STANDARD_PACE)
    expect(extra).toBeCloseTo((3000 * 0.3048 * 30) / 1000, 6)
  })

  it('NEVER buys time back, at any setting', () => {
    // The safety property, and the reason this is a penalty rather than a
    // signed correction. CLAUDE.md: "Naismith gets no descent credit... so the
    // next agent does not improve it into an optimistic number."
    for (const rate of [0, 5, 30, MAX_DESCENT_MINUTES_PER_1000M]) {
      const mine = { ...STANDARD_PACE, descentMinutesPer1000m: rate }
      expect(paceMinutes(DOWNHILL, mine)).toBeGreaterThanOrEqual(
        paceMinutes(DOWNHILL, STANDARD_PACE),
      )
    }
  })

  it('floors a negative descent rather than letting it buy time back', () => {
    // A caller passing a signed elevation delta would otherwise get a credit
    // through the back door.
    const signed = paceMinutes({ distanceMi: 3, ascentFt: 0, descentFt: -3000 }, KNEES)
    expect(signed).toBe(paceMinutes({ distanceMi: 3, ascentFt: 0 }, KNEES))
  })

  it('is absent from a walk that does not mention descent', () => {
    // A spur's round trip is net zero, and omitting the field costs nothing.
    expect(paceMinutes({ distanceMi: 3, ascentFt: 0 }, KNEES)).toBe(
      paceMinutes({ distanceMi: 3, ascentFt: 0, descentFt: 0 }, KNEES),
    )
  })

  it('makes the profile three coefficients, not two', () => {
    expect(Object.keys(STANDARD_PACE).sort()).toEqual([
      'ascentMetersPerHour',
      'descentMinutesPer1000m',
      'flatPaceMph',
    ])
  })

  it('starts at zero, which is on the control grid and IS the standard', () => {
    expect(STANDARD_PACE.descentMinutesPer1000m).toBe(0)
    expect(MIN_DESCENT_MINUTES_PER_1000M).toBe(0)
    expect(MAX_DESCENT_MINUTES_PER_1000M % DESCENT_STEP_MINUTES).toBe(0)
  })

  it('carries a baseline line once it changes the printed time', () => {
    // #851's rule reaches the new coefficient too - it is not special.
    const estimate = paceEstimate(DOWNHILL, KNEES)
    expect(estimate.relativeLine).toMatch(/^was ≈.*× standard$/)
  })
})

/**
 * #851's decision, held as a property.
 *
 * "We should always display how their setting relates to Naismith." The
 * baseline and the adjusted figure travel in one object so a caller cannot
 * take one without the other; these are the cases where the line appears.
 */
describe('the relationship to the standard', () => {
  it('carries the baseline as a TIME, not only as a multiplier', () => {
    const line = paceEstimate(WALK, slower()).relativeLine
    expect(line).toMatch(/^was ≈/)
    expect(line).toContain('× standard')
  })

  it('names the standard estimate the app would otherwise have printed', () => {
    const line = paceEstimate(WALK, slower()).relativeLine
    expect(line).toContain(naismithTime(WALK))
  })

  it('is computed for THIS walk, because one profile has no single ratio', () => {
    // A hiker slow on the flat and standard on climbs reads differently on a
    // towpath than on a staircase. Any screen printing one number has to
    // compute it for the walk in front of it.
    const towpath = paceRatio({ distanceMi: 6, ascentFt: 0 }, slower())
    const staircase = paceRatio({ distanceMi: 0.4, ascentFt: 2000 }, slower())
    expect(towpath).not.toBeNull()
    expect(staircase).not.toBeNull()
    expect(towpath).toBeGreaterThan(staircase as number)
  })

  it('says nothing when the two round to the same printed time', () => {
    // "was ≈2h 10m" beside "≈2h 10m" reads as a malfunction, not a caveat.
    const barely = { ...STANDARD_PACE, flatPaceMph: STANDARD_FLAT_PACE_MPH - 0.001 }
    const estimate = paceEstimate(WALK, barely)
    expect(estimate.text).toBe(naismithTime(WALK))
    expect(estimate.relativeLine).toBeNull()
  })

  it('has no baseline to offer for a walk of no length', () => {
    const nothing = paceEstimate({ distanceMi: 0, ascentFt: 0 }, slower())
    expect(nothing.relativeLine).toBeNull()
    expect(Number.isFinite(nothing.minutes)).toBe(true)
  })

  it('never prints an arrival clock, on any pace', () => {
    // WIREFRAMES.md's load-bearing rule for every estimate in the app.
    const estimate = paceEstimate(WALK, slower())
    expect(estimate.text).toContain('≈')
    expect(estimate.text).not.toMatch(/\d{1,2}:\d{2}\s*(am|pm)/i)
  })
})

/**
 * The safety property.
 *
 * These two numbers move every time estimate in the app, including the one a
 * hiker uses to decide whether they beat the dark. lib/preferences.ts repairs
 * unknown ENUM values and has nothing for numbers, so this is where a corrupt
 * value has to stop.
 */
describe('a stored value this build cannot read', () => {
  it('falls back to the standard rather than to whatever was stored', () => {
    for (const junk of [undefined, null, 'fast', NaN, Infinity, -Infinity, {}, []]) {
      const read = readPace({ flatPaceMph: junk, ascentMetersPerHour: junk })
      expect(read).toEqual(STANDARD_PACE)
      expect(isStandardPace(read)).toBe(true)
    }
  })

  it('clamps a value past either end rather than honouring it', () => {
    const wild = readPace({ flatPaceMph: 900, ascentMetersPerHour: -40 })
    expect(wild.flatPaceMph).toBe(MAX_FLAT_PACE_MPH)
    expect(wild.ascentMetersPerHour).toBe(MIN_ASCENT_METERS_PER_HOUR)
  })

  it('never yields a negative or non-finite duration, whatever is stored', () => {
    // Totality, asserted rather than assumed: a NaN reaching
    // formatNaismithMinutes prints "≈NaNm" on a safety-critical line.
    for (const junk of ['x', NaN, -5, 0, Infinity]) {
      const minutes = paceMinutes(WALK, {
        flatPaceMph: junk as unknown as number,
        ascentMetersPerHour: junk as unknown as number,
        descentMinutesPer1000m: junk as unknown as number,
      })
      expect(Number.isFinite(minutes)).toBe(true)
      expect(minutes).toBeGreaterThan(0)
    }
  })

  it('cannot be made faster than the fastest allowed pace', () => {
    // The bound that matters. Whatever is in storage, the app will not tell a
    // hiker they move quicker than MAX_FLAT_PACE_MPH on the flat.
    const fastest = paceMinutes(
      { distanceMi: 10, ascentFt: 0 },
      readPace({
        flatPaceMph: 1e9,
        ascentMetersPerHour: 1e9,
      }),
    )
    expect(fastest).toBeCloseTo((10 / MAX_FLAT_PACE_MPH) * 60, 6)
  })

  it('holds the same floor through paceEstimate, not only readPace', () => {
    const estimate = paceEstimate(WALK, {
      flatPaceMph: 1e9,
      ascentMetersPerHour: 1e9,
    } as PaceProfile)
    expect(Number.isFinite(estimate.minutes)).toBe(true)
    expect(estimate.text).not.toContain('NaN')
  })
})

describe('the bounds themselves', () => {
  it('bracket the standard, so a fresh install sits inside the range', () => {
    expect(STANDARD_FLAT_PACE_MPH).toBeGreaterThan(MIN_FLAT_PACE_MPH)
    expect(STANDARD_FLAT_PACE_MPH).toBeLessThan(MAX_FLAT_PACE_MPH)
    expect(STANDARD_ASCENT_METERS_PER_HOUR).toBeGreaterThan(MIN_ASCENT_METERS_PER_HOUR)
    expect(STANDARD_ASCENT_METERS_PER_HOUR).toBeLessThan(MAX_ASCENT_METERS_PER_HOUR)
  })

  it('puts the standard flat pace at 5 km/h, which is the rule', () => {
    expect(STANDARD_FLAT_PACE_MPH * 1.609344).toBeCloseTo(5, 9)
  })
})

/**
 * Where the profile is kept.
 *
 * Its own key, NOT `ourhike:preferences`. That blob is a sync target - the
 * router takes a whole-blob PUT with `extra="forbid"`, so one unknown key
 * costs the entire sync - and PERSONALIZED_PACE.md §4 keeps a pace profile
 * off the wire regardless: "not a sync target even when an account exists".
 */
describe('the pace store', () => {
  afterEach(() => {
    clearStoredPace()
  })

  it('is the standard pace on a phone that has never set one', () => {
    expect(readStoredPace()).toEqual(STANDARD_PACE)
  })

  it('round-trips a profile a hiker set', () => {
    const mine: PaceProfile = {
      flatPaceMph: 2.6,
      ascentMetersPerHour: 480,
      descentMinutesPer1000m: 20,
    }
    writeStoredPace(mine)
    expect(readStoredPace()).toEqual(mine)
  })

  it('keeps out of the synced preferences blob', () => {
    // The contract backend/tests/test_preferences_contract.py enforces: the
    // client's UserPreferences and the server's schema are one model written
    // twice, and a client-only key breaks the sync for every hiker.
    expect(PACE_STORAGE_KEY).not.toContain('preferences')
    writeStoredPace({
      flatPaceMph: 2.6,
      ascentMetersPerHour: 480,
      descentMinutesPer1000m: 0,
    })
    expect(localStorage.getItem('ourhike:preferences')).toBeNull()
  })

  it('clamps on the way IN, so nothing out of range is ever stored', () => {
    writeStoredPace({
      flatPaceMph: 99,
      ascentMetersPerHour: 1,
      descentMinutesPer1000m: 999,
    })
    const stored = JSON.parse(localStorage.getItem(PACE_STORAGE_KEY) as string)
    expect(stored.flatPaceMph).toBe(MAX_FLAT_PACE_MPH)
    expect(stored.ascentMetersPerHour).toBe(MIN_ASCENT_METERS_PER_HOUR)
    expect(stored.descentMinutesPer1000m).toBe(MAX_DESCENT_MINUTES_PER_1000M)
  })

  it('reads the standard pace back from anything unparseable', () => {
    for (const junk of ['not json', 'null', '[]', '"3.1"', '{"flatPaceMph":"fast"}']) {
      localStorage.setItem(PACE_STORAGE_KEY, junk)
      expect(readStoredPace()).toEqual(STANDARD_PACE)
    }
  })

  it('forgets it on clear, returning every estimate to the rule', () => {
    writeStoredPace({
      flatPaceMph: 2.6,
      ascentMetersPerHour: 480,
      descentMinutesPer1000m: 0,
    })
    clearStoredPace()
    expect(readStoredPace()).toEqual(STANDARD_PACE)
    expect(isStandardPace(readStoredPace())).toBe(true)
  })
})

/**
 * The range the maintainer chose (#888) and the step asked for in review on
 * #889: 1 to 4 mph in tenths.
 *
 * Replacing bounds that were tagged @unvalidated - picked to bracket the
 * standard, never measured.
 */
describe('the flat pace control range', () => {
  it('runs from 1 to 4 mph', () => {
    expect(MIN_FLAT_PACE_MPH).toBe(1)
    expect(MAX_FLAT_PACE_MPH).toBe(4)
  })

  it('steps in tenths of a mile per hour', () => {
    expect(FLAT_PACE_STEP_MPH).toBe(0.1)
  })

  it('reaches FASTER than the standard, which is the decision', () => {
    // The point of the range, asserted rather than implied by two numbers.
    // The safeguard is not a clamp - it is that an adjusted estimate always
    // carries what it was adjusted from.
    expect(MAX_FLAT_PACE_MPH).toBeGreaterThan(STANDARD_FLAT_PACE_MPH)
  })

  it('reaches a genuinely slow walk, for rough ground and a heavy pack', () => {
    expect(MIN_FLAT_PACE_MPH).toBeLessThan(STANDARD_FLAT_PACE_MPH)
  })
})

/**
 * The consequence of that grid, pinned so nobody "fixes" it.
 *
 * 5 km/h is 3.1069 mph, which is not a multiple of 0.1 either - the finer step
 * moved the nearest stop from 3.0 to 3.1 without putting the standard ON the
 * grid. Snapping it there would make a fresh install disagree with the rule it
 * claims to use, the exact property the two-term design exists to protect.
 */
describe('the standard sits off the grid, at any step', () => {
  it('is not reachable by dragging, so Reset is the way back', () => {
    const offGrid =
      Math.abs(
        STANDARD_FLAT_PACE_MPH / FLAT_PACE_STEP_MPH -
          Math.round(STANDARD_FLAT_PACE_MPH / FLAT_PACE_STEP_MPH),
      ) > 1e-9
    expect(offGrid).toBe(true)
  })

  it('is not standard at either neighbouring stop', () => {
    // 3.1 and 3.2 bracket it. Neither is the rule, and isStandardPace says so
    // - which is what makes the Reset control load-bearing rather than a
    // convenience. 3.1 is the interesting one: it prints the SAME estimate as
    // the standard, so the baseline line stays silent while Reset does not.
    for (const stop of [3.1, 3.2]) {
      expect(isStandardPace({ ...STANDARD_PACE, flatPaceMph: stop })).toBe(false)
    }
  })

  it('still IS exactly 5 km/h, which is the thing worth protecting', () => {
    expect(STANDARD_FLAT_PACE_MPH * 1.609344).toBeCloseTo(5, 9)
  })

  it('survives a round trip through the store, off-grid and all', () => {
    writeStoredPace(STANDARD_PACE)
    expect(isStandardPace(readStoredPace())).toBe(true)
    clearStoredPace()
  })
})
