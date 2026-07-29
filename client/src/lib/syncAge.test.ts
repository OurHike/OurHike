import { describe, it, expect } from 'vitest'
import { syncAgeLabel } from './syncAge'

// Fixed clock throughout - every case is a fixed offset from NOW rather than
// from a live Date.now(), so the boundary cases mean exactly what they say.
// (lib/staleness.test.ts learned this one the hard way.)
const NOW = new Date('2026-07-29T12:00:00.000Z')

function ago(ms: number): Date {
  return new Date(NOW.getTime() - ms)
}

const SECOND = 1000
const MINUTE = 60 * SECOND
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

describe('syncAgeLabel', () => {
  it('says "never synced" rather than going blank when it never has', () => {
    expect(syncAgeLabel(null, NOW)).toBe('never synced')
  })

  it('says "just now" for a sync inside the last minute', () => {
    expect(syncAgeLabel(ago(30 * SECOND), NOW)).toBe('just now')
  })

  it('switches to minutes exactly at the one-minute mark', () => {
    expect(syncAgeLabel(ago(MINUTE), NOW)).toBe('1m ago')
  })

  it('switches to hours exactly at the one-hour mark', () => {
    expect(syncAgeLabel(ago(HOUR), NOW)).toBe('1h ago')
  })

  it('switches to days exactly at the 24-hour mark', () => {
    expect(syncAgeLabel(ago(DAY), NOW)).toBe('1d ago')
  })

  it('rounds down rather than up, so it never overstates how fresh the data is', () => {
    // 59 minutes is still "59m ago", not "1h ago" - and 47 hours is "1d ago",
    // never "2d". Overstating freshness is the direction that misleads.
    expect(syncAgeLabel(ago(59 * MINUTE), NOW)).toBe('59m ago')
    expect(syncAgeLabel(ago(47 * HOUR), NOW)).toBe('1d ago')
  })

  it('keeps counting for very old data instead of capping', () => {
    expect(syncAgeLabel(ago(90 * DAY), NOW)).toBe('90d ago')
  })
})
