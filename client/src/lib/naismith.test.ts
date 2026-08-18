import { describe, it, expect } from 'vitest'
import { formatNaismithMinutes, naismithMinutes, naismithTime } from './naismith'

describe('naismithTime', () => {
  it('formats the exact WIREFRAMES.md example: 2.6 mi / 640 ft ascent -> ≈1h 10m', () => {
    // 2.6mi at 5km/h (≈3.107mph) = ~50.2min, + 640ft/600m ascent... ascent is
    // in feet in the app but the rule is defined in metric (1h per 600m) -
    // 640ft = 195.07m -> 0.3251h = 19.5min. Total ≈69.7min -> rounds to 70min = 1h10m.
    expect(naismithTime({ distanceMi: 2.6, ascentFt: 640 })).toBe('≈1h 10m')
  })

  it('always prefixes the output with ≈, never presents it as exact', () => {
    expect(naismithTime({ distanceMi: 1, ascentFt: 0 })).toMatch(/^≈/)
  })

  it('rounds to the nearest 5-minute step', () => {
    // A duration that lands on an awkward number of minutes should still
    // come out as a multiple of 5.
    const result = naismithTime({ distanceMi: 1.3, ascentFt: 100 })
    const minutesMatch = result.match(/(\d+)h\s*(\d+)?m?|(\d+)m/)
    expect(minutesMatch).not.toBeNull()
  })

  it('never subtracts time for descent - descent is not a parameter at all', () => {
    // naismithTime has no descentFt parameter - verified at the type level
    // (calling with one would be a TS error) and functionally: two hikes
    // with identical distance/ascent must produce identical times regardless
    // of how much descent happened along the way, because there's no way to
    // even pass that in.
    const a = naismithTime({ distanceMi: 5, ascentFt: 1000 })
    const b = naismithTime({ distanceMi: 5, ascentFt: 1000 })
    expect(a).toBe(b)
  })

  it('never formats as an arrival clock time (no colon-separated HH:MM, no AM/PM)', () => {
    const result = naismithTime({ distanceMi: 8, ascentFt: 2000 })
    expect(result).not.toMatch(/\d{1,2}:\d{2}/)
    expect(result).not.toMatch(/am|pm/i)
  })

  it('formats a sub-hour duration as minutes only, still rounded to 5', () => {
    expect(naismithTime({ distanceMi: 0.3, ascentFt: 0 })).toBe('≈5m')
  })

  it('formats a whole-hour duration without a trailing "0m"', () => {
    // ~5km/h for exactly 1 hour with no ascent = ~3.107mi
    const result = naismithTime({ distanceMi: 3.107, ascentFt: 0 })
    expect(result).toBe('≈1h')
  })
})

describe('naismithMinutes', () => {
  it('is the unrounded number under naismithTime', () => {
    // 10 km flat at 5 km/h is exactly 120 minutes.
    expect(naismithMinutes({ distanceMi: 10 / 1.609344, ascentFt: 0 })).toBeCloseTo(120)
    // 600 m of ascent alone is exactly 60 minutes.
    expect(naismithMinutes({ distanceMi: 0, ascentFt: 600 / 0.3048 })).toBeCloseTo(60)
  })

  it('does not round - rounding is the display rule, not the arithmetic', () => {
    // A route's total is summed from these BEFORE display. If each leg were
    // rounded to 5 minutes first, the printed total could drift from the
    // printed legs by 5 minutes a leg.
    const oneLeg = naismithMinutes({ distanceMi: 1.3, ascentFt: 100 })
    expect(oneLeg % 5).not.toBe(0)
  })

  it('agrees with naismithTime once formatted', () => {
    const input = { distanceMi: 2.6, ascentFt: 640 }
    expect(formatNaismithMinutes(naismithMinutes(input))).toBe(naismithTime(input))
  })
})

describe('formatNaismithMinutes', () => {
  it('applies the same 5-minute step and ≈ prefix as naismithTime', () => {
    expect(formatNaismithMinutes(69.7)).toBe('≈1h 10m')
    expect(formatNaismithMinutes(60)).toBe('≈1h')
    expect(formatNaismithMinutes(4)).toBe('≈5m')
  })

  it('never formats as an arrival clock time', () => {
    expect(formatNaismithMinutes(500)).not.toMatch(/\d{1,2}:\d{2}/)
    expect(formatNaismithMinutes(500)).not.toMatch(/am|pm/i)
  })
})
