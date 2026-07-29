import { describe, it, expect } from 'vitest'
import { stalenessTier } from './staleness'

// See WIREFRAMES.md's Data staleness section: Fresh <=~14 days, Ageing
// ~14-60 days, Stale/never >60 days or never confirmed. Independent of a
// separate verified/unverified confidence flag - staleness is "when a human
// last said it was fine," confidence is "was this ever verified to exist"
// - a dashed pin (unverified) can still be Fresh if recently confirmed, and
// a verified POI can still go Stale if nobody's confirmed it in months.

const DAY_MS = 24 * 60 * 60 * 1000
function daysAgo(n: number): Date {
  return new Date(Date.now() - n * DAY_MS)
}

describe('stalenessTier', () => {
  it('is fresh at exactly 14 days (boundary, inclusive)', () => {
    expect(stalenessTier(daysAgo(14))).toBe('fresh')
  })

  it('is ageing just past the 14-day boundary', () => {
    expect(stalenessTier(daysAgo(15))).toBe('ageing')
  })

  it('is ageing at exactly 60 days (boundary, inclusive)', () => {
    expect(stalenessTier(daysAgo(60))).toBe('ageing')
  })

  it('is stale just past the 60-day boundary', () => {
    expect(stalenessTier(daysAgo(61))).toBe('stale')
  })

  it('is fresh for something confirmed moments ago', () => {
    expect(stalenessTier(daysAgo(0))).toBe('fresh')
  })

  it('is stale when never confirmed at all (null)', () => {
    expect(stalenessTier(null)).toBe('stale')
  })

  it.each([
    ['verified', true],
    ['verified', false],
    ['unverified', true],
    ['unverified', false],
  ])(
    'staleness is independent of the verified/unverified confidence flag - %s POIs with lastConfirmed=%s days-ago-ness produce the same tier either way',
    (_label, isRecent) => {
      const lastConfirmed = isRecent ? daysAgo(0) : daysAgo(100)
      const expectedTier = isRecent ? 'fresh' : 'stale'
      // confidence (verified vs unverified) is a wholly separate concept
      // from staleness - stalenessTier takes only the date, proving by
      // construction that verified/unverified can't influence it.
      expect(stalenessTier(lastConfirmed)).toBe(expectedTier)
    },
  )
})
