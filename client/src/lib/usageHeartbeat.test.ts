import { describe, expect, it } from 'vitest'

import {
  FRESH_HEARTBEAT,
  type Heartbeat,
  isoWeek,
  MONTHS_REMEMBERED,
  normaliseHeartbeat,
  previousMonth,
  stampHeartbeat,
  type UsageEventName,
  usageDate,
  WEEKS_REMEMBERED,
} from './usageEvents'

// The heartbeat is how the report counts phones without an identifier
// (#1902, features/EVENTING.md §2): each row carries the phone's own "first
// time this week / this month / this club this month" answers, and the server
// counts the yeses. So a phone that answers yes twice for one period is a
// phone counted twice, and nothing downstream can see it happen.
//
// These are property tests: thousands of seeded histories of one phone, in
// the orders a real phone records them - a session row dated when the visit
// STARTED but recorded when it ENDED, after rows from the next day; a clock
// that steps back an hour or a day and forward again (a timezone, a manual
// fix) - each checked against the rule the report depends on. Seeded, so a
// failure names the seed that reproduces it.

/** mulberry32: small, fast, and the same sequence on every machine. */
function generator(seed: number): () => number {
  let state = seed >>> 0
  return () => {
    state = (state + 0x6d2b79f5) >>> 0
    let t = state
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR
const CLUBS = ['NYNJTC', 'AMC-NY', 'GATC', '_unrecorded']
const KINDS: UsageEventName[] = [
  'map_screen_viewed',
  'hike_plan_made',
  'hike_plan_completed',
  'user_login',
]

interface Recorded {
  /** The moment the row describes, on the phone's clock. */
  at: Date
  clubs: string[]
  kind: UsageEventName
}

/** One phone's rows, in the order the phone records them. */
function history(random: () => number, length: number): Recorded[] {
  const between = (low: number, high: number) => low + random() * (high - low)
  let clock = Date.UTC(2026, 0, 1) + between(0, 330) * DAY
  let visitStartedAt: number | null = null
  const rows: Recorded[] = []
  for (let i = 0; i < length; i += 1) {
    const step = random()
    if (step < 0.5) clock += between(1, 90) * MINUTE
    else if (step < 0.75) clock += between(2, 30) * HOUR
    else if (step < 0.88) clock += between(2, 12) * DAY
    else if (step < 0.94)
      clock -= between(1, 36) * HOUR // the clock steps back
    else clock += between(1, 36) * HOUR // and forward

    // A visit that is over is recorded now and dated when it began, which may
    // be yesterday, last week or last month by the phone's own calendar.
    if (visitStartedAt !== null && random() < 0.35) {
      rows.push({ at: new Date(visitStartedAt), clubs: [], kind: 'session' })
      visitStartedAt = null
    }
    if (visitStartedAt === null && random() < 0.5) {
      visitStartedAt = clock - between(0, 6) * HOUR
    }

    const clubs = CLUBS.filter(() => random() < 0.2)
    rows.push({
      at: new Date(clock),
      clubs,
      kind: KINDS[Math.floor(random() * KINDS.length)],
    })
  }
  return rows
}

interface Stamped extends Recorded {
  week_first: boolean
  month_first: boolean
  ever_first: boolean
  club_firsts: string[]
  kind_month_first: boolean
  month_returning: boolean
}

function stampAll(rows: Recorded[]): Stamped[] {
  let heartbeat: Heartbeat = FRESH_HEARTBEAT
  return rows.map((row) => {
    const { stamp, next } = stampHeartbeat(heartbeat, row.at, row.clubs, row.kind)
    heartbeat = next
    return { ...row, ...stamp }
  })
}

/** How many rows answered yes for each period a predicate sorts them into. */
function yesCounts(
  rows: Stamped[],
  periods: (row: Stamped) => string[],
  yes: (row: Stamped, period: string) => boolean,
): Map<string, number> {
  const counts = new Map<string, number>()
  for (const row of rows) {
    for (const period of periods(row)) {
      counts.set(period, (counts.get(period) ?? 0) + (yes(row, period) ? 1 : 0))
    }
  }
  return counts
}

const SEEDS = Array.from({ length: 400 }, (_, i) => i + 1)

function failures(counts: Map<string, number>): string[] {
  return [...counts].filter(([, n]) => n !== 1).map(([period, n]) => `${period}: ${n}`)
}

describe('the heartbeat, over histories a real phone records', () => {
  it('counts a phone exactly once in every week it was active', () => {
    for (const seed of SEEDS) {
      const rows = stampAll(history(generator(seed), 120))
      const counts = yesCounts(
        rows,
        (row) => [isoWeek(row.at)],
        (row) => row.week_first,
      )
      expect(failures(counts), `seed ${seed}`).toEqual([])
    }
  })

  it('counts a phone exactly once in every month it was active', () => {
    for (const seed of SEEDS) {
      const rows = stampAll(history(generator(seed), 120))
      const counts = yesCounts(
        rows,
        (row) => [usageDate(row.at).slice(0, 7)],
        (row) => row.month_first,
      )
      expect(failures(counts), `seed ${seed}`).toEqual([])
    }
  })

  it('counts a phone exactly once per club in every month it touched that club', () => {
    for (const seed of SEEDS) {
      const rows = stampAll(history(generator(seed), 120))
      const counts = yesCounts(
        rows,
        (row) => row.clubs.map((club) => `${usageDate(row.at).slice(0, 7)} ${club}`),
        (row, period) => row.club_firsts.includes(period.split(' ')[1]),
      )
      expect(failures(counts), `seed ${seed}`).toEqual([])
    }
  })

  it('says ever_first on exactly one row in a phone’s whole history', () => {
    for (const seed of SEEDS) {
      const rows = stampAll(history(generator(seed), 120))
      expect(
        rows.filter((row) => row.ever_first),
        `seed ${seed}`,
      ).toHaveLength(1)
    }
  })

  it('counts a phone exactly once per kind of event in every month it did that thing', () => {
    for (const seed of SEEDS) {
      const rows = stampAll(history(generator(seed), 120))
      const counts = yesCounts(
        rows,
        (row) => [`${usageDate(row.at).slice(0, 7)} ${row.kind}`],
        (row) => row.kind_month_first,
      )
      expect(failures(counts), `seed ${seed}`).toEqual([])
    }
  })

  it('never calls a phone returning unless it was already counted the month before', () => {
    for (const seed of SEEDS) {
      const rows = stampAll(history(generator(seed), 120))
      const counted = new Set<string>()
      for (const row of rows) {
        const month = usageDate(row.at).slice(0, 7)
        if (row.month_returning) {
          expect(row.month_first, `seed ${seed}: returning rides on month_first`).toBe(
            true,
          )
          expect(counted.has(previousMonth(month)), `seed ${seed}, ${month}`).toBe(true)
        }
        counted.add(month)
      }
    }
  })
})

describe('the heartbeat, on a phone whose rows arrive in date order', () => {
  it('calls a phone returning exactly when it was active the month before', () => {
    const months = ['2026-03', '2026-04', '2026-06', '2026-07', '2026-08', '2027-01']
    let heartbeat: Heartbeat = FRESH_HEARTBEAT
    const returning: Record<string, boolean> = {}
    for (const month of months) {
      for (const day of [3, 9, 21]) {
        const { stamp, next } = stampHeartbeat(
          heartbeat,
          new Date(`${month}-${String(day).padStart(2, '0')}T12:00:00`),
          [],
          'map_screen_viewed',
        )
        if (stamp.month_first) returning[month] = stamp.month_returning
        heartbeat = next
      }
    }

    expect(returning).toEqual({
      '2026-03': false,
      '2026-04': true,
      '2026-06': false,
      '2026-07': true,
      '2026-08': true,
      '2027-01': false,
    })
  })
})

describe('a row older than everything the phone remembers', () => {
  it('is never counted as first, because it cannot be told apart from one that was', () => {
    // Weekly from January to July: both remembered sets are full, so
    // December 2025 is older than anything the phone still knows about.
    let heartbeat: Heartbeat = FRESH_HEARTBEAT
    for (let week = 0; week < 26; week += 1) {
      heartbeat = stampHeartbeat(
        heartbeat,
        new Date(2026, 0, 5 + week * 7),
        ['NYNJTC'],
        'map_screen_viewed',
      ).next
    }
    expect(heartbeat.weeks).toHaveLength(WEEKS_REMEMBERED)
    expect(heartbeat.months).toHaveLength(MONTHS_REMEMBERED)

    const { stamp, next } = stampHeartbeat(
      heartbeat,
      new Date(2025, 11, 30),
      ['GATC'],
      'hike_plan_made',
    )

    expect(stamp).toMatchObject({
      week_first: false,
      month_first: false,
      club_firsts: [],
      kind_month_first: false,
      month_returning: false,
    })
    expect(next.months).toEqual(heartbeat.months)
  })
})

describe('normaliseHeartbeat', () => {
  it('reads the last-week-and-month shape an earlier build stored as one-entry sets', () => {
    expect(
      normaliseHeartbeat({
        week: '2026-W44',
        month: '2026-10',
        ever: true,
        clubs: ['NYNJTC'],
      }),
    ).toEqual({
      weeks: ['2026-W44'],
      months: ['2026-10'],
      ever: true,
      clubs: { '2026-10': ['NYNJTC'] },
      kinds: {},
    })
  })

  it('treats anything unreadable as a phone that has counted nothing yet', () => {
    expect(normaliseHeartbeat('garbage')).toEqual(FRESH_HEARTBEAT)
    expect(normaliseHeartbeat({ weeks: [3, 'x'], months: null })).toMatchObject({
      weeks: ['x'],
      months: [],
    })
  })
})
