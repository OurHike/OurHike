import { describe, it, expect } from 'vitest'
import {
  hoursCsv,
  hoursTotals,
  stateLabel,
  type VolunteerHoursSummary,
} from './volunteerHours'

// #761's display rules, held: which states count (the 2026-08-20 decision -
// claimed counts until disputed), the label that always travels with the
// number, and an export that includes every state LABELED so the first
// export cannot answer the policy question by accident.

function record(overrides: Partial<VolunteerHoursSummary>): VolunteerHoursSummary {
  return {
    id: crypto.randomUUID(),
    club_id: null,
    worked_on: '2026-08-18',
    hours: 4,
    work_project_id: null,
    activity: 'maintenance',
    note: null,
    mile: null,
    lat: null,
    lon: null,
    state: 'claimed',
    confirmed_at: null,
    recorded_at: '2026-08-18T22:00:00Z',
    ...overrides,
  }
}

describe('hoursTotals', () => {
  it('counts claimed and confirmed, and drops disputed', () => {
    const totals = hoursTotals([
      record({ hours: 4, state: 'claimed' }),
      record({ hours: 3, state: 'confirmed', worked_on: '2026-08-17' }),
      record({ hours: 8, state: 'disputed', worked_on: '2026-08-16' }),
    ])

    expect(totals.countedHours).toBe(7)
    expect(totals.unconfirmedHours).toBe(4)
  })

  it('counts days as distinct calendar days, never as points', () => {
    const totals = hoursTotals([
      record({ hours: 3, worked_on: '2026-08-18' }),
      record({ hours: 2, worked_on: '2026-08-18' }),
      record({ hours: 5, worked_on: '2026-08-17' }),
    ])

    expect(totals.daysWorked).toBe(2)
  })

  it('computes nothing comparative and no composite score', () => {
    // The four rules, structurally: the totals object holds hours, the
    // unconfirmed slice, and days - and nothing else to maximise.
    const totals = hoursTotals([record({})])

    expect(Object.keys(totals).sort()).toEqual([
      'countedHours',
      'daysWorked',
      'unconfirmedHours',
    ])
  })
})

describe('stateLabel', () => {
  it('says each state in a volunteer’s own terms', () => {
    expect(stateLabel('claimed')).toMatch(/not yet confirmed/i)
    expect(stateLabel('confirmed')).toMatch(/confirmed by the club/i)
    expect(stateLabel('disputed')).toMatch(/disputed/i)
  })
})

describe('hoursCsv', () => {
  it('exports every state, labeled, so a reader can tell a claim from a grant', () => {
    const csv = hoursCsv([
      record({ hours: 4, state: 'claimed' }),
      record({ hours: 3, state: 'disputed', worked_on: '2026-08-16' }),
    ])

    const lines = csv.trim().split('\n')
    expect(lines[0]).toBe('worked_on,hours,activity,state,club_confirmed_at,mile,note')
    expect(lines[1]).toContain('claimed')
    expect(lines[2]).toContain('disputed')
  })

  it('quotes a note that carries commas or quotes rather than corrupting the row', () => {
    const csv = hoursCsv([
      record({ note: 'Cleared blowdowns, fixed the "old" waterbar' }),
    ])

    expect(csv).toContain('"Cleared blowdowns, fixed the ""old"" waterbar"')
  })
})
