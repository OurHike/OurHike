import { afterEach, describe, expect, it } from 'vitest'
import { formatDay, formatMoment } from './challengeText'

// The suite runs in UTC (vite.config.ts), where a UTC date and the hiker's
// own date agree and a day read off the wrong clock cannot show. These run
// in New York, where after 8 pm in summer they disagree.
const SUITE_TZ = process.env.TZ

afterEach(() => {
  process.env.TZ = SUITE_TZ
})

describe('a tag’s day, on the hiker’s own clock', () => {
  it('prints a tag made at 8:30 pm in New York as that day, not the next', () => {
    process.env.TZ = 'America/New_York'
    // 8:30 pm EDT on Jul 14 is 00:30 UTC on Jul 15 - the ISO string a tag keeps.
    const at = '2027-07-15T00:30:00.000Z'
    expect(formatDay(at)).toBe('Jul 14')
    expect(formatMoment(at)).toBe('Jul 14 · 8:30 pm')
  })

  it('prints a bare calendar date as written, in any zone', () => {
    process.env.TZ = 'America/New_York'
    expect(formatDay('2027-09-01')).toBe('Sep 1')
  })
})
