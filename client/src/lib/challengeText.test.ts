import { afterEach, describe, expect, it } from 'vitest'
import { formatDay, formatMoment, itemMeta, statusLine } from './challengeText'
import { ATC_CHALLENGE } from './challenges.fixtures'

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

// features/VOLUNTEERING.md §5 as the handoff restates it for challenges:
// never comparative, never a lack-state (ChallengeDetail.test.tsx's regex).
const FORBIDDEN =
  /other hikers|behind|streak|\brank|leaderboard|you haven[’']t|left to go|remaining/i

const item = (id: string) => ATC_CHALLENGE.items.find((entry) => entry.id === id)!

describe('a row’s sub-line names a place or a walk, or is absent (#1961)', () => {
  it('prints nothing under an at-home item - never "at home"', () => {
    expect(itemMeta(item('trivia-quiz'))).toBe('')
  })

  it('prints the place under a place, and says when it is off the trail', () => {
    expect(itemMeta(item('mcafee-knob'))).toBe('McAfee Knob Summit')
    expect(itemMeta(item('monson-visitor-center'))).toMatch(/off the trail$/)
  })

  it('still says how a self-tagging item is done', () => {
    expect(itemMeta(item('summit-4000'))).toBe('from the elevation profile')
  })
})

describe('the one status line under a joined list (#1961)', () => {
  it.each([
    { apiConfigured: false, signedIn: false },
    { apiConfigured: true, signedIn: false },
    { apiConfigured: true, signedIn: true },
  ])('is one sentence, names the phone, and never a name - %o', (state) => {
    const line = statusLine(ATC_CHALLENGE, state)
    expect(line).toMatch(/^Saved on this phone/)
    expect(line).not.toMatch(FORBIDDEN)
    expect(line).not.toMatch(/\n/)
    expect(line.length).toBeLessThan(110)
  })

  it('promises no server while none is configured, and no count without one', () => {
    const line = statusLine(ATC_CHALLENGE, { apiConfigured: false, signedIn: true })
    expect(line).toMatch(/until OurHike’s server is running/)
    expect(line).not.toMatch(/counted/)
  })

  it('says the club sees a count and never a name once there is a server', () => {
    const line = statusLine(ATC_CHALLENGE, { apiConfigured: true, signedIn: true })
    expect(line).toMatch(/counted for the ATC/)
    expect(line).toMatch(/never by name/)
  })
})
