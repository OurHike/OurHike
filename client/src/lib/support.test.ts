import { beforeEach, describe, expect, it } from 'vitest'
import {
  ASK_ON_DAY,
  PENDING_GRACE_DAYS,
  dollars,
  readLocalChoice,
  shouldAsk,
  writeZeroChoice,
  type SupportSummary,
} from './support'
import { NUDGES, nudgeFor } from './supportNudges'

// When the support ask opens, and what the $0 nudge says (#1876, the
// maintainer's poll of 2026-10-23).

beforeEach(() => localStorage.clear())

const NOW = new Date('2026-10-23T12:00:00')

function server(over: Partial<SupportSummary>): SupportSummary {
  return {
    status: 'none',
    amount_cents: null,
    cadence: null,
    provider: null,
    provider_label: null,
    email: null,
    chosen_at: null,
    started_at: null,
    period_end: null,
    stop_requested_at: null,
    ended_at: null,
    supporting: false,
    can_stop: false,
    can_choose: true,
    ...over,
  }
}

const base = {
  now: NOW,
  apiConfigured: true,
  online: true,
  server: null,
  days: ASK_ON_DAY,
  local: null,
}

describe('shouldAsk', () => {
  it('asks on the fifth day of the year, and not on the fourth', () => {
    expect(shouldAsk(base)).toBe(true)
    expect(shouldAsk({ ...base, days: ASK_ON_DAY - 1 })).toBe(false)
  })

  it('waits while the phone has no signal, which mostly means on trail', () => {
    expect(shouldAsk({ ...base, online: false })).toBe(false)
  })

  it('never asks in a build with no backend, so a paid choice is verifiable from day one', () => {
    expect(shouldAsk({ ...base, apiConfigured: false, days: 200 })).toBe(false)
  })

  it('does not ask again after $0 this year, and does ask next year', () => {
    const local = { year: 2026, chosenAt: '2026-06-01T12:00:00.000Z' }
    expect(shouldAsk({ ...base, local })).toBe(false)
    expect(shouldAsk({ ...base, now: new Date('2027-08-01T12:00:00'), local })).toBe(true)
  })

  it('does not ask a hiker the server says is supporting, whatever the state', () => {
    for (const status of [
      'active',
      'paused',
      'cancel_scheduled',
      'stop_requested',
    ] as const) {
      expect(
        shouldAsk({
          ...base,
          server: server({ status, amount_cents: 6000, supporting: true }),
        }),
      ).toBe(false)
    }
  })

  it(`waits ${PENDING_GRACE_DAYS} days on a paid choice nobody completed, then asks again`, () => {
    const pending = server({
      status: 'pending',
      amount_cents: 6000,
      chosen_at: '2026-10-10T12:00:00Z',
    })
    expect(shouldAsk({ ...base, server: pending })).toBe(false)
    expect(
      shouldAsk({ ...base, server: { ...pending, chosen_at: '2026-09-01T12:00:00Z' } }),
    ).toBe(true)
  })

  it('does not ask again the year a hiker pressed Stop', () => {
    const stopped = server({ status: 'stopped', ended_at: '2026-09-01T12:00:00Z' })
    expect(shouldAsk({ ...base, server: stopped })).toBe(false)
    expect(
      shouldAsk({ ...base, now: new Date('2027-10-23T12:00:00'), server: stopped }),
    ).toBe(true)
  })
})

describe('the $0 answer on this phone', () => {
  it('records the year it covers', () => {
    writeZeroChoice(NOW)
    expect(readLocalChoice()).toMatchObject({ year: 2026 })
  })
})

describe('the $0 nudge', () => {
  it('shows a different line each year on the same phone', () => {
    const seen = new Set(
      [2026, 2027, 2028, 2029, 2030].map(
        (year) => nudgeFor(new Date(year, 5, 1), 3).title,
      ),
    )
    expect(seen.size).toBe(NUDGES.length)
  })

  it('names the amount on every paid button, whatever the joke around it', () => {
    for (const nudge of NUDGES) {
      expect(nudge.low).toContain('$12 a year')
      expect(nudge.mid).toContain('$60 a year')
      expect(nudge.zero).toContain('$0')
    }
  })

  it('never puts a number on what a hiker costs to serve (#393 measured about $0)', () => {
    for (const nudge of NUDGES) {
      expect(`${nudge.title} ${nudge.body}`).not.toMatch(/cost|covers your|your share/i)
    }
  })
})

describe('dollars', () => {
  it('writes whole dollars', () => {
    expect([0, 1200, 6000, 12000].map(dollars)).toEqual(['$0', '$12', '$60', '$120'])
  })
})
