import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { stalenessTier } from './staleness'

// See WIREFRAMES.md's Data staleness section: Fresh <=~14 days, Ageing
// ~14-60 days, Stale/never >60 days or never confirmed. Independent of a
// separate verified/unverified confidence flag - staleness is "when a human
// last said it was fine," confidence is "was this ever verified to exist"
// - a dashed pin (unverified) can still be Fresh if recently confirmed, and
// a verified POI can still go Stale if nobody's confirmed it in months.

const DAY_MS = 24 * 60 * 60 * 1000

// stalenessTier reads Date.now() itself, so `daysAgo(n)` and the module each
// take their own clock reading. Under a real clock those two readings land in
// different milliseconds every so often, which makes `daysAgo(14)` actually
// mean "14 days and a few ms ago" and flips the INCLUSIVE boundary cases to
// the next tier. That is a real intermittent failure, not a theoretical one -
// it took down CI on main once already at roughly a 1-in-6000 rate. Freezing
// the clock is what makes "exactly 14 days" exact, so these boundary
// assertions test the tier rule instead of a millisecond race.
const FROZEN_NOW = new Date('2026-07-29T12:00:00.000Z')

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(FROZEN_NOW)
})

afterEach(() => {
  vi.useRealTimers()
})

function daysAgo(n: number): Date {
  return new Date(Date.now() - n * DAY_MS)
}

function msAgo(ms: number): Date {
  return new Date(Date.now() - ms)
}

describe('stalenessTier', () => {
  it('is fresh at exactly 14 days (boundary, inclusive)', () => {
    expect(stalenessTier(daysAgo(14))).toBe('fresh')
  })

  it('is ageing one millisecond past the 14-day boundary - the boundary is exact, not approximate', () => {
    expect(stalenessTier(msAgo(14 * DAY_MS + 1))).toBe('ageing')
  })

  it('is ageing just past the 14-day boundary', () => {
    expect(stalenessTier(daysAgo(15))).toBe('ageing')
  })

  it('is ageing at exactly 60 days (boundary, inclusive)', () => {
    expect(stalenessTier(daysAgo(60))).toBe('ageing')
  })

  it('is stale one millisecond past the 60-day boundary - the boundary is exact, not approximate', () => {
    expect(stalenessTier(msAgo(60 * DAY_MS + 1))).toBe('stale')
  })

  it('is stale just past the 60-day boundary', () => {
    expect(stalenessTier(daysAgo(61))).toBe('stale')
  })

  it('is fresh for something confirmed moments ago', () => {
    expect(stalenessTier(daysAgo(0))).toBe('fresh')
  })

  it('is never - its own tier, not stale - when never confirmed at all (null)', () => {
    // Maintainer decision 2026-08-20 (recorded on #256): on a map with no
    // confirmation history yet, null-means-stale would render every pin
    // stale on day one and read as "nothing here is trustworthy". `stale`
    // now means "was confirmed, went quiet"; `never` means nobody has said.
    expect(stalenessTier(null)).toBe('never')
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
