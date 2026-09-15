import { describe, it, expect } from 'vitest'
import {
  NEARBY_CREW_MILES,
  crewOffWalkLine,
  crewWalkPositionLine,
  crewsAlongWalk,
  crewsOutToday,
  workdayCalendarMonth,
} from './crews'
import type { WorkProjectSummary } from './workProjects'

// Crews measured against a hiker (#1440, D18, D21): who is out today, who is
// on the walk and who is merely near it, and the three kinds of nothing a
// month grid has to tell apart.
//
// Its own file because lib/crews.ts is its own module - see that file's
// header for why the split is a seam rather than a budget dodge.

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

// A HIKER'S DAY IS NOT UTC'S (#1447 review).
//
// The suite pins TZ=UTC (vite.config.ts, #323), so a real zone cannot be
// used and no test above could tell the two readings apart - which is
// exactly why `crewsOutToday` read `now` in UTC for as long as it did, with
// fourteen green tests over it. This class is the stand-in: a `Date` whose
// LOCAL getters answer as a phone in Eastern time would, while UTC has
// already rolled into tomorrow. It overrides only the three getters the
// module calls, so a change that went back to `getUTCDate()` fails here.
//
// Eastern because that is the trail: the A.T. sits in one zone, four or five
// hours behind UTC, which is what makes the evening gap a daily event rather
// than an edge case.
const EASTERN_OFFSET_MS = 5 * 60 * 60 * 1000

class PhoneOnTheTrail extends Date {
  private get local(): Date {
    return new Date(this.getTime() - EASTERN_OFFSET_MS)
  }
  override getFullYear(): number {
    return this.local.getUTCFullYear()
  }
  override getMonth(): number {
    return this.local.getUTCMonth()
  }
  override getDate(): number {
    return this.local.getUTCDate()
  }
}

describe("a crew is out on the hiker's day, not on UTC's", () => {
  // 01:00 UTC on the 15th is 8pm on the 14th at the shelter. Every assertion
  // below is the opposite of what the UTC reading gave.
  const evening = new PhoneOnTheTrail('2026-09-15T01:00:00Z')

  it('does not call tomorrow morning a crew that is out now', () => {
    const tomorrow = project({ starts_on: '2026-09-15', ends_on: '2026-09-15' })

    expect(crewsOutToday([tomorrow], evening)).toHaveLength(0)
  })

  it('still counts the crew whose day the hiker is still in', () => {
    // The other half, and the one that matters more: a crew that IS out
    // while somebody is walking past must not vanish at eight in the evening.
    const today = project({ starts_on: '2026-09-14', ends_on: '2026-09-14' })

    expect(crewsOutToday([today], evening)).toHaveLength(1)
  })

  it('does not grey out the day the hiker is still living', () => {
    const { cells } = workdayCalendarMonth([], evening)
    const state = (date: string) => cells.find((cell) => cell.date === date)?.state

    expect(state('2026-09-14')).toBe('open')
    expect(state('2026-09-13')).toBe('past')
  })

  it('opens the grid on the month the hiker is in, not the one UTC has reached', () => {
    // 8pm on the last day of September, which is October in UTC. A grid that
    // skipped a month on the evening of the 30th would be the same defect
    // wearing a different face.
    const lastEvening = new PhoneOnTheTrail('2026-10-01T01:00:00Z')

    const { cells } = workdayCalendarMonth([], lastEvening)

    expect(cells[0]?.date).toBe('2026-09-01')
    expect(cells.at(-1)?.date).toBe('2026-09-30')
  })
})
