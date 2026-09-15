import { describe, it, expect } from 'vitest'
import {
  NEARBY_CREW_MILES,
  OPPORTUNITIES_STALE_MS,
  WORK_PROJECT_WINDOW_DAYS,
  crewOffWalkLine,
  crewWalkPositionLine,
  crewsAlongWalk,
  crewsOutToday,
  workdayCalendarMonth,
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

// --- Crews against a walk (#1440, D18, frame 14k) --------------------------

describe('crews out today', () => {
  it('counts a multi-day crew on every day it covers', () => {
    // The same `ends_on` rule the list keeps, so a crew mid-weekend is still
    // out on the Sunday rather than disappearing the morning after it began.
    const weekend = project({ id: 'w', starts_on: '2026-09-12', ends_on: '2026-09-13' })

    expect(crewsOutToday([weekend], new Date('2026-09-12T14:00:00Z'))).toHaveLength(1)
    expect(crewsOutToday([weekend], new Date('2026-09-13T06:00:00Z'))).toHaveLength(1)
    expect(crewsOutToday([weekend], new Date('2026-09-14T06:00:00Z'))).toHaveLength(0)
    expect(crewsOutToday([weekend], new Date('2026-09-11T23:00:00Z'))).toHaveLength(0)
  })

  it('leaves out a crew that is not running', () => {
    // Cancelled and completed are not "out today" in any reading, and a
    // cancelled crew printed as one is this feature's own failure mode.
    const today = new Date('2026-09-12T09:00:00Z')
    const running = { starts_on: '2026-09-12', ends_on: '2026-09-12' }
    const rows = [
      project({ id: 'off', status: 'cancelled', ...running }),
      project({ id: 'done', status: 'completed', ...running }),
      project({ id: 'on', ...running }),
    ]

    expect(crewsOutToday(rows, today).map((row) => row.id)).toEqual(['on'])
  })
})

describe('crews along the walk', () => {
  const WALK = { start: 100, end: 110 }

  it('places a crew as a mile OF THE WALK, not as a trail marker', () => {
    // "mile 4.1 of your walk" is the number that answers "will I meet them".
    // A trail marker cannot say how far into somebody's day a crew is.
    const { onRoute } = crewsAlongWalk([project({ id: 'a', mile: 104.1 })], WALK)

    expect(onRoute).toHaveLength(1)
    expect(onRoute[0].mileOfWalk).toBeCloseTo(4.1)
    expect(crewWalkPositionLine(onRoute[0].mileOfWalk)).toBe('mile 4.1 of your walk')
  })

  it('measures from where the hiker set off, walking either way', () => {
    // `start > end` is a southbound walk and not a mistake, so the same crew
    // is 4.1 miles into a northbound day and 5.9 into the southbound one.
    const south = crewsAlongWalk([project({ id: 'a', mile: 104.1 })], {
      start: 110,
      end: 100,
    })

    expect(south.onRoute[0].mileOfWalk).toBeCloseTo(5.9)
  })

  it('splits the ones near the walk from the ones on it', () => {
    const { onRoute, nearby } = crewsAlongWalk(
      [
        project({ id: 'on', mile: 105 }),
        project({ id: 'near', mile: 113.2 }),
        project({ id: 'far', mile: 400 }),
      ],
      WALK,
    )

    expect(onRoute.map((row) => row.project.id)).toEqual(['on'])
    expect(nearby.map((row) => row.project.id)).toEqual(['near'])
    expect(crewOffWalkLine(nearby[0].offRouteMi)).toBe('3.2 trail mi off your walk')
  })

  it('leaves a crew with no mile out of BOTH headings', () => {
    // With no mile there is no way to say a crew is on the route, and
    // printing it under either heading would claim a relationship nobody
    // established. It keeps its place in the full list instead - the only
    // surface that can hold it honestly.
    const { onRoute, nearby } = crewsAlongWalk(
      [project({ id: 'unplaced', mile: null })],
      WALK,
    )

    expect(onRoute).toEqual([])
    expect(nearby).toEqual([])
  })

  it('orders the walk by where they will be met, and the rest by distance', () => {
    const { onRoute, nearby } = crewsAlongWalk(
      [
        project({ id: 'later', mile: 108 }),
        project({ id: 'sooner', mile: 102 }),
        project({ id: 'further', mile: 118 }),
        project({ id: 'closer', mile: 112 }),
      ],
      WALK,
    )

    expect(onRoute.map((row) => row.project.id)).toEqual(['sooner', 'later'])
    expect(nearby.map((row) => row.project.id)).toEqual(['closer', 'further'])
  })

  it('stops calling a crew nearby past the threshold it was given', () => {
    const justInside = crewsAlongWalk(
      [project({ id: 'a', mile: 110 + NEARBY_CREW_MILES })],
      WALK,
    )
    const justOutside = crewsAlongWalk(
      [project({ id: 'a', mile: 110 + NEARBY_CREW_MILES + 0.1 })],
      WALK,
    )

    expect(justInside.nearby).toHaveLength(1)
    expect(justOutside.nearby).toHaveLength(0)
  })
})

// --- The calendar's own honesty (#1440, D21, frame 14j) --------------------

describe('the crews calendar', () => {
  // Today is Saturday 12 September 2026; the published window runs to the
  // 26th, so the 27th onward is a month the file was never asked about.
  const TODAY = new Date('2026-09-12T09:00:00Z')

  function cellOn(month: ReturnType<typeof workdayCalendarMonth>, day: number) {
    return month.cells.find((cell) => cell.dayOfMonth === day)
  }

  it('draws the published window’s edge, so an empty cell out there is not "no crew"', () => {
    // THE REASON THIS NEEDED DESIGNING rather than dropping a month grid in:
    // an empty cell past the horizon reads as "no crew that day" when the
    // truth is "nobody has said". Three states, because a month holds three
    // different kinds of nothing.
    const month = workdayCalendarMonth([], TODAY)

    expect(cellOn(month, 11)?.state).toBe('past')
    expect(cellOn(month, 12)?.state).toBe('open')
    expect(cellOn(month, 26)?.state).toBe('open')
    expect(cellOn(month, 27)?.state).toBe('beyond')
  })

  it('separates the past from the unknown', () => {
    // Two different absences, two treatments: the past is over rather than
    // unknown, which is why it is greyed and not hatched.
    const month = workdayCalendarMonth([], TODAY)
    const states = new Set(month.cells.map((cell) => cell.state))

    expect(states).toEqual(new Set(['past', 'open', 'beyond']))
  })

  it('dots every day a multi-day crew covers', () => {
    // The same `ends_on` rule the list keeps, so a crew mid-weekend still
    // shows on the Sunday.
    const month = workdayCalendarMonth(
      [project({ id: 'w', starts_on: '2026-09-12', ends_on: '2026-09-14' })],
      TODAY,
    )

    expect(cellOn(month, 12)?.crews).toHaveLength(1)
    expect(cellOn(month, 13)?.crews).toHaveLength(1)
    expect(cellOn(month, 14)?.crews).toHaveLength(1)
    expect(cellOn(month, 15)?.crews).toHaveLength(0)
  })

  it('leaves a cancelled crew out of the grid entirely', () => {
    const month = workdayCalendarMonth(
      [
        project({
          id: 'off',
          status: 'cancelled',
          starts_on: '2026-09-12',
          ends_on: '2026-09-12',
        }),
      ],
      TODAY,
    )

    expect(cellOn(month, 12)?.crews).toHaveLength(0)
  })

  it('marks the weekends, which is the first thing a hiker scans for', () => {
    const month = workdayCalendarMonth([], TODAY)

    expect(cellOn(month, 12)?.weekend).toBe(true)
    expect(cellOn(month, 13)?.weekend).toBe(true)
    expect(cellOn(month, 14)?.weekend).toBe(false)
  })

  it('leads the grid in on a Monday', () => {
    // 1 September 2026 is a Tuesday, so one blank before it.
    const month = workdayCalendarMonth([], TODAY)

    expect(month.blanks).toBe(1)
    expect(month.cells).toHaveLength(30)
  })
})
