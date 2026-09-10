import { describe, it, expect } from 'vitest'
import {
  OPPORTUNITIES_STALE_MS,
  WORK_PROJECT_WINDOW_DAYS,
  opportunitiesUsable,
  sortWorkProjects,
  upcomingWorkProjects,
  workProjectDates,
  workdayRow,
  workdayWindowSpan,
  type WorkProjectSummary,
  type WorkdayWindowId,
} from './workProjects'

// #760's rules, held: the fourteen-day window, the 48-hour ceiling past
// which rows stop being called opportunities, and nearest-first ordering
// that never invents a distance for a row nobody placed.

const NOW = new Date('2026-08-20T12:00:00Z')

function project(overrides: Partial<WorkProjectSummary>): WorkProjectSummary {
  return {
    id: crypto.randomUUID(),
    club_name: 'NY-NJ Trail Conference',
    title: 'Bear Mountain steps',
    description: null,
    lat: 41.31,
    lon: -73.99,
    mile: 1407.6,
    starts_on: '2026-08-24',
    ends_on: '2026-08-24',
    status: 'upcoming',
    capacity: null,
    signup_mode: 'contact',
    signup_contact: 'mailto:volunteer@example.org',
    ...overrides,
  }
}

describe('upcomingWorkProjects', () => {
  it('keeps a workday inside the window and drops one past it', () => {
    const inside = project({ starts_on: '2026-09-01', ends_on: '2026-09-01' })
    const beyond = project({ starts_on: '2026-09-20', ends_on: '2026-09-20' })

    expect(upcomingWorkProjects([inside, beyond], NOW)).toEqual([inside])
    expect(WORK_PROJECT_WINDOW_DAYS).toBe(14)
  })

  it('keeps an event already running - a crew mid-weekend still takes hands', () => {
    const running = project({ starts_on: '2026-08-19', ends_on: '2026-08-21' })

    expect(upcomingWorkProjects([running], NOW)).toEqual([running])
  })

  it('drops what is over, cancelled, or completed', () => {
    const over = project({ starts_on: '2026-08-10', ends_on: '2026-08-11' })
    const cancelled = project({ status: 'cancelled' })
    const completed = project({ status: 'completed' })

    expect(upcomingWorkProjects([over, cancelled, completed], NOW)).toEqual([])
  })
})

describe('the day windows (#1373, frame 14d)', () => {
  // NOW is Thursday 20 August; the coming weekend is Saturday 22 and
  // Sunday 23.
  it('reads "this weekend" as the coming Saturday and Sunday, in UTC days', () => {
    expect(workdayWindowSpan('weekend', NOW)).toEqual({
      from: Date.UTC(2026, 7, 22),
      to: Date.UTC(2026, 7, 24),
    })
    // On the Sunday itself it is still this weekend, not the next.
    expect(workdayWindowSpan('weekend', new Date('2026-08-23T09:00:00Z'))).toEqual({
      from: Date.UTC(2026, 7, 22),
      to: Date.UTC(2026, 7, 24),
    })
  })

  it('filters each window to its own days, and drops what is over in every window', () => {
    const saturday = project({
      id: 'sat',
      starts_on: '2026-08-22',
      ends_on: '2026-08-22',
    })
    const monday = project({ id: 'mon', starts_on: '2026-08-24', ends_on: '2026-08-24' })
    const next = project({ id: 'next', starts_on: '2026-09-12', ends_on: '2026-09-12' })
    const over = project({ id: 'over', starts_on: '2026-08-18', ends_on: '2026-08-19' })
    const all = [saturday, monday, next, over]

    const ids = (window: WorkdayWindowId, now = NOW) =>
      upcomingWorkProjects(all, now, window).map((p) => p.id)

    expect(ids('fortnight')).toEqual(['sat', 'mon'])
    expect(ids('weekend')).toEqual(['sat'])
    expect(ids('month')).toEqual(['sat', 'mon', 'next'])
    // Sunday morning: Saturday's workday is over and stays off the weekend
    // list; a Sunday one would still be on it.
    const sunday = project({ id: 'sun', starts_on: '2026-08-23', ends_on: '2026-08-23' })
    expect(
      upcomingWorkProjects(
        [saturday, sunday],
        new Date('2026-08-23T09:00:00Z'),
        'weekend',
      ).map((p) => p.id),
    ).toEqual(['sun'])
  })

  it('prints a row the way the tab does, and a distance only with a fix and a placed row', () => {
    const placed = project({ capacity: 12 })
    const row = workdayRow(placed, 1400)
    expect(row).toMatchObject({
      title: 'Bear Mountain steps',
      club: 'NY-NJ Trail Conference',
      dates: 'Aug 24',
      capacity: 12,
      contact: 'mailto:volunteer@example.org',
    })
    expect(row?.awayMi).toBeCloseTo(7.6)
    expect(workdayRow(placed, null)?.awayMi).toBeNull()
    expect(workdayRow(project({ mile: null }), 1400)?.awayMi).toBeNull()
    expect(workdayRow(project({ lat: null }), 1400)).toBeNull()
  })
})

describe('opportunitiesUsable', () => {
  it('accepts a bake younger than the ceiling and refuses one older', () => {
    const fresh = new Date(NOW.getTime() - OPPORTUNITIES_STALE_MS + 60_000)
    const stale = new Date(NOW.getTime() - OPPORTUNITIES_STALE_MS - 60_000)

    expect(opportunitiesUsable(fresh, NOW)).toBe(true)
    expect(opportunitiesUsable(stale, NOW)).toBe(false)
  })
})

describe('sortWorkProjects', () => {
  it('sorts nearest-first when the hiker has a trail mile', () => {
    const near = project({ id: 'near', mile: 1402.0 })
    const far = project({ id: 'far', mile: 1500.0 })

    const sorted = sortWorkProjects([far, near], 1400.0)

    expect(sorted.map((p) => p.id)).toEqual(['near', 'far'])
  })

  it('sorts soonest-first with no fix - the calendar is the only honest distance', () => {
    const later = project({ id: 'later', starts_on: '2026-08-30', ends_on: '2026-08-30' })
    const sooner = project({
      id: 'sooner',
      starts_on: '2026-08-22',
      ends_on: '2026-08-22',
    })

    expect(sortWorkProjects([later, sooner], null).map((p) => p.id)).toEqual([
      'sooner',
      'later',
    ])
  })

  it('never invents a distance: unplaced rows sort after placed ones', () => {
    const placed = project({ id: 'placed', mile: 1500.0 })
    const unplaced = project({ id: 'unplaced', mile: null })

    expect(sortWorkProjects([unplaced, placed], 1400.0).map((p) => p.id)).toEqual([
      'placed',
      'unplaced',
    ])
  })
})

describe('workProjectDates', () => {
  it('prints one day once and a range as a range, in UTC', () => {
    expect(workProjectDates(project({}))).toBe('Aug 24')
    expect(
      workProjectDates(project({ starts_on: '2026-08-29', ends_on: '2026-08-30' })),
    ).toBe('Aug 29–Aug 30')
  })
})

// The stale window guards the whole feature; a test naming the constant is
// what makes moving it a decision rather than a drive-by. @unvalidated per
// the module - "about 48 hours" is the design doc's phrase, not a finding.
it('the ceiling is 48 hours until somebody establishes better', () => {
  expect(OPPORTUNITIES_STALE_MS).toBe(48 * 60 * 60 * 1000)
})
