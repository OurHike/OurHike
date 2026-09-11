import { describe, it, expect } from 'vitest'
import {
  hoursCsv,
  hoursTotals,
  queuedHoursSummary,
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

// A day still in the outbox, as the logbook has to show it. The mapping is
// shared by the echo at log time and the restore at boot, so a change here
// moves both - which is the reason it is a function rather than two object
// literals in App.tsx.
describe('a queued day', () => {
  it('reads as claimed, carries the queue item’s own id and authored time, and keeps every optional field', () => {
    const summary = queuedHoursSummary({
      id: 'queued-1',
      authoredAt: '2026-09-11T14:00:00.000Z',
      volunteerHours: {
        worked_on: '2026-09-10',
        hours: 4,
        activity: 'maintenance',
        note: 'Cleared blowdowns',
        club_id: 'club-7',
        work_project_id: 'proj-3',
        mile: 1204.2,
        lat: 41.2,
        lon: -74.6,
      },
    })

    // CLAIMED IS THE HONEST STATE and the only one a queued day can have:
    // nobody has confirmed it, because it has not reached anybody yet.
    expect(summary.state).toBe('claimed')
    expect(summary.confirmed_at).toBeNull()
    // The queue item's id, so the server copy can replace the echo under the
    // same id once it lands (App.tsx's `hoursRecords`).
    expect(summary.id).toBe('queued-1')
    expect(summary.recorded_at).toBe('2026-09-11T14:00:00.000Z')
    expect(summary.hours).toBe(4)
    expect(summary.note).toBe('Cleared blowdowns')
    expect(summary.club_id).toBe('club-7')
    expect(summary.work_project_id).toBe('proj-3')
    expect(summary.mile).toBe(1204.2)
  })

  it('turns every absent optional into null rather than leaving it undefined', () => {
    // The logbook and the CSV both read these as `T | null`; an `undefined`
    // slipping through would print "undefined" in an export a club reads.
    const summary = queuedHoursSummary({
      id: 'queued-2',
      authoredAt: '2026-09-11T14:00:00.000Z',
      volunteerHours: { worked_on: '2026-09-10', hours: 2, activity: 'monitoring' },
    })

    expect(summary.club_id).toBeNull()
    expect(summary.work_project_id).toBeNull()
    expect(summary.note).toBeNull()
    expect(summary.mile).toBeNull()
    expect(summary.lat).toBeNull()
    expect(summary.lon).toBeNull()
  })

  it('counts in the totals the logbook prints, so a restored day is not a silent zero', () => {
    const restored = queuedHoursSummary({
      id: 'queued-3',
      authoredAt: '2026-09-11T14:00:00.000Z',
      volunteerHours: { worked_on: '2026-09-10', hours: 4, activity: 'maintenance' },
    })

    expect(hoursTotals([restored])).toMatchObject({
      daysWorked: 1,
      unconfirmedHours: 4,
    })
  })
})
