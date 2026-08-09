import { describe, it, expect } from 'vitest'
import type { Closure } from './closureBanner'
import { closureSpanMiles, isBroadAdvisory, MAX_BAND_MILES } from './closureSpan'

// The two ends of the evidence, from features/ATC_TRAIL_UPDATES.md's measured
// table. Held as tests rather than as prose because they are what any future
// change to MAX_BAND_MILES has to keep true: the nine-mile closure a hiker
// walks around must stay drawable, and the 398-mile advisory must not.

function closure(overrides: Partial<Closure> = {}): Closure {
  return {
    id: 'c1',
    reason_type: 'storm_damage',
    note: null,
    status: 'closed',
    start_mile_marker: 476.6,
    end_mile_marker: 485.8,
    ...overrides,
  }
}

describe('closureSpanMiles', () => {
  it('measures a range', () => {
    // ATC's VA Creeper Trail closure, verbatim: "(NOBO miles 476.6 to 485.8)".
    expect(closureSpanMiles(closure())).toBeCloseTo(9.2, 5)
  })

  it('is zero for a point closure', () => {
    // ATC publishes several - a shelter, a footbridge - as one mile marker.
    // "(NOBO mile 1,026.7)", the Harpers Ferry footbridge.
    const point = closure({ start_mile_marker: 1026.7, end_mile_marker: 1026.7 })

    expect(closureSpanMiles(point)).toBe(0)
  })

  it('reads a reversed pair as the same span, not a negative one', () => {
    // A span is a span whichever order its ends arrive in. Signed arithmetic
    // here would make a reversed record look infinitely short and so always
    // drawable, which is the wrong way for this particular check to fail.
    const backwards = closure({ start_mile_marker: 485.8, end_mile_marker: 476.6 })

    expect(closureSpanMiles(backwards)).toBeCloseTo(9.2, 5)
  })
})

describe('isBroadAdvisory', () => {
  it('is true for ATC Hurricane Helene, the case this exists for', () => {
    // "(NOBO miles 239.4 to 637.8)" - 398 miles, a fifth of the trail. Drawn
    // as a band it swamps everything more specific.
    const helene = closure({ start_mile_marker: 239.4, end_mile_marker: 637.8 })

    expect(isBroadAdvisory(helene)).toBe(true)
  })

  it('is false for the nine-mile closure a hiker actually walks around', () => {
    // The whole point of the ceiling is that this one keeps its band. A cap
    // that suppressed this would have traded one buried warning for another.
    expect(isBroadAdvisory(closure())).toBe(false)
  })

  it('is false for a point closure', () => {
    expect(
      isBroadAdvisory(closure({ start_mile_marker: 1026.7, end_mile_marker: 1026.7 })),
    ).toBe(false)
  })

  it('draws a closure exactly at the ceiling', () => {
    // Inclusive on purpose. The number is provisional, so the boundary should
    // fall on the side that keeps showing the hiker something.
    const exact = closure({
      start_mile_marker: 100,
      end_mile_marker: 100 + MAX_BAND_MILES,
    })

    expect(isBroadAdvisory(exact)).toBe(false)
  })

  it('suppresses one just past it', () => {
    const over = closure({
      start_mile_marker: 100,
      end_mile_marker: 100 + MAX_BAND_MILES + 0.1,
    })

    expect(isBroadAdvisory(over)).toBe(true)
  })

  it('does not call a closure with unusable mile markers broad', () => {
    // A NaN span is a broken record, not a wide one, and calling it broad here
    // would hide a data fault behind a policy decision. map/closureLayers.ts
    // already declines to draw a closure the centerline index cannot place,
    // which is where this one stops.
    const broken = closure({ start_mile_marker: Number.NaN, end_mile_marker: 10 })

    expect(isBroadAdvisory(broken)).toBe(false)
  })
})

describe('the ceiling itself', () => {
  it('sits clear of both ends of the measured evidence', () => {
    // Not an arbitrary assertion about a constant: it is the one property the
    // number has to keep however the field-testing pass in #462 moves it.
    // 9.2 is ATC's longest drawable range, 398.4 their one undrawable advisory.
    expect(MAX_BAND_MILES).toBeGreaterThan(9.2)
    expect(MAX_BAND_MILES).toBeLessThan(398.4)
  })
})
